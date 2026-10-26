"""
Модерация чата (группы или чата обсуждения канала).

Сообщения обычных участников проверяются на ссылки, стоп-слова и — если подключена
нейросеть — на спам/рекламу. Нарушение: сообщение удаляется, участник получает
предупреждение; после MAX_WARNINGS предупреждений — мут на MUTE_HOURS часов.
Админов чата бот не трогает.
"""
import asyncio
import html
import logging
import re
import time
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.types import ChatPermissions, Message

import ai
import config
import db

router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))
log = logging.getLogger(__name__)

LINK_RE = re.compile(r"(https?://|www\.|t\.me/|\b[\w-]+\.(ru|com|net|org|io|me|xyz|top|site|online|рф)\b)",
                     re.IGNORECASE)

_admins_cache: dict[int, tuple[float, set[int]]] = {}


async def chat_admins(bot: Bot, chat_id: int) -> set[int]:
    """Админы чата, с кэшем на 10 минут, чтобы не спрашивать Telegram на каждое сообщение."""
    cached = _admins_cache.get(chat_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        members = await bot.get_chat_administrators(chat_id)
        ids = {m.user.id for m in members}
    except Exception as e:
        log.warning("Не удалось получить админов чата %s: %s", chat_id, e)
        ids = set()
    _admins_cache[chat_id] = (time.monotonic() + 600, ids)
    return ids


def find_violation(text: str, entities=None) -> str | None:
    """Правила без нейросети. Возвращает причину или None."""
    low = (text or "").lower()
    if config.DELETE_LINKS:
        if any(e.type in ("url", "text_link") for e in (entities or [])) or LINK_RE.search(low):
            return "ссылки в чате запрещены"
    for word in config.STOP_WORDS:
        if word in low:
            return "запрещённая тема"
    return None


async def ai_is_spam(text: str) -> bool:
    if not (config.AI_MODERATION and ai.enabled()) or len(text) < config.AI_MIN_LENGTH:
        return False
    try:
        answer = await ai.chat(
            [
                {"role": "system", "content":
                    "Ты модератор русскоязычного чата. Определи, является ли сообщение спамом: "
                    "рекламой, предложением заработка, мошенничеством, продажей услуг, призывом "
                    "писать в личку. Обычные вопросы, споры и мнения — не спам. "
                    "Ответь одним словом: SPAM или OK."},
                {"role": "user", "content": text[:1500]},
            ],
            max_tokens=3, temperature=0,
        )
    except ai.AIError as e:
        log.warning("ИИ-модерация недоступна: %s", e)
        return False  # нейросеть недоступна — не наказываем
    return "SPAM" in answer.upper()


async def delete_later(bot: Bot, chat_id: int, message_id: int, seconds: int) -> None:
    await asyncio.sleep(seconds)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def punish(bot: Bot, message: Message, reason: str) -> None:
    chat_id, user = message.chat.id, message.from_user
    try:
        await message.delete()
    except Exception as e:
        log.warning("Не удалось удалить сообщение (бот не админ?): %s", e)
        return
    name = html.escape(user.first_name or "участник")
    count = db.add_warning(chat_id, user.id)
    if count >= config.MAX_WARNINGS:
        try:
            await bot.restrict_chat_member(
                chat_id, user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=timedelta(hours=config.MUTE_HOURS),
            )
            db.reset_warnings(chat_id, user.id)
            db.log_action(chat_id, user.id, "muted", reason)
            text = f"🔇 {name} не может писать {config.MUTE_HOURS} ч. Причина: {reason}."
        except Exception as e:
            log.warning("Не удалось выдать мут: %s", e)
            db.log_action(chat_id, user.id, "deleted", reason)
            text = f"⚠️ {name}, {reason}."
    else:
        db.log_action(chat_id, user.id, "deleted", reason)
        text = f"⚠️ {name}, {reason}. Предупреждение {count}/{config.MAX_WARNINGS}."
    notice = await bot.send_message(chat_id, text)
    asyncio.create_task(delete_later(bot, chat_id, notice.message_id, 30))


@router.message(F.new_chat_members)
async def new_members(message: Message, bot: Bot):
    if config.DELETE_JOIN_MESSAGES:
        try:
            await message.delete()
        except Exception:
            pass
    for member in message.new_chat_members:
        if member.is_bot or not config.WELCOME_TEXT:
            continue
        sent = await bot.send_message(message.chat.id,
                                      config.WELCOME_TEXT.format(name=html.escape(member.first_name or "")))
        asyncio.create_task(delete_later(bot, message.chat.id, sent.message_id, 60))


@router.message(F.left_chat_member)
async def left_member(message: Message):
    if config.DELETE_JOIN_MESSAGES:
        try:
            await message.delete()
        except Exception:
            pass


@router.message()
async def moderate(message: Message, bot: Bot):
    user = message.from_user
    # Не трогаем: посты канала в чате обсуждения, анонимных админов, ботов, админов чата
    if message.is_automatic_forward or message.sender_chat or not user or user.is_bot:
        return
    if user.id in config.ADMIN_IDS or user.id in await chat_admins(bot, message.chat.id):
        return
    text = message.text or message.caption or ""
    reason = find_violation(text, message.entities or message.caption_entities)
    if reason is None and await ai_is_spam(text):
        reason = "реклама и спам запрещены"
    if reason:
        await punish(bot, message, reason)
