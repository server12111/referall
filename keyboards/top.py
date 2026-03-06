from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def top_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Топ по рефералам", callback_data="top:type:refs"))
    builder.row(InlineKeyboardButton(text="⭐ Топ по звёздам", callback_data="top:type:stars"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"))
    return builder.as_markup()


def top_period_kb(top_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data=f"top:{top_type}:day"),
        InlineKeyboardButton(text="📆 Неделя", callback_data=f"top:{top_type}:week"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Месяц", callback_data=f"top:{top_type}:month"),
        InlineKeyboardButton(text="🏆 Всё время", callback_data=f"top:{top_type}:all"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:top"))
    return builder.as_markup()


def top_result_kb(top_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"top:type:{top_type}")
    ]])
