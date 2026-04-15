import logging

import aiohttp

from config import config

logger = logging.getLogger(__name__)

PIARFLOW_URL = "https://piarflow.ru/get_task"


async def get_piarflow_tasks(user_id: int, count: int = 5) -> dict:
    """
    Fetch PiarFlow sponsor tasks for the user.

    Returns:
        {
            "completed": bool,
            "skip":      bool,
            "tasks":     list[str],  # channel URLs
        }
    count — number of sponsors to request (1-10).
    On any error returns completed=True/skip=True so users are never blocked.
    """
    if not config.PIARFLOW_KEY:
        return {"completed": True, "skip": True, "tasks": []}

    headers = {
        "Auth": config.PIARFLOW_KEY,
        "Content-Type": "application/json",
    }
    payload = {"chat_id": user_id, "count": max(1, min(count, 10))}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                PIARFLOW_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status in (401, 400, 422, 500):
                    logger.error("PiarFlow: HTTP %s for user %s", resp.status, user_id)
                    return {"completed": True, "skip": True, "tasks": []}

                if resp.status != 200:
                    logger.error("PiarFlow: Unexpected status %s for user %s", resp.status, user_id)
                    return {"completed": True, "skip": True, "tasks": []}

                data = await resp.json()
                logger.debug("PiarFlow response for user %s: %s", user_id, data)

                # Handle "register" status (user must verify via PiarFlow bot)
                if data.get("status") == "register":
                    reg_url = data.get("additional", {}).get("registration_url", "")
                    logger.info("PiarFlow: user %s needs registration via %s", user_id, reg_url)
                    return {
                        "completed": False,
                        "skip": False,
                        "tasks": [reg_url] if reg_url else [],
                    }

                return {
                    "completed": bool(data.get("completed", True)),
                    "skip": bool(data.get("skip", False)),
                    "tasks": data.get("tasks", []),
                }

    except aiohttp.ClientConnectorError as exc:
        logger.warning("PiarFlow: Connection error for user %s: %s", user_id, exc)
        return {"completed": True, "skip": True, "tasks": []}
    except aiohttp.ServerTimeoutError:
        logger.warning("PiarFlow: Timeout for user %s", user_id)
        return {"completed": True, "skip": True, "tasks": []}
    except Exception as exc:
        logger.warning("PiarFlow: Unexpected error for user %s: %s", user_id, exc)
        return {"completed": True, "skip": True, "tasks": []}
