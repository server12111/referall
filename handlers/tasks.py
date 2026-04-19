import logging

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, Task, TaskCompletion, LinkniCompletion, FlyerServiceCompletion
from handlers.button_helper import safe_edit
from keyboards.main import task_single_kb, task_done_kb, back_to_menu_kb

router = Router()
logger = logging.getLogger(__name__)

TASK_REWARD = 0.25


async def _show_next_task(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext | None = None,
) -> None:
    """Find next uncompleted task and display it (one-at-a-time, interleaved Linkni:Bot:FlyerService)."""
    from services.linkni import get_linkni_task_url, linkni_has_sponsors
    from services.flyerservice import get_flyerservice_tasks

    user_id = db_user.user_id

    # Completed bot task IDs
    done_bot_ids = set((await session.execute(
        select(TaskCompletion.task_id).where(TaskCompletion.user_id == user_id)
    )).scalars().all())

    # Completed Linkni entry keys
    done_linkni_keys = set((await session.execute(
        select(LinkniCompletion.entry_key).where(LinkniCompletion.user_id == user_id)
    )).scalars().all())

    # Completed FlyerService signatures
    done_fs_sigs = set((await session.execute(
        select(FlyerServiceCompletion.signature).where(FlyerServiceCompletion.user_id == user_id)
    )).scalars().all())

    # Skipped this session (stored in FSM)
    fsm_data = (await state.get_data()) if state else {}
    skipped_bot = set(fsm_data.get("skipped_bot", []))
    skipped_fs = set(fsm_data.get("skipped_fs", []))
    linkni_skipped = fsm_data.get("linkni_skipped", False)

    # Active bot tasks not yet completed or skipped
    all_tasks = (await session.execute(
        select(Task).where(Task.is_active == True).order_by(Task.created_at)
    )).scalars().all()
    pending_bot = [t for t in all_tasks if t.id not in done_bot_ids and t.id not in skipped_bot]

    # Linkni: one synthetic task if available and not skipped this session
    linkni_url = get_linkni_task_url(user_id)
    linkni_available = bool(linkni_url) and not linkni_skipped and await linkni_has_sponsors(user_id)
    pending_linkni = [{"url": linkni_url, "title": "Подписка на канал"}] if linkni_available else []

    # FlyerService tasks not yet locally completed or skipped
    fs_tasks_raw = await get_flyerservice_tasks(user_id)
    pending_fs = [t for t in fs_tasks_raw if t.get("signature") not in done_fs_sigs and t.get("signature") not in skipped_fs]

    # Interleave round-robin across three pools
    total_done = len(done_bot_ids) + len(done_linkni_keys) + len(done_fs_sigs)
    pools_order = [
        ("flyerservice", pending_fs),
        ("linkni", pending_linkni),
        ("bot", pending_bot),
    ]
    # Rotate based on completed count so pools alternate
    idx = total_done % len(pools_order)
    ordered = pools_order[idx:] + pools_order[:idx]

    next_type, next_task = None, None
    for t_type, pool in ordered:
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

    if next_type == "flyerservice":
        sig = next_task.get("signature", "")
        links = next_task.get("links") or []
        url = links[0] if links else None
        if state:
            await state.update_data(fs_signature=sig, current_task_type="flyerservice", current_task_id=sig)
        kb = task_single_kb("flyerservice", sig, url)
        text = (
            f"📋 <b>Задание</b>\n\n"
            f"🔗 <b>{next_task.get('name', 'Подписка на канал')}</b>\n\n"
            f"Выполни задание и нажми «Проверить».\n\n"
            f"💰 Награда: <b>{TASK_REWARD} ⭐</b>"
        )
    elif next_type == "linkni":
        if state:
            await state.update_data(current_task_type="linkni", current_task_id="linkni")
        kb = task_single_kb("linkni", "0", next_task["url"])
        text = (
            f"📋 <b>Задание</b>\n\n"
            f"🔗 <b>{next_task['title']}</b>\n\n"
            f"Подпишись на канал и нажми «Проверить».\n\n"
            f"💰 Награда: <b>{TASK_REWARD} ⭐</b>"
        )
    else:
        task = next_task
        if state:
            await state.update_data(current_task_type="bot", current_task_id=str(task.id))
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
async def cb_tasks_menu(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    await _show_next_task(callback, session, db_user, state)


@router.callback_query(lambda c: c.data == "task:skip")
async def cb_task_skip(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    """Skip current task for this session and show next one."""
    fsm_data = await state.get_data()
    task_type = fsm_data.get("current_task_type")
    task_id = fsm_data.get("current_task_id")

    if task_type == "bot" and task_id:
        skipped = set(fsm_data.get("skipped_bot", []))
        skipped.add(int(task_id))
        await state.update_data(skipped_bot=list(skipped))
    elif task_type == "flyerservice" and task_id:
        skipped = set(fsm_data.get("skipped_fs", []))
        skipped.add(task_id)
        await state.update_data(skipped_fs=list(skipped))
    elif task_type == "linkni":
        await state.update_data(linkni_skipped=True)

    await callback.answer("⏭ Пропущено")
    await _show_next_task(callback, session, db_user, state)


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


@router.callback_query(lambda c: c.data == "task:flyerservice:check")
async def cb_verify_flyerservice(
    callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    """Verify FlyerService task: check if signature is no longer in pending list."""
    from services.flyerservice import is_task_done

    data = await state.get_data()
    signature = data.get("fs_signature")
    if not signature:
        await callback.answer("❌ Задание не найдено. Попробуй открыть задания заново.", show_alert=True)
        return

    done = await is_task_done(db_user.user_id, signature, callback.from_user.language_code)
    if not done:
        await callback.answer(
            "❌ Задание ещё не выполнено.\nВыполни его и нажми «Проверить».",
            show_alert=True,
        )
        return

    # Already saved?
    already = (await session.execute(
        select(FlyerServiceCompletion).where(
            FlyerServiceCompletion.user_id == db_user.user_id,
            FlyerServiceCompletion.signature == signature,
        )
    )).scalar_one_or_none()
    if already:
        await callback.answer("Ты уже выполнил это задание!", show_alert=True)
        return

    session.add(FlyerServiceCompletion(user_id=db_user.user_id, signature=signature))
    db_user.stars_balance += TASK_REWARD
    await session.commit()
    await state.update_data(fs_signature=None)

    await safe_edit(
        callback,
        f"✅ <b>+{TASK_REWARD} ⭐ получено!</b>\n\n"
        f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        task_done_kb(),
    )
    await callback.answer(f"+{TASK_REWARD} ⭐")
    logger.info("FlyerService task completed by user %s (sig=%s)", db_user.user_id, signature)
