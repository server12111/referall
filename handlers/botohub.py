import logging

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from handlers.button_helper import answer_with_content
from keyboards.botohub import build_botohub_wall_kb
from keyboards.main import main_menu_kb
from services.referral import grant_referral_reward_if_pending
from utils.botohub_api import check_botohub

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data == "botohub:check")
async def cb_botohub_check(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Called when the user presses "✅ Я подписался" on the BotoHub wall.

    Re-checks the subscription via BotoHub API.
    If completed — opens the main menu and gives referral reward if pending.
    If not — shows the wall again with an error alert.
    """
    result = await check_botohub(callback.from_user.id)

    if result["completed"] or result["skip"]:
        # Subscription confirmed — give referral reward if still pending
        db_user = await session.get(User, callback.from_user.id)
        if db_user and db_user.referral_reward_pending:
            await grant_referral_reward_if_pending(db_user, session, callback.bot)

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
        await callback.answer("✅ Подписка подтверждена!")
        logger.info("BotoHub: user %s passed subscription wall", callback.from_user.id)

    else:
        # Not all channels subscribed — show alert and refresh the wall
        await callback.answer(
            "❌ Вы не подписались на все каналы.\nПодпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        if result["tasks"]:
            wall_kb = build_botohub_wall_kb(result["tasks"])
            try:
                await callback.message.edit_reply_markup(reply_markup=wall_kb)
            except Exception:
                pass
        logger.info(
            "BotoHub: user %s pressed check but is not subscribed yet", callback.from_user.id
        )
