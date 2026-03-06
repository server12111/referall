from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

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

    import json
    rt_row = await session.get(BotSettings, "reward_type")
    reward_type = rt_row.value if rt_row else "per_sponsor"

    if reward_type == "fixed":
        rr_row = await session.get(BotSettings, "referral_reward")
        reward = float(rr_row.value) if rr_row and rr_row.value else 0.0
    else:
        mode_row = await session.get(BotSettings, "referral_mode")
        mode = mode_row.value if mode_row else "botohub_flyer"
        sps_row = await session.get(BotSettings, "stars_per_sponsor")
        stars_per_sponsor = float(sps_row.value) if sps_row and sps_row.value else 0.45

        if mode == "sponsors":
            sponsors_row = await session.get(BotSettings, "sponsor_channels")
            sponsors = json.loads(sponsors_row.value) if sponsors_row and sponsors_row.value and sponsors_row.value.strip() else []
            total_sponsors = len(sponsors)
        else:
            from services.flyer import get_channels_count
            botohub_row = await session.get(BotSettings, "botohub_sponsors_count")
            botohub_count = int(botohub_row.value) if botohub_row else 0
            flyer_count = await get_channels_count()
            total_sponsors = botohub_count + flyer_count

        reward = round(total_sponsors * stars_per_sponsor, 2)

    referrer.referrals_count += 1
    user.referral_reward_pending = False

    if referrer.referrals_count >= 3:
        referrer.stars_balance += reward
        await session.commit()

        try:
            await bot.send_message(
                user.referrer_id,
                f"🎉 Вам начислено <b>{reward} ⭐</b> за нового реферала!",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await session.commit()
