import logging

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import config
from database.models import User, Task, TaskCompletion
from utils.emoji import pe
from handlers.button_helper import safe_edit
from keyboards.main import task_single_kb, task_done_kb, back_to_menu_kb

router = Router()
logger = logging.getLogger(__name__)

TASK_REWARD = 0.25
USER_TASK_COMMISSION = 0.15  # 15% platform fee; creator pays upfront
USER_TASK_CREATOR_RATE = 1.0 - USER_TASK_COMMISSION  # 85% to completer
USER_TASK_MIN_REWARD = 1.0
USER_TASK_MAX_REWARD = 100.0


class UserTaskCreateStates(StatesGroup):
    channel = State()
    reward = State()
    confirm = State()


async def _show_next_task(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext | None = None,
) -> None:
    user_id = db_user.user_id

    done_bot_ids = set((await session.execute(
        select(TaskCompletion.task_id).where(TaskCompletion.user_id == user_id)
    )).scalars().all())

    fsm_data = ((await state.get_data()) or {}) if state else {}
    skipped_bot = set(fsm_data.get("skipped_bot", []))

    all_tasks = (await session.execute(
        select(Task).where(Task.is_active == True, Task.is_approved == True).order_by(Task.created_at)
    )).scalars().all()
    pending_bot = [t for t in all_tasks if t.id not in done_bot_ids and t.id not in skipped_bot]

    if pending_bot:
        task = pending_bot[0]
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
        display_reward = (
            round(task.reward * task.creator_reward_rate, 2)
            if task.creator_id and task.creator_reward_rate > 0
            else TASK_REWARD
        )
        text = pe(
            f"📋 <b>{task.title}</b>\n\n"
            f"{task.description}{extra}\n\n"
            f"💰 Награда: <b>{display_reward} ⭐</b>"
        )
        await safe_edit(callback, text, kb)
        await callback.answer()
        return

    create_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать своё задание", callback_data="tasks:create", style="primary", icon_custom_emoji_id="5435970940670320222")],
        [InlineKeyboardButton(text="Главное меню", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533")],
    ])
    await safe_edit(
        callback,
        pe("📋 <b>Задания</b>\n\nВсе задания выполнены! Заходи позже.\n\n💡 Можешь создать собственное задание за звёзды!"),
        create_kb,
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:tasks")
async def cb_tasks_menu(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    await _show_next_task(callback, session, db_user, state)


@router.callback_query(lambda c: c.data == "task:skip")
async def cb_task_skip(callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext) -> None:
    fsm_data = await state.get_data()
    task_type = fsm_data.get("current_task_type")
    task_id = fsm_data.get("current_task_id")

    if task_type == "bot" and task_id:
        skipped = set(fsm_data.get("skipped_bot", []))
        skipped.add(int(task_id))
        await state.update_data(skipped_bot=list(skipped))

    await callback.answer("⏭ Пропущено")
    await _show_next_task(callback, session, db_user, state)


@router.callback_query(lambda c: c.data and c.data.startswith("task:bot:"))
async def cb_verify_bot(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot) -> None:
    try:
        task_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    task = await session.get(Task, task_id)
    if not task or not task.is_active:
        await callback.answer("Задание не найдено или деактивировано.", show_alert=True)
        return

    already = (await session.execute(
        select(TaskCompletion).where(
            TaskCompletion.user_id == db_user.user_id,
            TaskCompletion.task_id == task_id,
        )
    )).scalar_one_or_none()
    if already:
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

    # Determine reward (user-created tasks use their own reward amount)
    if task.creator_id and task.creator_reward_rate > 0:
        completer_reward = round(task.reward * task.creator_reward_rate, 2)
    else:
        completer_reward = TASK_REWARD

    session.add(TaskCompletion(user_id=db_user.user_id, task_id=task_id))
    db_user.stars_balance += completer_reward
    await session.commit()

    await safe_edit(
        callback,
        pe(
            f"✅ <b>+{completer_reward} ⭐ получено!</b>\n\n"
            f"<b>{task.title}</b>\n"
            f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
        ),
        task_done_kb(),
    )
    await callback.answer(f"+{completer_reward} ⭐")
    logger.info("Bot task %s completed by user %s (reward %.2f)", task_id, db_user.user_id, completer_reward)


# ── User-created task flow ────────────────────────────────────────────────────

def _user_task_create_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать задание", callback_data="tasks:create", style="primary", icon_custom_emoji_id="5435970940670320222")],
        [InlineKeyboardButton(text="Назад", callback_data="menu:main", style="danger", icon_custom_emoji_id="5318991467639756533")],
    ])


def _user_task_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и оплатить", callback_data="tasks:create:confirm", style="success", icon_custom_emoji_id="5462919317832082236")],
        [InlineKeyboardButton(text="Отмена", callback_data="tasks:create:cancel", style="danger", icon_custom_emoji_id="5318991467639756533")],
    ])


@router.callback_query(lambda c: c.data == "tasks:create")
async def cb_task_create_start(callback: CallbackQuery, state: FSMContext, db_user: User) -> None:
    await state.set_state(UserTaskCreateStates.channel)
    await callback.message.answer(
        pe(
            "📝 <b>Создать задание</b>\n\n"
            "Отправь ссылку на Telegram-канал, на который должны подписаться пользователи.\n\n"
            "Пример: <code>@mychannel</code> или <code>https://t.me/mychannel</code>"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="tasks:create:cancel", style="danger", icon_custom_emoji_id="5318991467639756533")]
        ]),
    )
    await callback.answer()


