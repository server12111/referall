from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_botohub_wall_kb(tasks: list[str]) -> InlineKeyboardMarkup:
    """
    Build the subscription wall keyboard.

    Each task URL becomes a channel button, plus a confirm button at the bottom.
    """
    buttons = []
    for i, url in enumerate(tasks, start=1):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url)])
    buttons.append(
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="botohub:check")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
