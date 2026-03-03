from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from database.models import User
from handlers.button_helper import answer_with_content, send_with_content
from keyboards.botohub import build_botohub_wall_kb
from keyboards.main import main_menu_kb
from config import config
from services.referral import grant_referral_reward_if_pending
from utils.botohub_api import check_botohub

router = Router()


async def _register_user(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    first_name: str,
    referrer_id: int | None,
) -> tuple[User, bool]:
    """Returns (user, is_new). Referral reward is NOT given here — it is
    granted only after the new user passes the subscription wall."""
    db_user = await session.get(User, user_id)
    if db_user is not None:
        db_user.username = username
        db_user.first_name = first_name
        await session.commit()
        return db_user, False

    # New user — assign referrer only now
    valid_referrer = None
    if referrer_id and referrer_id != user_id:
        referrer = await session.get(User, referrer_id)
        if referrer:
            valid_referrer = referrer_id

    db_user = User(
        user_id=user_id,
        username=username,
        first_name=first_name,
        referrer_id=valid_referrer,
        referral_reward_pending=bool(valid_referrer),
    )
    session.add(db_user)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        db_user = await session.get(User, user_id)
        return db_user, False

    return db_user, True


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    referrer_id = None
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
        except ValueError:
            pass

    user, is_new = await _register_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        referrer_id,
    )

    if is_new and user.referrer_id:
        await message.answer("👋 Добро пожаловать! Ты перешёл по реферальной ссылке.")

    # ── BotoHub subscription wall ──
    if message.from_user.id not in config.ADMIN_IDS:
        result = await check_botohub(message.from_user.id)
        if not result["completed"] and not result["skip"]:
            await message.answer(
                "📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>",
                reply_markup=build_botohub_wall_kb(result["tasks"]),
            )
            return

        # ── Flyer subscription wall (after BotoHub passes) ──
        from services.flyer import check_subscription
        subscribed = await check_subscription(
            user_id=message.from_user.id,
            language_code=message.from_user.language_code,
        )
        if not subscribed:
            return  # Flyer sends the wall automatically

    # User passed both subscription walls — give referral reward if still pending
    await grant_referral_reward_if_pending(user, session, message.bot)

    default_text = (
        "👋 <b>Добро пожаловать в SrvNkStars!</b>\n\n"
        "🌟 Зарабатывай Telegram Stars прямо здесь:\n\n"
        "• ⭐ <b>Рефералы</b> — приглашай друзей и получай звёзды за каждого\n"
        "• 📋 <b>Задания</b> — подписывайся на каналы и выполняй задачи\n"
        "• 🎮 <b>Игры</b> — испытай удачу в мини-играх\n"
        "• 🎁 <b>Бонус</b> — бесплатные звёзды каждые 24 часа\n"
        "• 💰 <b>Вывод</b> — выводи накопленное на свой Telegram\n\n"
        "Выбери раздел ниже 👇"
    )
    await send_with_content(message, session, "menu:main", default_text, main_menu_kb())


@router.callback_query(lambda c: c.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    default_text = (
        "👋 <b>Главное меню</b>\n\n"
        "🌟 Зарабатывай Telegram Stars прямо здесь:\n\n"
        "• ⭐ <b>Рефералы</b> — приглашай друзей и получай звёзды за каждого\n"
        "• 📋 <b>Задания</b> — подписывайся на каналы и выполняй задачи\n"
        "• 🎮 <b>Игры</b> — испытай удачу в мини-играх\n"
        "• 🎁 <b>Бонус</b> — бесплатные звёзды каждые 24 часа\n"
        "• 💰 <b>Вывод</b> — выводи накопленное на свой Telegram\n\n"
        "Выбери раздел ниже 👇"
    )
    await answer_with_content(callback, session, "menu:main", default_text, main_menu_kb())
    await callback.answer()
