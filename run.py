import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, API_HOST, API_PORT
from database.db import init_db
from bot.middlewares import DbSessionMiddleware, MaintenanceMiddleware
from bot.handlers import start, menu, support, admin
from bot.scheduler import run_scheduler
from api.main import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run")


async def build_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: DB session must be available before maintenance check runs
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(MaintenanceMiddleware())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(support.router)
    dp.include_router(admin.router)

    return bot, dp


async def main():
    await init_db()
    bot, dp = await build_bot_and_dispatcher()

    # Make the bot instance available to the FastAPI routes (e.g. to send ticket replies)
    app.state.bot = bot

    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)

    await bot.delete_webhook(drop_pending_updates=True)

    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
        run_scheduler(bot),
    )


if __name__ == "__main__":
    asyncio.run(main())
