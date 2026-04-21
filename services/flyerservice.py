import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp

from config import config

logger = logging.getLogger(__name__)

FLYERSERVICE_API = "https://api.flyerservice.io"
TASK_REWARD = 0.25
POLL_INTERVAL = 300  # seconds between polling cycles


async def get_completed_tasks(user_id: int) -> list[dict]:
    """
    Returns list of completed tasks for the user from FlyerService.
    Returns [] if key not set, on error, or no completions.
    """
    if not config.FLYERSERVICE_KEY:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FLYERSERVICE_API}/get_completed_tasks",
                json={"key": config.FLYERSERVICE_KEY, "user_id": user_id},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if isinstance(data, dict):
                    if data.get("error"):
                        return []
                    return data.get("result") or []
                if isinstance(data, list):
                    return data
                return []
    except Exception as exc:
        logger.warning("FlyerService get_completed_tasks error for user %s: %s", user_id, exc)
        return []


async def flyerservice_poll_loop() -> None:
    """
    Background polling loop: every POLL_INTERVAL seconds checks recent active
    users for new FlyerService completions and credits them.
    """
    if not config.FLYERSERVICE_KEY:
        logger.info("FlyerService polling disabled (no key)")
        return

    logger.info("FlyerService polling started (interval=%ds)", POLL_INTERVAL)

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            await _poll_cycle()
        except Exception as exc:
            logger.error("FlyerService poll cycle error: %s", exc)


async def _poll_cycle() -> None:
    from sqlalchemy import select
    from database.engine import SessionFactory
    from database.models import User, FlyerServiceCompletion

    cutoff = datetime.utcnow() - timedelta(hours=48)

    async with SessionFactory() as session:
        # Only check users active in last 48h
        users = (await session.execute(
            select(User.user_id).where(User.last_seen_at >= cutoff)
        )).scalars().all()

    if not users:
        return

    logger.debug("FlyerService poll: checking %d active users", len(users))
    credited = 0

    for user_id in users:
        try:
            completions = await get_completed_tasks(user_id)
            if not completions:
                continue

            async with SessionFactory() as session:
                db_user = await session.get(User, user_id)
                if not db_user:
                    continue

                for item in completions:
                    sig = str(item.get("signature") or item.get("id") or "")
                    if not sig:
                        continue

                    already = (await session.execute(
                        select(FlyerServiceCompletion).where(
                            FlyerServiceCompletion.user_id == user_id,
                            FlyerServiceCompletion.signature == sig,
                        )
                    )).scalar_one_or_none()

                    if not already:
                        session.add(FlyerServiceCompletion(user_id=user_id, signature=sig))
                        db_user.stars_balance += TASK_REWARD
                        credited += 1

                if credited:
                    await session.commit()

        except Exception as exc:
            logger.warning("FlyerService poll error for user %s: %s", user_id, exc)

    if credited:
        logger.info("FlyerService poll: credited %d new completions", credited)
