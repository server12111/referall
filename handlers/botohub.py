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
from utils.emoji import pe

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
        db_user = await session.get(User, callback.from_user.id)
        if db_user and db_user.referral_reward_pending:
            await grant_referral_reward_if_pending(db_user, session, callback.bot)

        import asyncio as _asyncio
        _asyncio.create_task(show_gramads(callback.from_user.id))

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
    Unified check for the combined wall (all integrations + GramAds).
    Checks all integrations in parallel — single wall, no stages.
    """
    user_id = callback.from_user.id
    language_code = callback.from_user.language_code

    async def _flag(k, default):
        r = await session.get(BotSettings, k)
        return (r.value == "1") if r else default

    bh_on = await _flag("integration_botohub_enabled", True)
    fl_on = await _flag("integration_flyer_enabled", True)
    pf_on = await _flag("integration_piarflow_enabled", False)
    sg_on = await _flag("integration_subgram_enabled", False)
    tg_on = await _flag("integration_tgrass_enabled", False)

    pf_count_row = await session.get(BotSettings, "piarflow_count")
    pf_count = int(pf_count_row.value) if pf_count_row and pf_count_row.value else 5
    sg_count_row = await session.get(BotSettings, "subgram_count")
    sg_count = int(sg_count_row.value) if sg_count_row and sg_count_row.value else 5

    async def _skip_bh(): return {"completed": True, "skip": True, "tasks": []}
    async def _skip_pf(): return {"completed": True, "skip": True, "tasks": []}
    async def _skip_list(): return []
    async def _skip_bool(): return True

    from services.tgrass import check_tgrass_subscription, get_tgrass_wall_url

    # Check all in parallel — one wall
    tgrass_ok, sg_sponsors, pf_result, bh_result, flyer_tasks = await asyncio.gather(
        check_tgrass_subscription(user_id) if tg_on else _skip_bool(),
        get_subgram_sponsors(user_id, sg_count) if sg_on else _skip_list(),
        get_piarflow_tasks(user_id, pf_count) if pf_on else _skip_pf(),
        check_botohub(user_id) if bh_on else _skip_bh(),
        get_flyer_tasks(user_id, language_code) if fl_on else _skip_list(),
    )

    tgrass_url = get_tgrass_wall_url() if (tg_on and not tgrass_ok) else None
    pf_pending = not pf_result["completed"] and not pf_result["skip"] and bool(pf_result["tasks"])
    bh_pending = bh_on and not bh_result["completed"] and not bh_result["skip"] and bool(bh_result["tasks"])
    flyer_pending = fl_on and bool(flyer_tasks)
    sg_pending = sg_on and bool(sg_sponsors)

    if tgrass_url or sg_pending or pf_pending or bh_pending or flyer_pending:
        await callback.answer(
            "❌ Вы не подписались на все каналы.\nПодпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        wall_kb = build_combined_wall_kb(
            bh_result["tasks"] if bh_pending else [],
            flyer_tasks if flyer_pending else [],
            [],
            piarflow_tasks=pf_result["tasks"] if pf_pending else [],
            subgram_sponsors=sg_sponsors if sg_pending else [],
            tgrass_url=tgrass_url,
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=wall_kb)
        except Exception:
            pass
        logger.info(
            "CombinedWall: user %s still blocked (tg=%s, sg=%s, pf=%s, bh=%s, fl=%s)",
            user_id, bool(tgrass_url), sg_pending, pf_pending, bh_pending, flyer_pending,
        )
        return

    # All passed — referral reward + GramAds + main menu
    db_user = await session.get(User, user_id)
    if db_user and db_user.referral_reward_pending:
        await grant_referral_reward_if_pending(db_user, session, callback.bot)

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
    logger.info("CombinedWall: user %s passed all walls", user_id)
