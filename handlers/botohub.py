import asyncio
import json
import logging

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, BotSettings
from handlers.button_helper import answer_with_content
from keyboards.botohub import build_botohub_wall_kb, build_combined_wall_kb
from keyboards.main import main_menu_kb
from services.referral import grant_referral_reward_if_pending
from services.flyer import check_subscription, get_flyer_tasks
from services.piarflow import get_piarflow_tasks
from services.subgram import get_subgram_sponsors, check_subgram_subscriptions
from services.gramads import show_gramads
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


@router.callback_query(lambda c: c.data == "wall:check")
async def cb_combined_wall_check(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Unified check for the combined wall (all 5 integrations + GramAds).
    Opens main menu only when ALL integrations confirm subscription.
    """
    user_id = callback.from_user.id
    language_code = callback.from_user.language_code

    # Read enabled flags and counts sequentially (same session)
    async def _flag(k, default):
        r = await session.get(BotSettings, k)
        return (r.value == "1") if r else default

    bh_on = await _flag("integration_botohub_enabled", True)
    fl_on = await _flag("integration_flyer_enabled", True)
    pf_on = await _flag("integration_piarflow_enabled", False)
    sg_on = await _flag("integration_subgram_enabled", False)

    pf_count_row = await session.get(BotSettings, "piarflow_count")
    pf_count = int(pf_count_row.value) if pf_count_row and pf_count_row.value else 5
    sg_count_row = await session.get(BotSettings, "subgram_count")
    sg_count = int(sg_count_row.value) if sg_count_row and sg_count_row.value else 5

    async def _skip_bh(): return {"completed": True, "skip": True, "tasks": []}
    async def _skip_bool(): return True

    # Check only enabled integrations in parallel
    bh_result, flyer_done, pf_result = await asyncio.gather(
        check_botohub(user_id) if bh_on else _skip_bh(),
        check_subscription(user_id, language_code) if fl_on else _skip_bool(),
        get_piarflow_tasks(user_id, pf_count) if pf_on else _skip_bh(),
    )

    bh_done = bh_result["completed"] or bh_result["skip"]
    pf_done = pf_result["completed"] or pf_result["skip"]

    if bh_done and flyer_done and pf_done:
        # All passed — referral reward + GramAds + main menu
        db_user = await session.get(User, user_id)
        if db_user and db_user.referral_reward_pending:
            await grant_referral_reward_if_pending(db_user, session, callback.bot)

        # Show GramAds ad (non-blocking, silent on error)
        asyncio.create_task(show_gramads(user_id))

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
        logger.info("CombinedWall: user %s passed all subscription walls", user_id)

    else:
        await callback.answer(
            "❌ Вы не подписались на все каналы.\nПодпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        # Rebuild keyboard with only remaining channels
        flyer_tasks = await get_flyer_tasks(user_id, language_code) if fl_on and not flyer_done else []
        sg_sponsors = await get_subgram_sponsors(user_id, sg_count) if sg_on else []

        new_kb = build_combined_wall_kb(
            bh_result["tasks"] if bh_on and not bh_done else [],
            flyer_tasks,
            [],
            piarflow_tasks=pf_result["tasks"] if pf_on and not pf_done else [],
            subgram_sponsors=sg_sponsors,
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=new_kb)
        except Exception:
            pass
        logger.info(
            "CombinedWall: user %s not fully subscribed (bh=%s, flyer=%s, pf=%s)",
            user_id, bh_done, flyer_done, pf_done,
        )
