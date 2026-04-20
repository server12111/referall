from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def top_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Топ по рефералам", callback_data="top:type:refs", style="primary"))
    builder.row(InlineKeyboardButton(text="⭐ Топ по звёздам", callback_data="top:type:stars", style="primary"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger"))
    return builder.as_markup()


def top_period_kb(top_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data=f"top:{top_type}:day", style="primary"),
        InlineKeyboardButton(text="📆 Неделя", callback_data=f"top:{top_type}:week", style="primary"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Месяц", callback_data=f"top:{top_type}:month", style="primary"),
        InlineKeyboardButton(text="🏆 Всё время", callback_data=f"top:{top_type}:all", style="primary"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:top", style="danger"))
    return builder.as_markup()


def top_result_kb(top_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"top:type:{top_type}", style="danger")
    ]])
