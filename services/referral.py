from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import BotSettings, User


async def grant_referral_reward_if_pending(
    user: User, session: AsyncSession, bot: Bot
) -> None:
    """
    Give the referral reward to the referrer only if it is still pending.

    Called after the new user passes the subscription wall (BotoHub or standard sponsors).
    Sets referral_reward_pending=False atomically to prevent double-reward.
    """
    if not user.referral_reward_pending or not user.referrer_id:
        return

    referrer = await session.get(User, user.referrer_id)
    if not referrer:
        user.referral_reward_pending = False
        await session.commit()
        return

    rr_row = await session.get(BotSettings, "referral_reward")
    reward = float(rr_row.value) if rr_row else config.REFERRAL_REWARD

    referrer.stars_balance += reward
    referrer.referrals_count += 1
    user.referral_reward_pending = False
    await session.commit()

    try:
        await bot.send_message(
            user.referrer_id,
            f"🎉 Вам начислено <b>{reward} ⭐</b> за нового реферала!",
            parse_mode="HTML",
        )
    except Exception:
        pass
