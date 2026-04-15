import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, Task, TaskCompletion, LinkniCompletion
from handlers.button_helper import safe_edit
from keyboards.main import task_single_kb, task_done_kb, back_to_menu_kb

router = Router()
logger = logging.getLogger(__name__)

TASK_REWARD = 0.25


async def _show_next_task(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    """Find next uncompleted task and display it (one-at-a-time, interleaved Linkni:Bot)."""
    from services.linkni import get_linkni_task_url, linkni_has_sponsors

    user_id = db_user.user_id

    # Completed bot task IDs
    done_bot_ids = set((await session.execute(
        select(TaskCompletion.task_id).where(TaskCompletion.user_id == user_id)
    )).scalars().all())

    # Completed Linkni entry keys
    done_linkni_keys = set((await session.execute(
        select(LinkniCompletion.entry_key).where(LinkniCompletion.user_id == user_id)
    )).scalars().all())

    # Active bot tasks not yet completed
    all_tasks = (await session.execute(
        select(Task).where(Task.is_active == True).order_by(Task.created_at)
    )).scalars().all()
    pending_bot = [t for t in all_tasks if t.id not in done_bot_ids]

    # Linkni: show one synthetic task if LINKNI_CODE is set and sponsors are available
    linkni_url = get_linkni_task_url(user_id)
    linkni_available = bool(linkni_url) and await linkni_has_sponsors(user_id)
    pending_linkni = [{"url": linkni_url, "title": "Подписка на канал"}] if linkni_available else []

    # Interleave 1:1 — even total completed → Linkni first; odd → bot first
    total_done = len(done_bot_ids) + len(done_linkni_keys)
    if total_done % 2 == 0:
        order = [("linkni", pending_linkni), ("bot", pending_bot)]
    else:
        order = [("bot", pending_bot), ("linkni", pending_linkni)]

    next_type, next_task = None, None
    for t_type, pool in order:
        if pool:
            next_type, next_task = t_type, pool[0]
            break

    if next_type is None:
        await safe_edit(
            callback,
            "📋 <b>Задания</b>\n\nВсе задания выполнены! Заходи позже.",
            back_to_menu_kb(),
        )
        await callback.answer()
        return

    if next_type == "linkni":
        kb = task_single_kb("linkni", "0", next_task["url"])
        text = (
            f"📋 <b>Задание</b>\n\n"
            f"🔗 <b>{next_task['title']}</b>\n\n"
            f"Подпишись на канал и нажми «Проверить».\n\n"
            f"💰 Награда: <b>{TASK_REWARD} ⭐</b>"
        )
    else:
        task = next_task
        url = None
        if task.task_type == "subscribe" and task.channel_id:
            url = f"https://t.me/{task.channel_id.lstrip('@').lstrip('-100')}"
        elif task.task_type == "linkni" and task.channel_id:
            url = f"https://t.me/linknibot/app?startapp=x_{task.channel_id}_"
        kb = task_single_kb(task.task_type, str(task.id), url)
        extra = ""
        if task.task_type == "referrals" and task.target_value:
            extra = f"\n🎯 Нужно рефералов: <b>{task.target_value}</b> (у тебя: <b>{db_user.referrals_count}</b>)"
        text = (
            f"📋 <b>{task.title}</b>\n\n"
            f"{task.description}{extra}\n\n"
            f"💰 Награда: <b>{TASK_REWARD} ⭐</b>"
        )

    await safe_edit(callback, text, kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:tasks")
async def cb_tasks_menu(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    await _show_next_task(callback, session, db_user)


@router.callback_query(lambda c: c.data and c.data.startswith("task:linkni:"))
async def cb_verify_linkni(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    """Verify Linkni task by checking new subscription in API response."""
    from services.linkni import linkni_find_new_subscription

    done_linkni_keys = set((await session.execute(
        select(LinkniCompletion.entry_key).where(LinkniCompletion.user_id == db_user.user_id)
    )).scalars().all())

    found, key = await linkni_find_new_subscription(db_user.user_id, done_linkni_keys)
    if not found:
        await callback.answer(
            "❌ Ты ещё не подписался.\nПерейди по ссылке и нажми «Проверить».",
            show_alert=True,
        )
        return

    # Give reward
    session.add(LinkniCompletion(user_id=db_user.user_id, entry_key=key))
    db_user.stars_balance += TASK_REWARD
    await session.commit()

    await safe_edit(
        callback,
        f"✅ <b>+{TASK_REWARD} ⭐ получено!</b>\n\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        task_done_kb(),
    )
    await callback.answer(f"+{TASK_REWARD} ⭐")
    logger.info("Linkni task completed by user %s (key=%s)", db_user.user_id, key)


@router.callback_query(lambda c: c.data and c.data.startswith("task:bot:"))
async def cb_verify_bot(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot) -> None:
    """Verify a bot admin task."""
    try:
        task_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    task = await session.get(Task, task_id)
    if not task or not task.is_active:
        await callback.answer("Задание не найдено или деактивировано.", show_alert=True)
        return

    # Already done?
    already = (await session.execute(
        select(TaskCompletion).where(
            TaskCompletion.user_id == db_user.user_id,
            TaskCompletion.task_id == task_id,
        )
    )).scalar_one_or_none()
    if already:
        await callback.answer("Ты уже выполнил это задание!", show_alert=True)
        return

    # Verify based on type
    if task.task_type == "subscribe":
        if not task.channel_id:
            await callback.answer("Ошибка конфигурации задания.", show_alert=True)
            return
        try:
            member = await bot.get_chat_member(task.channel_id, db_user.user_id)
            if member.status in ("left", "kicked", "banned"):
                await callback.answer(
                    "❌ Вы не подписаны на канал.\nПодпишитесь и нажмите «Проверить».",
                    show_alert=True,
                )
                return
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("bot is not a member", "chat not found", "forbidden", "kicked")):
                task.is_active = False
                await session.commit()
                logger.warning("Task %s auto-deactivated: %s", task.id, e)
                await callback.answer(
                    "⚠️ Задание недоступно — бот был удалён из канала.",
                    show_alert=True,
                )
            else:
                await callback.answer("❌ Не удалось проверить подписку. Попробуйте позже.", show_alert=True)
            return

    elif task.task_type == "referrals":
        target = task.target_value or 0
        if db_user.referrals_count < target:
            await callback.answer(
                f"❌ Недостаточно рефералов.\nНужно: {target}, у тебя: {db_user.referrals_count}",
                show_alert=True,
            )
            return

    elif task.task_type == "linkni":
        if not task.channel_id:
            await callback.answer("Ошибка конфигурации задания.", show_alert=True)
            return
        from services.linkni import check_linkni_subscription_by_code
        done = await check_linkni_subscription_by_code(db_user.user_id, task.channel_id)
        if not done:
            await callback.answer(
                "❌ Вы не выполнили задание.\nПерейдите по ссылке и нажмите «Проверить».",
                show_alert=True,
            )
            return

    # All checks passed — give reward
    session.add(TaskCompletion(user_id=db_user.user_id, task_id=task_id))
    db_user.stars_balance += TASK_REWARD
    await session.commit()

    await safe_edit(
        callback,
        f"✅ <b>+{TASK_REWARD} ⭐ получено!</b>\n\n"
        f"<b>{task.title}</b>\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        task_done_kb(),
    )
    await callback.answer(f"+{TASK_REWARD} ⭐")
    logger.info("Bot task %s completed by user %s", task_id, db_user.user_id)
