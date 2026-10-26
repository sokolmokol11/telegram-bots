"""
Админка: ответы клиентам и статистика.

Чтобы ответить клиенту, менеджер нажимает «Ответить» на пересланном вопросе
и пишет текст (или отправляет фото/файл) — бот доставит это клиенту.
"""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import db

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))


async def is_reply_to_client(message: Message) -> bool | dict:
    """Фильтр: админ ответил на сообщение, за которым стоит клиент."""
    if not message.reply_to_message:
        return False
    user_id = db.relay_target(message.chat.id, message.reply_to_message.message_id)
    return {"client_id": user_id} if user_id else False


@router.message(is_reply_to_client)
async def answer_client(message: Message, bot: Bot, client_id: int):
    try:
        if message.text:
            await bot.send_message(client_id, f"👤 Менеджер:\n{message.text}", parse_mode=None)
        else:
            await bot.send_message(client_id, "👤 Менеджер:")
            await bot.copy_message(client_id, message.chat.id, message.message_id)
    except Exception:
        await message.reply("❌ Не доставлено: клиент мог заблокировать бота.")
        return
    db.save_relay(message.chat.id, message.message_id, client_id)  # чтобы можно было ответить и на свой ответ
    await message.reply("✅ Отправлено клиенту")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    s = db.stats()
    ev = s["events"]

    def line(kind: str, label: str) -> str:
        total, today = ev.get(kind, (0, 0))
        return f"{label}: {today} сегодня / {total} всего"

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"Клиентов писали боту: {s['users']}\n"
        + line("ai_answer", "Ответов ИИ") + "\n"
        + line("handoff", "Передано менеджеру") + "\n"
        + line("ai_error", "Ошибок нейросети") + "\n\n"
        "Чтобы ответить клиенту — нажмите «Ответить» на его пересланном вопросе.\n"
        "Базу знаний ИИ меняйте в файле knowledge.md (после правки — перезапуск не нужен)."
    )
