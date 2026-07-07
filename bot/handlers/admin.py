from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import back_button, admin_panel, cancel_kb
from bot.states import BroadcastForm
from bot.services import send_broadcast
from database.models import User, SupportTicket, TicketStatus

router = Router(name="admin")


async def _is_admin(session: AsyncSession, telegram_id: int) -> bool:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    return bool(user and user.is_admin)


@router.callback_query(F.data == "menu:admin")
async def open_admin_panel(callback: CallbackQuery, session: AsyncSession):
    if not await _is_admin(session, callback.from_user.id):
        await callback.answer("Admins only.", show_alert=True)
        return
    await callback.message.edit_text("🛠 <b>Admin Panel</b>", reply_markup=admin_panel())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    if not await _is_admin(session, callback.from_user.id):
        await callback.answer("Admins only.", show_alert=True)
        return
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    open_tickets = (await session.execute(
        select(func.count(SupportTicket.id)).where(SupportTicket.status == TicketStatus.OPEN)
    )).scalar_one()
    banned = (await session.execute(select(func.count(User.id)).where(User.is_banned == True))).scalar_one()  # noqa: E712
    text = (
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Total users: <b>{total_users}</b>\n"
        f"🚫 Banned: <b>{banned}</b>\n"
        f"🛟 Open tickets: <b>{open_tickets}</b>"
    )
    await callback.message.edit_text(text, reply_markup=back_button("menu:admin"))
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard_info")
async def dashboard_info(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌐 The full web dashboard (charts, ticket inbox, scheduled broadcasts, user search) "
        "is available wherever you're running the API — by default at:\n\n"
        "<code>http://localhost:8000</code>",
        reply_markup=back_button("menu:admin"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    if not await _is_admin(session, callback.from_user.id):
        await callback.answer("Admins only.", show_alert=True)
        return
    await state.set_state(BroadcastForm.waiting_for_message)
    await callback.message.edit_text(
        "📢 <b>Broadcast</b>\n\nSend the message you want to broadcast to <b>all users</b>.\n"
        "(For scheduled or segmented broadcasts, use the web dashboard.)",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(BroadcastForm.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if not await _is_admin(session, message.from_user.id):
        await state.clear()
        return
    await message.answer("📤 Sending broadcast, this may take a moment...")
    log = await send_broadcast(bot, session, message.text, segment="all")
    await state.clear()
    await message.answer(
        f"✅ Broadcast complete.\nSent: {log.sent_count} · Failed: {log.failed_count}",
        reply_markup=back_button("menu:admin"),
    )


@router.message(Command("stats"))
async def stats_command(message: Message, session: AsyncSession):
    if not await _is_admin(session, message.from_user.id):
        return
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    await message.answer(f"👥 Total users: {total_users}")
