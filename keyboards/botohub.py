from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_botohub_wall_kb(tasks: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for i, url in enumerate(tasks, start=1):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url, style="primary")])
    buttons.append(
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="botohub:check", style="success")]
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
    buttons = []
    i = 1

    for url in (botohub_tasks or []):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url, style="primary")])
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
            buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url, style="primary")])
            i += 1

    for url in (piarflow_tasks or []):
        buttons.append([InlineKeyboardButton(text=f"📢 Канал {i}", url=url, style="primary")])
        i += 1

    for sp in (subgram_sponsors or []):
        label = sp.get("button_text") or sp.get("title") or f"📢 Канал {i}"
        buttons.append([InlineKeyboardButton(text=label, url=sp["link"], style="primary")])
        i += 1

    for sp in (custom_sponsors or []):
        buttons.append([InlineKeyboardButton(text=f"📢 {sp['title']}", url=sp["link"], style="primary")])

    if linkni_url:
        buttons.append([InlineKeyboardButton(text="🔗 Linkni — подписаться", url=linkni_url, style="primary")])

    buttons.append(
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="wall:check", style="success")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
