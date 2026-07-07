"""
Business logic shared between the Telegram bot handlers and the
dashboard API (e.g. sending a broadcast can be triggered from a
/broadcast command OR from a button click in the web dashboard).
"""
import asyncio
import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, BroadcastLog, SupportTicket, TicketMessage, TicketStatus
from database.db import log_activity


def _segment_query(segment: str):
    stmt = select(User).where(User.is_banned == False)  # noqa: E712
    if segment == "active_7d":
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        stmt = stmt.where(User.last_active_at >= cutoff)
    elif segment == "new_30d":
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        stmt = stmt.where(User.joined_at >= cutoff)
    return stmt


async def send_broadcast(bot: Bot, session: AsyncSession, body: str, segment: str = "all") -> BroadcastLog:
    result = await session.execute(_segment_query(segment))
    users = result.scalars().all()

    log = BroadcastLog(body=body, segment=segment, sent_at=datetime.datetime.utcnow())
    session.add(log)
    await session.flush()

    sent, failed = 0, 0
    for user in users:
        try:
            await bot.send_message(user.telegram_id, body)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(user.telegram_id, body)
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # stay comfortably under rate limits

    log.sent_count = sent
    log.failed_count = failed
    await log_activity(
        session, "broadcast",
        f"Broadcast sent to {sent} users ({segment}), {failed} failed"
    )
    return log


async def reply_to_ticket(bot: Bot, session: AsyncSession, ticket: SupportTicket, body: str):
    session.add(TicketMessage(ticket_id=ticket.id, from_admin=True, body=body))
    ticket.status = TicketStatus.ANSWERED
    user = await session.get(User, ticket.user_id)
    try:
        await bot.send_message(
            user.telegram_id,
            f"🛟 <b>Support reply</b>\n\n{body}",
        )
        ok = True
    except Exception:
        ok = False
    await log_activity(session, "ticket_reply", f"Admin replied to ticket #{ticket.id}")
    return ok
