import asyncio
import logging
import traceback

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import ErrorEvent

from config import config
from database import init_db
from handlers import routers
from middlewares import SessionMiddleware, RegisteredUserMiddleware
from middlewares.register import CombinedWallMiddleware
from webhooks.flyerservice import handle as fs_webhook_handle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=SQLStorage("fsm_storage.db"))

    # Middlewares — order matters: session → combined wall → user check
    dp.message.middleware(SessionMiddleware())
    dp.callback_query.middleware(SessionMiddleware())
    dp.message.middleware(CombinedWallMiddleware())
    dp.callback_query.middleware(CombinedWallMiddleware())
    dp.message.middleware(RegisteredUserMiddleware())
    dp.callback_query.middleware(RegisteredUserMiddleware())

    @dp.errors()
    async def error_handler(event: ErrorEvent) -> None:
        if isinstance(event.exception, TelegramForbiddenError):
            return
        logger.error("Handler error: %s\n%s", event.exception, traceback.format_exc())

    for router in routers:
        dp.include_router(router)

    from services.retention import retention_loop
    asyncio.create_task(retention_loop(bot))

    # Webhook HTTP server for FlyerService callbacks
    app = web.Application()
    app.router.add_post("/flyerservice/webhook", fs_webhook_handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT)
    await site.start()
    logger.info("Webhook server listening on port %s", config.WEBHOOK_PORT)

    logger.info("Bot started")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
