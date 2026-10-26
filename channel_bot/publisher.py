"""
Публикация постов в канал: сразу или по расписанию (фоновая проверка раз в 20 секунд).

Пост не хранится в базе целиком: бот копирует исходное сообщение из чата админа
с ботом в канал (copy_message). Поэтому работают текст, фото, видео, файлы, опросы —
с форматированием и кнопками-ссылками как в оригинале.
"""
import asyncio
import html
import logging

from aiogram import Bot

import config
import db

log = logging.getLogger(__name__)


def post_link(channel_msg_id: int) -> str | None:
    ch = config.CHANNEL_ID
    if ch.startswith("@"):
        return f"https://t.me/{ch[1:]}/{channel_msg_id}"
    if ch.startswith("-100"):
        return f"https://t.me/c/{ch[4:]}/{channel_msg_id}"
    return None


async def publish(bot: Bot, post) -> bool:
    """Публикует пост из очереди. Возвращает True при успехе."""
    if not config.CHANNEL_ID:
        await bot.send_message(post["created_by"], "❌ Не задан CHANNEL_ID в .env — некуда публиковать.")
        db.set_post_status(post["id"], "failed")
        return False
    try:
        sent = await bot.copy_message(chat_id=config.CHANNEL_ID, from_chat_id=post["from_chat_id"],
                                      message_id=post["message_id"])
    except Exception as e:
        log.warning("Пост №%s не опубликован: %s", post["id"], e)
        db.set_post_status(post["id"], "failed")
        await bot.send_message(
            post["created_by"],
            f"❌ Пост №{post['id']} не опубликован: {html.escape(str(e))}\n\n"
            "Проверьте, что бот — админ канала с правом публикации, а исходное сообщение не удалено.",
        )
        return False
    db.set_post_status(post["id"], "published", sent.message_id)
    link = post_link(sent.message_id)
    await bot.send_message(post["created_by"],
                           f"📢 Пост №{post['id']} опубликован" + (f": {link}" if link else ""))
    return True


async def publisher_loop(bot: Bot) -> None:
    while True:
        try:
            for post in db.due_posts(db.now()):
                await publish(bot, post)
        except Exception:
            log.exception("Ошибка в цикле публикаций")
        await asyncio.sleep(20)
