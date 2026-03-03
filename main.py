import asyncio
import logging
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram_sqlite_storage.sqlitestore import SQLStorage
from aiogram.types import ErrorEvent

from config import config
from database import init_db
from handlers import routers
from middlewares import SessionMiddleware, BotHubMiddleware, FlyerMiddleware, RegisteredUserMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=SQLStorage("fsm_storage.db"))

    # Middlewares — order matters: session → botohub → flyer → user check
    dp.message.middleware(SessionMiddleware())
    dp.callback_query.middleware(SessionMiddleware())
    dp.message.middleware(BotHubMiddleware())
    dp.callback_query.middleware(BotHubMiddleware())
    dp.message.middleware(FlyerMiddleware())
    dp.callback_query.middleware(FlyerMiddleware())
    dp.message.middleware(RegisteredUserMiddleware())
    dp.callback_query.middleware(RegisteredUserMiddleware())

    @dp.errors()
    async def error_handler(event: ErrorEvent) -> None:
        logger.error("Handler error: %s\n%s", event.exception, traceback.format_exc())

    for router in routers:
        dp.include_router(router)

    logger.info("Bot started")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
