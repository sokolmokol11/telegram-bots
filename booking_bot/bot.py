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

import config
import db
from handlers import admin, user
from reminders import reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN. Создайте файл .env по примеру .env.example")
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS пуст: уведомления о записях никому не придут. "
                        "Узнайте свой ID командой /myid и впишите в .env")

    db.init()
    # Прокси нужен, если сервер в России и Telegram с него не отвечает
    session = AiohttpSession(proxy=config.PROXY) if config.PROXY else None
    if config.PROXY:
        logging.info("Подключаюсь к Telegram через прокси")
    bot = Bot(config.BOT_TOKEN, session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)  # админский роутер первым: у клиентского есть «ловушки» для всего остального
    dp.include_router(user.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="myid", description="Узнать свой ID"),
    ])

    asyncio.create_task(reminder_loop(bot))
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
