from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def duel_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Создать дуэль", callback_data="duel:create", style="success"))
    builder.row(InlineKeyboardButton(text="🔥 Активные дуэли", callback_data="duel:active", style="primary"))
    builder.row(InlineKeyboardButton(text="📜 История дуэлей", callback_data="duel:history", style="primary"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:games", style="danger"))
    return builder.as_markup()


def active_duels_kb(duels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for duel in duels:
        builder.row(InlineKeyboardButton(
            text=f"⚔️ Дуэль #{duel.id} — {duel.amount:.0f} ⭐",
            callback_data=f"duel:view:{duel.id}",
            style="primary",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="duel:menu", style="danger"))
    return builder.as_markup()


def duel_view_kb(duel_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Вступить в дуэль", callback_data=f"duel:join:{duel_id}", style="success"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="duel:active", style="danger"))
    return builder.as_markup()


def duel_creator_kb(duel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить дуэль", callback_data=f"duel:cancel:{duel_id}", style="danger")
    ]])


def duel_roll_kb(duel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎲 Бросить кубик", callback_data=f"duel:roll:{duel_id}", style="success")
    ]])


def duel_confirm_kb(duel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"duel:confirm:{duel_id}", style="success"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"duel:decline_join:{duel_id}", style="danger"),
    ]])


def back_to_duel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ К дуэлям", callback_data="duel:menu", style="danger")
    ]])