@router.message(UserTaskCreateStates.channel)
async def msg_task_create_channel(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    # Normalize: accept @username or t.me/username or https://t.me/username
    if raw.startswith("https://t.me/"):
        channel_id = "@" + raw[len("https://t.me/"):]
    elif raw.startswith("t.me/"):
        channel_id = "@" + raw[len("t.me/"):]
    elif raw.startswith("@"):
        channel_id = raw
    else:
        channel_id = "@" + raw

    await state.update_data(channel_id=channel_id)
    await state.set_state(UserTaskCreateStates.reward)
    await message.answer(
        pe(
            f"✅ Канал: <code>{channel_id}</code>\n\n"
            f"Укажи награду за выполнение задания (в ⭐).\n"
            f"Мин: <b>{USER_TASK_MIN_REWARD:.0f}</b>, Макс: <b>{USER_TASK_MAX_REWARD:.0f}</b>\n\n"
            f"💡 С тебя будет списано reward × 1.15 (15% комиссия платформы)."
        ),
    )


@router.message(UserTaskCreateStates.reward)
async def msg_task_create_reward(message: Message, state: FSMContext, db_user: User) -> None:
    try:
        reward = float((message.text or "").strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введи число, например: <b>5</b>")
        return

    if reward < USER_TASK_MIN_REWARD or reward > USER_TASK_MAX_REWARD:
        await message.answer(
            pe(f"❌ Награда должна быть от <b>{USER_TASK_MIN_REWARD:.0f}</b> до <b>{USER_TASK_MAX_REWARD:.0f}</b> ⭐")
        )
        return

    total_cost = round(reward * (1 + USER_TASK_COMMISSION), 2)
    if db_user.stars_balance < total_cost:
        await message.answer(
            pe(
                f"❌ Недостаточно звёзд.\n"
                f"Нужно: <b>{total_cost:.2f} ⭐</b> (награда {reward:.0f} + комиссия {USER_TASK_COMMISSION*100:.0f}%)\n"
                f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>"
            )
        )
        return

    fsm_data = await state.get_data()
    channel_id = fsm_data["channel_id"]
    await state.update_data(reward=reward, total_cost=total_cost)
    await state.set_state(UserTaskCreateStates.confirm)

    await message.answer(
        pe(
            f"📋 <b>Подтверждение задания</b>\n\n"
            f"Канал: <code>{channel_id}</code>\n"
            f"Награда за выполнение: <b>{reward:.0f} ⭐</b>\n"
            f"Из них тебе (85%): остаётся у тебя\n"
            f"Комиссия платформы (15%): <b>{total_cost - reward:.2f} ⭐</b>\n"
            f"Итого к списанию: <b>{total_cost:.2f} ⭐</b>\n\n"
            f"Задание будет активировано после проверки администратором."
        ),
        reply_markup=_user_task_confirm_kb(),
    )


@router.callback_query(lambda c: c.data == "tasks:create:confirm")
async def cb_task_create_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    fsm_data = await state.get_data()
    channel_id = fsm_data.get("channel_id")
    reward = fsm_data.get("reward")
    total_cost = fsm_data.get("total_cost")

    if not channel_id or not reward or not total_cost:
        await callback.answer("Ошибка данных. Начни заново.", show_alert=True)
        await state.clear()
        return

    if db_user.stars_balance < total_cost:
        await callback.answer(
            f"❌ Недостаточно звёзд ({db_user.stars_balance:.2f} < {total_cost:.2f})",
            show_alert=True,
        )
        await state.clear()
        return

    # Deduct cost and create task
    db_user.stars_balance -= total_cost
    task = Task(
        task_type="subscribe",
        title=f"Подписаться на {channel_id}",
        description=f"Подпишись на канал {channel_id} и получи награду!",
        reward=reward,
        channel_id=channel_id,
        is_active=True,
        is_approved=False,
        creator_id=db_user.user_id,
        creator_reward_rate=USER_TASK_CREATOR_RATE,
    )
    session.add(task)
    await session.flush()
    await session.commit()
    await state.clear()

    # Notify admins
    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                pe(
                    f"📋 <b>Новое задание на проверку #{task.id}</b>\n\n"
                    f"👤 @{db_user.username or db_user.first_name} | ID {db_user.user_id}\n"
                    f"🔗 Канал: <code>{channel_id}</code>\n"
                    f"💰 Награда: <b>{reward:.0f} ⭐</b>"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin:task_approve:{task.id}", style="success", icon_custom_emoji_id="5462919317832082236"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:task_reject:{task.id}", style="danger", icon_custom_emoji_id="5210952531676504517"),
                    ]
                ]),
            )
        except Exception:
            pass

    await callback.message.edit_text(
        pe(
            f"✅ <b>Задание #{task.id} отправлено на проверку!</b>\n\n"
            f"Списано: <b>{total_cost:.2f} ⭐</b>\n"
            f"Баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n\n"
            f"Задание будет активировано после одобрения администратором."
        ),
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer("✅ Отправлено!")


@router.callback_query(lambda c: c.data == "tasks:create:cancel")
async def cb_task_create_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Создание задания отменено.", reply_markup=back_to_menu_kb())
    await callback.answer()
