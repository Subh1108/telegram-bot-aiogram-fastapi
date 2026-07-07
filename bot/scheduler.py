"""
Lightweight polling scheduler (no extra dependency needed beyond asyncio).
Checks every 30s for scheduled broadcasts whose time has come and sends them.
"""
import asyncio
import datetime
import logging

from aiogram import Bot
from sqlalchemy import select

from database.db import SessionLocal
from database.models import BroadcastLog
from bot.services import send_broadcast

logger = logging.getLogger("scheduler")


async def run_scheduler(bot: Bot, poll_seconds: int = 30):
    while True:
        try:
            async with SessionLocal() as session:
                now = datetime.datetime.utcnow()
                result = await session.execute(
                    select(BroadcastLog).where(
                        BroadcastLog.scheduled_for.isnot(None),
                        BroadcastLog.scheduled_for <= now,
                        BroadcastLog.sent_at.is_(None),
                    )
                )
                due = result.scalars().all()
                for log in due:
                    logger.info("Sending scheduled broadcast #%s", log.id)
                    body, segment = log.body, log.segment
                    # Remove the placeholder row, send_broadcast will create the "real" log entry
                    await session.delete(log)
                    await session.flush()
                    await send_broadcast(bot, session, body, segment)
                if due:
                    await session.commit()
        except Exception:
            logger.exception("Scheduler loop error")
        await asyncio.sleep(poll_seconds)
