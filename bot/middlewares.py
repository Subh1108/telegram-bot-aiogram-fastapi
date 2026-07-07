from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from database.db import SessionLocal, get_setting
from sqlalchemy import select
from database.models import User


class DbSessionMiddleware(BaseMiddleware):
    """Opens one DB session per update and commits at the end."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result


class MaintenanceMiddleware(BaseMiddleware):
    """Blocks non-admin users when maintenance mode is enabled."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        user_obj = getattr(event, "from_user", None) or getattr(
            getattr(event, "message", None) or getattr(event, "callback_query", None),
            "from_user", None
        )
        if session is not None and user_obj is not None:
            mode = await get_setting(session, "maintenance_mode", "off")
            if mode == "on":
                result = await session.execute(select(User).where(User.telegram_id == user_obj.id))
                db_user = result.scalar_one_or_none()
                if not (db_user and db_user.is_admin):
                    target = getattr(event, "message", None) or getattr(event, "callback_query", None)
                    if target is not None:
                        if hasattr(target, "answer"):
                            try:
                                await target.answer(
                                    "🚧 The bot is under maintenance right now. Please check back soon."
                                )
                            except Exception:
                                pass
                    return  # swallow the update, don't call handler
        return await handler(event, data)
