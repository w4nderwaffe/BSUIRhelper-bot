import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from app.handlers import start, question, admin, feedback, admin_panel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    """Регистрирует команды бота в Telegram — пользователь видит подсказки при вводе /"""
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help",  description="Справка по боту"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main() -> None:
    # --- Валидация переменных окружения ---
    bot_token = os.getenv("BOT_TOKEN")
    api_base_url = os.getenv("API_BASE_URL")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан — заполни файл .env")
    if not api_base_url:
        raise RuntimeError("API_BASE_URL не задан — заполни файл .env")

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # --- Глобальный обработчик необработанных исключений ---
    @dp.errors()
    async def error_handler(event: ErrorEvent) -> None:
        logger.exception(
            "Unhandled exception in update_id=%s: %s",
            event.update.update_id if event.update else "unknown",
            event.exception,
        )

    # Порядок важен: admin раньше question (перехватывает F.document)
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(admin_panel.router)
    dp.include_router(feedback.router)
    dp.include_router(question.router)

    await set_commands(bot)
    logger.info("Bot starting — API: %s", api_base_url)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
