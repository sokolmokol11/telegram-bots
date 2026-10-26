"""
Обычные пользователи в личке: бот рассказывает о себе (для демо — куда зайти и что потестить).
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

import config

router = Router()
router.message.filter(F.chat.type == "private")


def about() -> str:
    text = (
        "📢 Я помогаю вести Telegram-канал:\n\n"
        "• публикую посты по расписанию — админ присылает пост и выбирает время;\n"
        "• слежу за порядком в чате: удаляю ссылки, рекламу и спам, "
        "выдаю предупреждения и мут нарушителям;\n"
        "• приветствую новых участников и убираю служебные сообщения."
    )
    if config.DEMO_CONTACT:
        text += f"\n\n🛠 <i>Это демо: {config.BOT_KIND}.</i>"
        if config.DEMO_CHAT_LINK:
            text += (f"\nПроверьте модерацию сами: зайдите в демо-чат {config.DEMO_CHAT_LINK} "
                     "и отправьте ссылку или рекламу — бот её удалит.")
        text += f"\nХотите такого бота для своего канала? Пишите: {config.DEMO_CONTACT}"
    return text


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")


@router.message()
async def any_message(message: Message):
    await message.answer(about())
