import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

GRAMADS_URL = "https://api.gramads.net/ad/SendPost"


async def show_gramads(user_id: int) -> None:
    """
    Send a GramAds advertisement to the user.
    Called after the user passes all subscription walls.
    Silent on any error — ads are non-critical.
    """
    if not config.GRAMADS_TOKEN:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GRAMADS_URL,
                headers={
                    "Authorization": f"Bearer {config.GRAMADS_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"SendToChatId": user_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if not response.ok:
                    logger.error("GramAds: %s", await response.json())
                else:
                    logger.debug("GramAds: ad sent to user %s", user_id)

    except Exception as exc:
        logger.warning("GramAds: error for user %s: %s", user_id, exc)
