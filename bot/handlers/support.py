from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import back_button, cancel_kb
from bot.states import SupportForm
from database.models import User
from database.db import create_ticket

router = Router(name="support")


@router.callback_query(F.data == "menu:support")
async def start_support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportForm.waiting_for_message)
    await callback.message.edit_text(
        "🛟 <b>Contact Support</b>\n\nSend your question or issue as a message and our team "
        "will reply to you right here in this chat.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(SupportForm.waiting_for_message)
async def receive_support_message(message: Message, state: FSMContext, session: AsyncSession):
    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()
    await create_ticket(session, user, message.text or "(non-text message)")
    await state.clear()
    await message.answer(
        "✅ Thanks! Your message was sent to our support team. We'll reply here as soon as possible.",
        reply_markup=back_button(),
    )


@router.callback_query(F.data == "cancel")
async def cancel_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Cancelled.", reply_markup=back_button())
    await callback.answer()


@router.message(Command("support"))
async def support_command(message: Message, session: AsyncSession):
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer("Usage: /support your message here")
        return
    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()
    await create_ticket(session, user, text)
    await message.answer("✅ Your message was sent to our support team.")
