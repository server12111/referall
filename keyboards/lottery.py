from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def lottery_menu_kb(can_buy: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_buy:
        builder.row(InlineKeyboardButton(text="🎟 Купить билет (5 ⭐)", callback_data="game:lottery_buy", style="success"))
    builder.row(InlineKeyboardButton(text="◀️ К играм", callback_data="menu:games", style="danger"))
    return builder.as_markup()


def admin_lottery_kb(has_active: bool, has_participants: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_active:
        if has_participants:
            builder.row(InlineKeyboardButton(text="🎲 Случайный розыгрыш", callback_data="admin:lottery_random", style="primary"))
            builder.row(InlineKeyboardButton(text="👤 Выбрать победителя", callback_data="admin:lottery_pick", style="primary"))
        builder.row(InlineKeyboardButton(text="🔴 Отменить лотерею", callback_data="admin:lottery_cancel", style="danger"))
    else:
        builder.row(InlineKeyboardButton(text="➕ Запустить новую лотерею", callback_data="admin:lottery_new", style="success"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main", style="danger"))
    return builder.as_markup()


def admin_lottery_pick_kb(participants: list) -> InlineKeyboardMarkup:
    """participants: list of (user_id, username, first_name, ticket_count)"""
    builder = InlineKeyboardBuilder()
    for uid, username, first_name, cnt in participants:
        display = f"@{username}" if username else first_name
        builder.row(InlineKeyboardButton(
            text=f"{display} — {cnt} билет(ов)",
            callback_data=f"admin:lottery_winner:{uid}",
            style="primary",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:lottery", style="danger"))
    return builder.as_markup()
