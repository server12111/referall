from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Получить звёзды", callback_data="menu:earn"))
    builder.row(InlineKeyboardButton(text="👥 Мои рефералы", callback_data="menu:referrals"))
    builder.row(
        InlineKeyboardButton(text="🎁 Бонус", callback_data="menu:bonus"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile"),
    )
    builder.row(InlineKeyboardButton(text="📋 Задания", callback_data="menu:tasks"))
    builder.row(
        InlineKeyboardButton(text="🏆 Топ", callback_data="menu:top"),
        InlineKeyboardButton(text="🎮 Игры", callback_data="menu:games"),
    )
    builder.row(InlineKeyboardButton(text="💰 Вывод", callback_data="menu:withdraw"))
    builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="menu:search"))
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔴 Назад", callback_data="menu:main")]]
    )


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Перевести звёзды", callback_data="profile:transfer"))
    builder.row(InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo:enter"))
    builder.row(InlineKeyboardButton(text="🔴 Назад", callback_data="menu:main"))
    return builder.as_markup()


def task_single_kb(task_type: str, identifier: str, url: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard for single task display (one-at-a-time mode)."""
    builder = InlineKeyboardBuilder()
    if url:
        btn_text = "🔵 Выполнить задание" if task_type in ("linkni", "flyerservice") else "🔵 Подписаться"
        builder.row(InlineKeyboardButton(text=btn_text, url=url))
    if task_type == "linkni":
        builder.row(InlineKeyboardButton(text="🟢 Проверить", callback_data=f"task:linkni:{identifier}"))
    elif task_type == "flyerservice":
        builder.row(InlineKeyboardButton(text="🟢 Проверить", callback_data="task:flyerservice:check"))
    else:
        builder.row(InlineKeyboardButton(text="🟢 Проверить", callback_data=f"task:bot:{identifier}"))
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="task:skip"),
        InlineKeyboardButton(text="🔴 Назад", callback_data="menu:main"),
    )
    return builder.as_markup()


def task_done_kb() -> InlineKeyboardMarkup:
    """Shown after task completion."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Следующее задание", callback_data="menu:tasks"))
    builder.row(InlineKeyboardButton(text="🔴 Главное меню", callback_data="menu:main"))
    return builder.as_markup()
