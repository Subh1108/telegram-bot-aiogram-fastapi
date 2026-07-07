from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import back_button, faq_list
from database.models import User, FAQItem
from database.db import count_referrals

router = Router(name="menu")


async def _current_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


@router.callback_query(F.data == "menu:profile")
async def show_profile(callback: CallbackQuery, session: AsyncSession):
    user = await _current_user(session, callback.from_user.id)
    referrals = await count_referrals(session, user.id)
    text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"<b>Name:</b> {(user.first_name or '').strip()} {(user.last_name or '').strip()}\n"
        f"<b>Username:</b> {'@' + user.username if user.username else '—'}\n"
        f"<b>Joined:</b> {user.joined_at.strftime('%d %b %Y')}\n"
        f"<b>Referrals:</b> {referrals}\n"
        f"<b>Status:</b> {'🛠 Admin' if user.is_admin else '✅ Member'}"
    )
    await callback.message.edit_text(text, reply_markup=back_button())
    await callback.answer()


@router.callback_query(F.data == "menu:faq")
async def show_faq(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(select(FAQItem).order_by(FAQItem.sort_order))
    items = result.scalars().all()
    await callback.message.edit_text(
        "❓ <b>Frequently Asked Questions</b>\nTap a question to see the answer:",
        reply_markup=faq_list(items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq:"))
async def show_faq_answer(callback: CallbackQuery, session: AsyncSession):
    faq_id = int(callback.data.split(":")[1])
    item = await session.get(FAQItem, faq_id)
    if item:
        await callback.message.edit_text(
            f"❓ <b>{item.question}</b>\n\n{item.answer}",
            reply_markup=back_button("menu:faq"),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:invite")
async def show_invite(callback: CallbackQuery, session: AsyncSession):
    user = await _current_user(session, callback.from_user.id)
    referrals = await count_referrals(session, user.id)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user.referral_code}"
    text = (
        "🔗 <b>Invite Friends</b>\n\n"
        f"Share your personal link — anyone who joins through it is credited to you:\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Friends invited so far: <b>{referrals}</b>"
    )
    await callback.message.edit_text(text, reply_markup=back_button(), disable_web_page_preview=True)
    await callback.answer()
