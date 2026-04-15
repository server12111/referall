import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

LINKNI_API_URL = "https://go.linkni.me/api/subscriptions"


def get_linkni_task_url(user_id: int) -> str | None:
    """
    Returns the Linkni mini-app URL with user_id as sub_code for tracking.
    Format: https://t.me/linknibot/app?startapp=x_{sell_code}_{user_id}
    Returns None if LINKNI_CODE not configured.
    """
    if not config.LINKNI_CODE:
        return None
    return f"https://t.me/linknibot/app?startapp=x_{config.LINKNI_CODE}_{user_id}"


async def get_linkni_raw(user_id: int, sub_code: str | None = None) -> list[dict]:
    """
    Raw API call: GET /api/subscriptions?code={LINKNI_CODE}&user_id={user_id}[&sub_code=...]
    Returns last hour's subscription entries for this user.
    Returns [] on any error or if LINKNI_CODE not set.
    """
    if not config.LINKNI_CODE:
        return []
    try:
        params: dict = {"code": config.LINKNI_CODE, "user_id": user_id}
        if sub_code is not None:
            params["sub_code"] = sub_code
        async with aiohttp.ClientSession() as http:
            async with http.get(
                LINKNI_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Linkni API HTTP %s for user %s", resp.status, user_id)
                    return []
                data = await resp.json()
                logger.info("Linkni API response for user %s: %s", user_id, data)
                return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("Linkni API error for user %s: %s", user_id, exc)
        return []


async def linkni_has_sponsors(user_id: int) -> bool:
    """
    Returns False only when Linkni explicitly says no_sponsors.
    Returns True if sponsors are available (or on API error — don't block the user).
    """
    if not config.LINKNI_CODE:
        return False
    entries = await get_linkni_raw(user_id)
    for entry in entries:
        if entry.get("status") == "no_sponsors":
            return False
    return True


async def linkni_find_new_subscription(user_id: int, done_keys: set) -> tuple[bool, str | None]:
    """
    Check if user has a NEW (unrewarded) subscription in the last hour.
    Returns (True, key) if found, (False, None) otherwise.
    key = timestamp string from API response, used to prevent double-rewarding.
    """
    if not config.LINKNI_CODE:
        return False, None
    entries = await get_linkni_raw(user_id, sub_code=str(user_id))
    for entry in entries:
        if entry.get("status") == "subscribed":
            key = entry.get("timestamp") or str(entry)
            if key not in done_keys:
                return True, key
    return False, None


# Keep for backward compatibility with check in wall handler
async def check_linkni_subscription_by_code(user_id: int, code: str | None) -> bool:
    """
    Check whether the user has subscribed via a specific Linkni code.
    Returns True if subscribed or code is not set.
    On any API error — returns True (don't block on network failure).
    """
    if not code:
        return True
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                LINKNI_API_URL,
                params={"code": code, "user_id": user_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    return True
                data = await resp.json()
                if not isinstance(data, list):
                    return True
                for entry in data:
                    if entry.get("status") == "subscribed":
                        return True
                return False
    except Exception as exc:
        logger.warning("Linkni check error for user %s: %s", user_id, exc)
        return True
