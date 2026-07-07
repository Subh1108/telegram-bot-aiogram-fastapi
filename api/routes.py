import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func

from api.auth import create_token, verify_password, require_auth
from database.db import (
    SessionLocal, search_users, get_setting, set_setting, recent_activity
)
from database.models import User, SupportTicket, TicketStatus, BroadcastLog, ActivityEvent
from bot.services import send_broadcast, reply_to_ticket

router = APIRouter()


# ---------- Auth ----------

class LoginBody(BaseModel):
    password: str


@router.post("/auth/login")
async def login(body: LoginBody):
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    return {"token": create_token()}


# ---------- Stats ----------

@router.get("/stats", dependencies=[Depends(require_auth)])
async def get_stats():
    async with SessionLocal() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
        today = datetime.datetime.utcnow().date()
        active_today = (await session.execute(
            select(func.count(User.id)).where(func.date(User.last_active_at) == today)
        )).scalar_one()
        open_tickets = (await session.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.status == TicketStatus.OPEN)
        )).scalar_one()
        broadcasts_sent = (await session.execute(select(func.count(BroadcastLog.id)))).scalar_one()

        # last 14 days signups, for the growth chart
        signups = []
        for i in range(13, -1, -1):
            day = today - datetime.timedelta(days=i)
            count = (await session.execute(
                select(func.count(User.id)).where(func.date(User.joined_at) == day)
            )).scalar_one()
            signups.append({"date": day.isoformat(), "count": count})

        return {
            "total_users": total_users,
            "active_today": active_today,
            "open_tickets": open_tickets,
            "broadcasts_sent": broadcasts_sent,
            "signups_last_14d": signups,
        }


@router.get("/activity", dependencies=[Depends(require_auth)])
async def get_activity():
    async with SessionLocal() as session:
        events = await recent_activity(session, limit=40)
        return [
            {"id": e.id, "type": e.event_type, "description": e.description,
             "created_at": e.created_at.isoformat()}
            for e in events
        ]


# ---------- Users ----------

@router.get("/users", dependencies=[Depends(require_auth)])
async def list_users(q: str | None = None, page: int = 1, page_size: int = 20):
    async with SessionLocal() as session:
        users, total = await search_users(session, q, page, page_size)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "users": [
                {
                    "id": u.id, "telegram_id": u.telegram_id, "display_name": u.display_name,
                    "is_admin": u.is_admin, "is_banned": u.is_banned,
                    "joined_at": u.joined_at.isoformat(),
                    "last_active_at": u.last_active_at.isoformat(),
                }
                for u in users
            ],
        }


@router.post("/users/{user_id}/ban", dependencies=[Depends(require_auth)])
async def ban_user(user_id: int):
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        user.is_banned = True
        await session.commit()
        return {"ok": True}


@router.post("/users/{user_id}/unban", dependencies=[Depends(require_auth)])
async def unban_user(user_id: int):
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "User not found")
        user.is_banned = False
        await session.commit()
        return {"ok": True}


# ---------- Tickets ----------

@router.get("/tickets", dependencies=[Depends(require_auth)])
async def list_tickets(status_filter: str | None = None):
    async with SessionLocal() as session:
        stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
        if status_filter:
            stmt = stmt.where(SupportTicket.status == status_filter)
        tickets = (await session.execute(stmt)).scalars().all()
        out = []
        for t in tickets:
            user = await session.get(User, t.user_id)
            out.append({
                "id": t.id, "subject": t.subject, "status": t.status.value,
                "user": user.display_name if user else "unknown",
                "created_at": t.created_at.isoformat(),
            })
        return out


@router.get("/tickets/{ticket_id}", dependencies=[Depends(require_auth)])
async def get_ticket(ticket_id: int):
    async with SessionLocal() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        user = await session.get(User, ticket.user_id)
        messages = ticket.messages
        return {
            "id": ticket.id, "subject": ticket.subject, "status": ticket.status.value,
            "user": user.display_name if user else "unknown",
            "messages": [
                {"from_admin": m.from_admin, "body": m.body, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
        }


class ReplyBody(BaseModel):
    message: str


@router.post("/tickets/{ticket_id}/reply", dependencies=[Depends(require_auth)])
async def reply_ticket(ticket_id: int, body: ReplyBody, request: Request):
    async with SessionLocal() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        bot = request.app.state.bot
        ok = await reply_to_ticket(bot, session, ticket, body.message)
        await session.commit()
        return {"ok": ok}


@router.post("/tickets/{ticket_id}/close", dependencies=[Depends(require_auth)])
async def close_ticket(ticket_id: int):
    async with SessionLocal() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        if not ticket:
            raise HTTPException(404, "Ticket not found")
        ticket.status = TicketStatus.CLOSED
        await session.commit()
        return {"ok": True}


# ---------- Broadcast ----------

class BroadcastBody(BaseModel):
    message: str
    segment: str = "all"
    scheduled_for: str | None = None  # ISO datetime, optional


@router.post("/broadcast", dependencies=[Depends(require_auth)])
async def create_broadcast(body: BroadcastBody, request: Request):
    async with SessionLocal() as session:
        if body.scheduled_for:
            log = BroadcastLog(
                body=body.message, segment=body.segment,
                scheduled_for=datetime.datetime.fromisoformat(body.scheduled_for),
            )
            session.add(log)
            await session.commit()
            return {"ok": True, "scheduled": True}
        else:
            bot = request.app.state.bot
            log = await send_broadcast(bot, session, body.message, body.segment)
            await session.commit()
            return {"ok": True, "sent": log.sent_count, "failed": log.failed_count}


@router.get("/broadcast/history", dependencies=[Depends(require_auth)])
async def broadcast_history():
    async with SessionLocal() as session:
        logs = (await session.execute(
            select(BroadcastLog).order_by(BroadcastLog.created_at.desc()).limit(50)
        )).scalars().all()
        return [
            {
                "id": l.id, "body": l.body, "segment": l.segment,
                "sent_count": l.sent_count, "failed_count": l.failed_count,
                "scheduled_for": l.scheduled_for.isoformat() if l.scheduled_for else None,
                "sent_at": l.sent_at.isoformat() if l.sent_at else None,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ]


# ---------- Settings ----------

@router.get("/settings", dependencies=[Depends(require_auth)])
async def get_settings():
    async with SessionLocal() as session:
        return {
            "maintenance_mode": await get_setting(session, "maintenance_mode", "off"),
            "welcome_message": await get_setting(session, "welcome_message", ""),
        }


class SettingsBody(BaseModel):
    maintenance_mode: str | None = None
    welcome_message: str | None = None


@router.post("/settings", dependencies=[Depends(require_auth)])
async def update_settings(body: SettingsBody):
    async with SessionLocal() as session:
        if body.maintenance_mode is not None:
            await set_setting(session, "maintenance_mode", body.maintenance_mode)
        if body.welcome_message is not None:
            await set_setting(session, "welcome_message", body.welcome_message)
        await session.commit()
        return {"ok": True}
