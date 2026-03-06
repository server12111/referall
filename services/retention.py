import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select

logger = logging.getLogger(__name__)

_DEFAULT_MESSAGE = (
    "👋 Привет! Ты давно не заходил в бот.\n"
    "Держи бонус за возвращение — <b>{bonus} ⭐</b>!"
)


async def retention_loop(bot: Bot) -> None:
    """Background task: check inactive users every hour."""
    await asyncio.sleep(60)  # wait 1 min after startup
    while True:
        try:
            await _check_and_notify(bot)
        except Exception as exc:
            logger.error("Retention loop error: %s", exc)
        await asyncio.sleep(3600)


async def _check_and_notify(bot: Bot) -> None:
    from database.engine import SessionFactory
    from database.models import User, BotSettings

    async with SessionFactory() as session:
        enabled_row = await session.get(BotSettings, "retention_enabled")
        if not enabled_row or enabled_row.value != "1":
            return

        days_row = await session.get(BotSettings, "retention_days")
        bonus_row = await session.get(BotSettings, "retention_bonus")
        msg_row = await session.get(BotSettings, "retention_message")

        days = int(days_row.value) if days_row else 3
        bonus = float(bonus_row.value) if bonus_row else 1.0
        text = msg_row.value if msg_row else _DEFAULT_MESSAGE

        threshold = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(User).where(
                User.last_seen_at.isnot(None),
                User.last_seen_at < threshold,
                (User.last_notified_at.is_(None)) | (User.last_notified_at < threshold),
            )
        )
        users = result.scalars().all()

        sent = 0
        for user in users:
            try:
                await bot.send_message(
                    user.user_id,
                    text.replace("{bonus}", str(bonus)),
                    parse_mode="HTML",
                )
                if bonus > 0:
                    user.stars_balance += bonus
                sent += 1
            except Exception as exc:
                logger.warning("Retention: cannot notify user %s: %s", user.user_id, exc)
            finally:
                user.last_notified_at = datetime.utcnow()

        if users:
            await session.commit()
            logger.info("Retention: notified %d/%d users", sent, len(users))
