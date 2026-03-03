import logging
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import config

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseMiddleware):
    """Injects async DB session into every handler."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from database.engine import SessionFactory
        async with SessionFactory() as session:
            data["session"] = session
            return await handler(event, data)


class BotHubMiddleware(BaseMiddleware):
    """
    Enforces BotoHub subscription check before any bot feature.

    /admin and /start are always whitelisted:
      • /admin — admin panel, never blocked
      • /start — registration runs first; the start handler itself shows the
                 subscription wall, preventing a loop.
    Admins always bypass the check entirely.
    botohub:check callback is also whitelisted — its handler does the re-check.
    """

    _SKIP_COMMANDS = {"/admin", "/start"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self._SKIP_COMMANDS):
                return await handler(event, data)

        elif isinstance(event, CallbackQuery):
            user = event.from_user
            # Let botohub:check through — the handler re-checks via API itself
            if event.data == "botohub:check":
                return await handler(event, data)

        else:
            return await handler(event, data)

        if user is None:
            return await handler(event, data)

        # Admins always bypass
        if user.id in config.ADMIN_IDS:
            return await handler(event, data)

        from utils.botohub_api import check_botohub
        result = await check_botohub(user.id)

        if not result["completed"] and not result["skip"]:
            from keyboards.botohub import build_botohub_wall_kb
            wall_text = "📢 <b>Подпишитесь на каналы ниже и нажмите «Я подписался».</b>"
            wall_kb = build_botohub_wall_kb(result["tasks"])

            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
                await event.message.answer(wall_text, reply_markup=wall_kb)
            else:
                await event.answer(wall_text, reply_markup=wall_kb)

            logger.info("BotoHub: blocked user %s — not subscribed", user.id)
            return  # block

        # User passed the subscription wall — give referral reward if still pending
        session = data.get("session")
        if session:
            from database.models import User
            from services.referral import grant_referral_reward_if_pending
            db_user = await session.get(User, user.id)
            if db_user and db_user.referral_reward_pending:
                bot = data.get("bot") or getattr(event, "bot", None)
                if bot:
                    await grant_referral_reward_if_pending(db_user, session, bot)

        return await handler(event, data)


class FlyerMiddleware(BaseMiddleware):
    """
    Enforces Flyer subscription check after BotHub passes.

    /admin and /start are always whitelisted.
    Admins always bypass the check entirely.
    When the user is not subscribed, Flyer sends the wall automatically.
    """

    _SKIP_COMMANDS = {"/admin", "/start"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from services.flyer import check_subscription

        if isinstance(event, Message):
            user = event.from_user
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self._SKIP_COMMANDS):
                return await handler(event, data)

        elif isinstance(event, CallbackQuery):
            user = event.from_user

        else:
            return await handler(event, data)

        if user is None:
            return await handler(event, data)

        # Admins always bypass
        if user.id in config.ADMIN_IDS:
            return await handler(event, data)

        subscribed = await check_subscription(
            user_id=user.id,
            language_code=user.language_code,
        )
        if not subscribed:
            # Flyer already sent the subscription wall automatically.
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer()
                except Exception:
                    pass
            return  # block

        return await handler(event, data)


class RegisteredUserMiddleware(BaseMiddleware):
    """
    Blocks unregistered users from using the bot without /start.
    Admins always bypass this check.
    """

    SKIP_TEXT = {"/start", "/admin"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from database.models import User

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        else:
            return await handler(event, data)

        if user is None:
            return

        # Admins: try to load db_user; if not registered yet — require /start first
        if user.id in config.ADMIN_IDS:
            session = data.get("session")
            db_user = None
            if session:
                db_user = await session.get(User, user.id)
            if db_user:
                data["db_user"] = db_user
                return await handler(event, data)
            if isinstance(event, Message):
                text = event.text or ""
                if any(text.startswith(cmd) for cmd in {"/start", "/admin"}):
                    return await handler(event, data)
                await event.answer("Нажми /start чтобы начать.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сначала нажми /start.", show_alert=True)
            return

        # Skip /start and /admin for regular users
        if isinstance(event, Message):
            text = event.text or ""
            if any(text.startswith(cmd) for cmd in self.SKIP_TEXT):
                return await handler(event, data)

        # Allow botohub:check through
        if isinstance(event, CallbackQuery) and event.data == "botohub:check":
            session = data.get("session")
            if session:
                db_user = await session.get(User, user.id)
                if db_user:
                    data["db_user"] = db_user
            return await handler(event, data)

        session = data.get("session")
        if session is None:
            return

        db_user = await session.get(User, user.id)
        if db_user is None:
            if isinstance(event, Message):
                await event.answer("Нажми /start чтобы начать.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Сначала нажми /start.", show_alert=True)
            return

        data["db_user"] = db_user
        return await handler(event, data)
