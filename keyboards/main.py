from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Получить звёзды", callback_data="menu:earn", style="primary"))
    builder.row(InlineKeyboardButton(text="👥 Мои рефералы", callback_data="menu:referrals", style="primary"))
    builder.row(
        InlineKeyboardButton(text="🎁 Бонус", callback_data="menu:bonus", style="primary"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="menu:profile", style="primary"),
    )
    builder.row(InlineKeyboardButton(text="📋 Задания", callback_data="menu:tasks", style="primary"))
    builder.row(
        InlineKeyboardButton(text="🏆 Топ", callback_data="menu:top", style="primary"),
        InlineKeyboardButton(text="🎮 Игры", callback_data="menu:games", style="primary"),
    )
    builder.row(InlineKeyboardButton(text="💰 Вывод", callback_data="menu:withdraw", style="primary"))
    builder.row(InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="menu:search", style="primary"))
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger")]]
    )


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Перевести звёзды", callback_data="profile:transfer", style="primary"))
    builder.row(InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo:enter", style="primary"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger"))
    return builder.as_markup()


def task_single_kb(task_type: str, identifier: str, url: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard for single task display (one-at-a-time mode)."""
    builder = InlineKeyboardBuilder()
    if url:
        btn_text = "🔗 Выполнить задание" if task_type in ("linkni", "flyerservice") else "📢 Подписаться"
        builder.row(InlineKeyboardButton(text=btn_text, url=url, style="primary"))
    if task_type == "linkni":
        builder.row(InlineKeyboardButton(text="✅ Проверить", callback_data=f"task:linkni:{identifier}", style="success"))
    elif task_type == "flyerservice":
        builder.row(InlineKeyboardButton(text="✅ Проверить", callback_data="task:flyerservice:check", style="success"))
    else:
        builder.row(InlineKeyboardButton(text="✅ Проверить", callback_data=f"task:bot:{identifier}", style="success"))
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="task:skip"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main", style="danger"),
    )
    return builder.as_markup()


def task_done_kb() -> InlineKeyboardMarkup:
    """Shown after task completion."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➡️ Следующее задание", callback_data="menu:tasks", style="success"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main", style="danger"))
    return builder.as_markup()
