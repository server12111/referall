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


def build_combined_wall_kb(
    botohub_tasks: list[str],
    flyer_tasks: list[dict],
    custom_sponsors: list[dict],
    piarflow_tasks: list[str] | None = None,
    subgram_sponsors: list[dict] | None = None,
    linkni_url: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Build one combined subscription wall keyboard from all integrations.

    botohub_tasks    — list of channel URLs from BotoHub
    flyer_tasks      — list of task dicts from Flyer (url/link/invite_link field)
    custom_sponsors  — list of dicts {'title': ..., 'link': ...} from admin panel
    piarflow_tasks   — list of channel URLs from PiarFlow
    subgram_sponsors — list of dicts {'link': ..., 'button_text': ...} from Subgram
    """
    buttons = []
    i = 1

    for url in (botohub_tasks or []):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url)])
        i += 1

    for task in (flyer_tasks or []):
        url = (
            task.get("url")
            or task.get("link")
            or task.get("invite_link")
            or task.get("channel_url")
            or ""
        )
        if url:
            buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url)])
            i += 1

    for url in (piarflow_tasks or []):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url)])
        i += 1

    for sp in (subgram_sponsors or []):
        label = sp.get("button_text") or sp.get("title") or f"📢 Канал {i}"
        buttons.append([InlineKeyboardButton(text=label, url=sp["link"])])
        i += 1

    for sp in (custom_sponsors or []):
        buttons.append([InlineKeyboardButton(text=f"📢 {sp['title']}", url=sp["link"])])

    if linkni_url:
        buttons.append([InlineKeyboardButton(text="🔗 Linkni — подписаться", url=linkni_url)])

    buttons.append(
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="wall:check")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
