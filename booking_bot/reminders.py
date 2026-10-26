"""
Фоновая задача: раз в минуту проверяет, кому пора напомнить о визите.
"""
import asyncio
import logging
from datetime import timedelta

from aiogram import Bot

import config
import db
from schedule import fmt_dt, now

log = logging.getLogger(__name__)


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            current = now()
            due = db.due_reminders(current, current + timedelta(hours=config.REMIND_HOURS_BEFORE))
            for appt in due:
                try:
                    await bot.send_message(
                        appt["user_id"],
                        f"⏰ Напоминаем: вы записаны на {fmt_dt(db.from_str(appt['start_at']))}\n"
                        f"💅 {appt['service_name']}\n\n{config.CONTACTS_TEXT}\n\n"
                        "Если планы изменились — отмените запись в разделе «Мои записи».",
                    )
                except Exception as e:
                    log.warning("Не удалось напомнить клиенту %s: %s", appt["user_id"], e)
                db.mark_reminded(appt["id"])
        except Exception:
            log.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(60)
