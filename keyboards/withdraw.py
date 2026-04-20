from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

WITHDRAW_AMOUNTS = [15, 25, 50, 100]


def withdraw_amounts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for amount in WITHDRAW_AMOUNTS:
        builder.add(InlineKeyboardButton(text=f"{amount} ⭐", callback_data=f"withdraw:{amount}", style="primary"))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger"))
    return builder.as_markup()


def withdraw_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger")]]
    )


def captcha_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="withdraw:cancel", style="danger")]]
    )


def withdraw_success_kb(channel_url: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.row(InlineKeyboardButton(text="📢 Канал выплат", url=channel_url, style="primary"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main", style="danger"))
    return builder.as_markup()
