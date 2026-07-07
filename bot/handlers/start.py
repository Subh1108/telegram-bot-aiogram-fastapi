from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import main_menu
from database.db import get_or_create_user, get_setting
from database.models import User

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession):
    referral_code = command.args if command.args else None
    user, created = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referral_code=referral_code,
    )

    welcome_template = await get_setting(
        session, "welcome_message", "👋 Welcome, {name}! I'm your all-in-one assistant bot."
    )
    text = welcome_template.format(name=message.from_user.first_name or "there")
    await message.answer(text, reply_markup=main_menu(is_admin=user.is_admin))


@router.callback_query(F.data == "menu:home")
async def show_home(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one_or_none()
    is_admin = bool(user and user.is_admin)
    await callback.message.edit_text(
        "🏠 <b>Main Menu</b>\nChoose an option below:",
        reply_markup=main_menu(is_admin=is_admin),
    )
    await callback.answer()
