"""
Точка входа. Запуск: python bot.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import ai
import config
import db
from handlers import admin, group, user
from publisher import publisher_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Создайте файл .env по примеру .env.example")
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS пуст: публиковать посты никто не сможет. Узнайте ID командой /myid")
    if not config.CHANNEL_ID:
        logging.warning("CHANNEL_ID не задан: посты публиковать некуда (модерация чата работает)")
    logging.info("ИИ-модерация: %s", "включена" if (config.AI_MODERATION and ai.enabled()) else "выключена")

    db.init()
    session = AiohttpSession(proxy=config.PROXY) if config.PROXY else None
    bot = Bot(config.BOT_TOKEN, session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)  # личка админа: посты и расписание
    dp.include_router(group.router)  # группы: модерация
    dp.include_router(user.router)   # личка остальных: рассказ о боте

    await bot.set_my_commands([
        BotCommand(command="start", description="Что умеет бот"),
        BotCommand(command="queue", description="Очередь постов (для админа)"),
        BotCommand(command="myid", description="Узнать свой ID"),
    ])
    asyncio.create_task(publisher_loop(bot))
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
