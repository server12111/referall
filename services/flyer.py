import logging

try:
    from flyerapi import Flyer as FlyerClient
except ImportError:
    FlyerClient = None

from config import config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Return a cached Flyer client, or None if FLYER_KEY is not set or flyerapi not installed."""
    if FlyerClient is None or not config.FLYER_KEY:
        return None
    global _client
    if _client is None:
        _client = FlyerClient(config.FLYER_KEY)
    return _client


async def get_channels_count() -> int:
    """Return the number of Flyer channels configured for this bot."""
    client = _get_client()
    if client is None:
        return 0
    try:
        info = await client.get_me()
        channels = info.get("channels") or info.get("resources") or []
        return len(channels)
    except Exception as exc:
        logger.warning("Flyer get_me error: %s", exc)
        return 0


async def check_subscription(user_id: int, language_code: str | None = None) -> bool:
    """
    Check whether the user has subscribed to all required Flyer channels.

    Returns True if:
      - FLYER_KEY is not configured (feature disabled), or
      - the user has subscribed to all channels.

    Returns False if the user is missing at least one subscription.
    When False is returned, Flyer has already sent the subscription wall
    to the user — no additional message is needed.
    """
    client = _get_client()
    if client is None:
        return True

    try:
        return await client.check(
            user_id=user_id,
            language_code=language_code or "en",
        )
    except Exception as exc:
        logger.warning("Flyer API error for user %s: %s", user_id, exc)
        return True  # on error — allow access so users are not blocked
