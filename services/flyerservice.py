import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

FLYERSERVICE_API = "https://api.flyerservice.io"


async def get_flyerservice_tasks(user_id: int, language_code: str | None = None) -> list[dict]:
    """
    Returns list of pending tasks for the user from api.flyerservice.io.
    Each task has: signature, type, name, links (list of URLs), price, photo.
    Returns [] if key not set, on error, or no tasks.
    """
    if not config.FLYERSERVICE_KEY:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FLYERSERVICE_API}/get_tasks",
                json={
                    "key": config.FLYERSERVICE_KEY,
                    "user_id": user_id,
                    "language_code": language_code or "ru",
                    "limit": 10,
                },
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    logger.warning("FlyerService get_tasks HTTP %s for user %s", resp.status, user_id)
                    return []
                data = await resp.json()
                if isinstance(data, dict):
                    tasks = data.get("result") or []
                elif isinstance(data, list):
                    tasks = data
                else:
                    return []
                if not isinstance(tasks, list):
                    return []
                logger.debug("FlyerService tasks for user %s: %s", user_id, tasks[:1])
                return tasks
    except Exception as exc:
        logger.warning("FlyerService get_tasks error for user %s: %s", user_id, exc)
        return []


async def is_task_done(user_id: int, signature: str, language_code: str | None = None) -> bool:
    """
    Returns True if the task with given signature is no longer pending
    (i.e. user completed it — it no longer appears in get_tasks response).
    Returns False on error (to not block user).
    """
    tasks = await get_flyerservice_tasks(user_id, language_code)
    if tasks is None:
        return False
    pending_signatures = {t.get("signature") for t in tasks}
    return signature not in pending_signatures
