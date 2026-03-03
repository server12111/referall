import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

BOTOHUB_URL = "https://botohub.me/get-tasks"


async def check_botohub(user_id: int) -> dict:
    """
    Check whether the user has completed all BotoHub sponsor tasks.

    Returns:
        {
            "completed": bool,  # True — all tasks done, allow access
            "skip":      bool,  # True — no sponsors available, allow access
            "tasks":     list,  # List of channel URLs to show the user
        }

    On any API error returns {"completed": True, "skip": True, "tasks": []}
    so users are never blocked by a network failure.
    """
    if not config.BOTOHUB_KEY:
        logger.warning("BotoHub: BOTOHUB_KEY is not set — subscription check disabled")
        return {"completed": True, "skip": True, "tasks": []}

    headers = {
        "Auth": config.BOTOHUB_KEY,
        "Content-Type": "application/json",
    }
    payload = {"chat_id": user_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                BOTOHUB_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 401:
                    logger.error("BotoHub: Unauthorized (401) — check your BOTOHUB_KEY")
                    return {"completed": True, "skip": True, "tasks": []}

                if resp.status == 400:
                    logger.error("BotoHub: Bad request (400)")
                    return {"completed": True, "skip": True, "tasks": []}

                if resp.status != 200:
                    logger.error("BotoHub: Unexpected status %s for user %s", resp.status, user_id)
                    return {"completed": True, "skip": True, "tasks": []}

                data = await resp.json()
                logger.debug("BotoHub response for user %s: %s", user_id, data)

                return {
                    "completed": bool(data.get("completed", True)),
                    "skip": bool(data.get("skip", False)),
                    "tasks": data.get("tasks", []),
                }

    except aiohttp.ClientConnectorError as exc:
        logger.warning("BotoHub: Connection error for user %s: %s", user_id, exc)
        return {"completed": True, "skip": True, "tasks": []}
    except aiohttp.ServerTimeoutError:
        logger.warning("BotoHub: Timeout for user %s", user_id)
        return {"completed": True, "skip": True, "tasks": []}
    except Exception as exc:
        logger.warning("BotoHub: Unexpected error for user %s: %s", user_id, exc)
        return {"completed": True, "skip": True, "tasks": []}
