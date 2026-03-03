import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, Task, TaskCompletion
from handlers.button_helper import answer_with_content, safe_edit
from keyboards.main import tasks_list_kb, task_detail_kb, back_to_tasks_kb, back_to_menu_kb

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "menu:tasks")
async def cb_tasks_menu(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    tasks = (await session.execute(
        select(Task).where(Task.is_active == True).order_by(Task.created_at)
    )).scalars().all()

    completed_ids = set((await session.execute(
        select(TaskCompletion.task_id).where(TaskCompletion.user_id == db_user.user_id)
    )).scalars().all())

    if not tasks:
        await answer_with_content(
            callback, session, "menu:tasks",
            "📋 <b>Задания</b>\n\nПока нет активных заданий.",
            back_to_menu_kb(),
        )
        await callback.answer()
        return

    await answer_with_content(
        callback, session, "menu:tasks",
        "📋 <b>Задания</b>\n\nВыполняй задания и получай звёзды:",
        tasks_list_kb(tasks, completed_ids),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("task:view:"))
async def cb_task_view(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    task_id = int(callback.data.split(":")[2])
    task = await session.get(Task, task_id)
    if not task or not task.is_active:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    completed = (await session.execute(
        select(TaskCompletion).where(
            TaskCompletion.user_id == db_user.user_id,
            TaskCompletion.task_id == task_id,
        )
    )).scalar_one_or_none() is not None

    type_label = {
        "subscribe": "📢 Подписка на канал",
        "referrals": "👥 Рефералы",
    }.get(task.task_type, task.task_type)
    status = "✅ Выполнено" if completed else "⏳ Не выполнено"

    extra = ""
    if task.task_type == "referrals" and task.target_value:
        extra = f"\n🎯 Нужно рефералов: <b>{task.target_value}</b>\nТвоих рефералов: <b>{db_user.referrals_count}</b>"

    await safe_edit(
        callback,
        f"📌 <b>{task.title}</b>\n\n"
        f"{task.description}\n\n"
        f"💰 Награда: <b>{task.reward} ⭐</b>\n"
        f"📂 Тип: {type_label}\n"
        f"Статус: {status}"
        f"{extra}",
        task_detail_kb(task.id, task.task_type, task.channel_id, completed),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("task:check:"))
async def cb_task_check(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot) -> None:
    task_id = int(callback.data.split(":")[2])
    task = await session.get(Task, task_id)
    if not task or not task.is_active:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    already_done = (await session.execute(
        select(TaskCompletion).where(
            TaskCompletion.user_id == db_user.user_id,
            TaskCompletion.task_id == task_id,
        )
    )).scalar_one_or_none()
    if already_done:
        await callback.answer("Ты уже выполнил это задание!", show_alert=True)
        return

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
            # Auto-deactivate if bot was removed from channel or channel was deleted
            if any(k in err for k in ("bot is not a member", "chat not found", "forbidden", "kicked")):
                task.is_active = False
                await session.commit()
                logger.warning("Task %s auto-deactivated (bot lost channel access): %s", task.id, e)
                await callback.answer(
                    "⚠️ Задание недоступно — бот был удалён из канала. Задание деактивировано.",
                    show_alert=True,
                )
            else:
                logger.error("Task %s subscription check error: %s", task.id, e)
                await callback.answer(
                    "❌ Не удалось проверить подписку. Попробуйте позже.",
                    show_alert=True,
                )
            return

    elif task.task_type == "referrals":
        target = task.target_value or 0
        if db_user.referrals_count < target:
            await callback.answer(
                f"❌ Недостаточно рефералов.\n"
                f"Нужно: {target}, у тебя: {db_user.referrals_count}",
                show_alert=True,
            )
            return

    session.add(TaskCompletion(user_id=db_user.user_id, task_id=task_id))
    db_user.stars_balance += task.reward
    await session.commit()

    await safe_edit(
        callback,
        f"✅ Вы получили <b>{task.reward} ⭐</b> за выполнение задания!\n\n"
        f"<b>{task.title}</b>\n"
        f"Текущий баланс: <b>{db_user.stars_balance:.2f} ⭐</b>",
        back_to_tasks_kb(),
    )
    await callback.answer(f"+{task.reward} ⭐")
