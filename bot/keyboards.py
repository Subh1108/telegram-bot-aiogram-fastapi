from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Profile", callback_data="menu:profile")
    kb.button(text="❓ FAQ / Help", callback_data="menu:faq")
    kb.button(text="🛟 Support", callback_data="menu:support")
    kb.button(text="🔗 Invite Friends", callback_data="menu:invite")
    if is_admin:
        kb.button(text="🛠 Admin Panel", callback_data="menu:admin")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def back_button(target: str = "menu:home") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Back", callback_data=target)
    return kb.as_markup()


def faq_list(items) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=item.question, callback_data=f"faq:{item.id}")
    kb.button(text="⬅️ Back", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def admin_panel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats", callback_data="admin:stats")
    kb.button(text="📢 Broadcast", callback_data="admin:broadcast")
    kb.button(text="🌐 Open Dashboard", callback_data="admin:dashboard_info")
    kb.button(text="⬅️ Back", callback_data="menu:home")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✖️ Cancel", callback_data="cancel")
    return kb.as_markup()
