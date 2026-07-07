"""
Async SQLAlchemy engine/session + small helper/service functions
used by both the bot handlers and the API routes.
"""
import datetime
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select, func, or_

from config import DATABASE_URL, ADMIN_IDS
from database.models import (
    Base, User, SupportTicket, TicketMessage, TicketStatus,
    BroadcastLog, Setting, ActivityEvent, FAQItem, gen_referral_code
)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # seed defaults
    async with SessionLocal() as session:
        await _seed_settings(session)
        await _seed_faq(session)
        await session.commit()


async def _seed_settings(session: AsyncSession):
    defaults = {
        "maintenance_mode": "off",
        "welcome_message": "👋 Welcome, {name}! I'm your all-in-one assistant bot.",
    }
    for key, value in defaults.items():
        existing = await session.get(Setting, key)
        if not existing:
            session.add(Setting(key=key, value=value))


async def _seed_faq(session: AsyncSession):
    count = (await session.execute(select(func.count(FAQItem.id)))).scalar_one()
    if count == 0:
        session.add_all([
            FAQItem(question="What can this bot do?",
                    answer="I can manage your profile, answer FAQs, take support requests, "
                           "and send you updates via broadcast. Use /menu to see all options.",
                    sort_order=1),
            FAQItem(question="How do I contact a human?",
                    answer="Use the Support option in the menu, or send /support followed by "
                           "your message. Our team will reply here in this chat.",
                    sort_order=2),
            FAQItem(question="How do referrals work?",
                    answer="Open Invite Friends in the menu to get your personal invite link. "
                           "Every person who joins through it is credited to your account.",
                    sort_order=3),
        ])


# ---------- Users ----------

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None,
                              first_name: str | None, last_name: str | None,
                              referral_code: str | None = None) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    created = False
    if user is None:
        referred_by = None
        if referral_code:
            ref_result = await session.execute(select(User).where(User.referral_code == referral_code))
            referred_by = ref_result.scalar_one_or_none()
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=telegram_id in ADMIN_IDS,
            referred_by_id=referred_by.id if referred_by else None,
        )
        session.add(user)
        await session.flush()
        created = True
        session.add(ActivityEvent(
            event_type="new_user",
            description=f"New user joined: {user.display_name}"
            + (f" (invited by {referred_by.display_name})" if referred_by else ""),
        ))
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.last_active_at = datetime.datetime.utcnow()
    return user, created


async def count_referrals(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(User.id)).where(User.referred_by_id == user_id)
    )
    return result.scalar_one()


async def search_users(session: AsyncSession, query: str | None, page: int = 1, page_size: int = 20):
    stmt = select(User).order_by(User.joined_at.desc())
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.first_name.ilike(like),
                               User.last_name.ilike(like)))
    total = (await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )).scalar_one()
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    users = (await session.execute(stmt)).scalars().all()
    return users, total


# ---------- Settings ----------

async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    setting = await session.get(Setting, key)
    return setting.value if setting else default


async def set_setting(session: AsyncSession, key: str, value: str):
    setting = await session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))


# ---------- Activity feed ----------

async def log_activity(session: AsyncSession, event_type: str, description: str):
    session.add(ActivityEvent(event_type=event_type, description=description))


async def recent_activity(session: AsyncSession, limit: int = 30) -> Sequence[ActivityEvent]:
    result = await session.execute(
        select(ActivityEvent).order_by(ActivityEvent.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


# ---------- Tickets ----------

async def create_ticket(session: AsyncSession, user: User, body: str) -> SupportTicket:
    ticket = SupportTicket(user_id=user.id, subject=body[:60])
    session.add(ticket)
    await session.flush()
    session.add(TicketMessage(ticket_id=ticket.id, from_admin=False, body=body))
    session.add(ActivityEvent(event_type="ticket", description=f"New support ticket from {user.display_name}"))
    return ticket
