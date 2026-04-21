import logging

from aiohttp import web
from sqlalchemy import select

from database.engine import SessionFactory
from database.models import User, FlyerServiceCompletion

logger = logging.getLogger(__name__)

TASK_REWARD = 0.25


async def handle(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": False}, status=400)

    event_type = data.get("type", "")
    if event_type == "test":
        logger.info("FlyerService webhook test received")
        return web.json_response({"status": True})

    if event_type not in ("sub_completed", "new_status"):
        return web.json_response({"status": True})

    event_data = data.get("data") or {}
    raw_uid = event_data.get("user_id")
    signature = str(event_data.get("signature") or "")

    if not raw_uid:
        return web.json_response({"status": True})

    try:
        user_id = int(raw_uid)
    except (ValueError, TypeError):
        return web.json_response({"status": True})

    try:
        async with SessionFactory() as session:
            db_user = await session.get(User, user_id)
            if not db_user:
                logger.warning("FlyerService webhook: unknown user %s", user_id)
                return web.json_response({"status": True})

            already = (await session.execute(
                select(FlyerServiceCompletion).where(
                    FlyerServiceCompletion.user_id == user_id,
                    FlyerServiceCompletion.signature == signature,
                )
            )).scalar_one_or_none()

            if not already:
                session.add(FlyerServiceCompletion(user_id=user_id, signature=signature))
                db_user.stars_balance += TASK_REWARD
                await session.commit()
                logger.info("FlyerService reward %.2f given to user %s (sig=%s)", TASK_REWARD, user_id, signature)
    except Exception as exc:
        logger.error("FlyerService webhook DB error: %s", exc)

    return web.json_response({"status": True})
