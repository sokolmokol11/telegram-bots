"""
Админка мастера: команда /admin.
Работает только для ID из ADMIN_IDS в файле .env.
"""
import html
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
from schedule import fmt_day, fmt_dt, now

router = Router()
# Все хендлеры этого роутера срабатывают только для админов
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

MENU_TEXT = "🛠 Панель мастера. Что показать?"


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(MENU_TEXT, reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm:menu")
async def back_to_menu(call: CallbackQuery):
    await call.message.edit_text(MENU_TEXT, reply_markup=kb.admin_menu())
    await call.answer()


def period(name: str) -> tuple[datetime, datetime, str]:
    today = datetime.combine(now().date(), datetime.min.time())
    if name == "today":
        return today, today + timedelta(days=1), "сегодня"
    if name == "tomorrow":
        return today + timedelta(days=1), today + timedelta(days=2), "завтра"
    return today, today + timedelta(days=7), "на 7 дней"


def appointments_text(appts, title: str) -> str:
    if not appts:
        return f"Записей {title} нет."
    lines = [f"📋 Записи {title}:\n"]
    current_day = None
    for a in appts:
        start = db.from_str(a["start_at"])
        if start.date() != current_day:
            current_day = start.date()
            lines.append(f"\n<b>{fmt_day(current_day)}</b>")
        lines.append(
            f"{start:%H:%M}–{a['end_at'][11:]} · {a['service_name']} · "
            f"{html.escape(a['client_name'])}, {a['phone']}"
        )
    lines.append("\nНажмите на запись ниже, чтобы отменить её.")
    return "\n".join(lines)


@router.callback_query(F.data.in_({"adm:today", "adm:tomorrow", "adm:week"}))
async def show_appointments(call: CallbackQuery):
    start, end, title = period(call.data.split(":")[1])
    appts = db.appointments_between(start, end)
    await call.message.edit_text(appointments_text(appts, title),
                                 reply_markup=kb.admin_appointments(appts))
    await call.answer()


@router.callback_query(F.data.startswith("acancel:"))
async def admin_cancel(call: CallbackQuery, bot: Bot):
    appt = db.get_appointment(int(call.data.split(":")[1]))
    if not appt or not db.cancel_appointment(appt["id"]):
        await call.answer("Запись уже отменена", show_alert=True)
        return
    when = fmt_dt(db.from_str(appt["start_at"]))
    await call.answer(f"Запись {when} отменена", show_alert=True)
    try:
        await bot.send_message(
            appt["user_id"],
            f"😔 К сожалению, мастер отменил вашу запись на {when} ({appt['service_name']}).\n"
            "Пожалуйста, выберите другое время: «Записаться».",
        )
    except Exception:
        pass  # клиент мог заблокировать бота
    await call.message.edit_text(MENU_TEXT, reply_markup=kb.admin_menu())


async def render_days_off(call: CallbackQuery) -> None:
    current = now()
    days = [current.date() + timedelta(days=i) for i in range(config.BOOKING_DAYS_AHEAD + 1)]
    days = [d for d in days if d.weekday() in config.WORK_WEEKDAYS]
    await call.message.edit_text(
        "Нажмите на день, чтобы закрыть или открыть его для записи.\n"
        "✅ — открыт, 🔒 — выходной.",
        reply_markup=kb.admin_days_off(days, db.days_off()),
    )


@router.callback_query(F.data == "adm:daysoff")
async def days_off_menu(call: CallbackQuery):
    await render_days_off(call)
    await call.answer()


@router.callback_query(F.data.startswith("dayoff:"))
async def toggle_day(call: CallbackQuery):
    day = call.data.split(":")[1]
    closed = db.toggle_day_off(day)
    note = ""
    if closed:
        d = datetime.fromisoformat(day)
        existing = db.appointments_between(d, d + timedelta(days=1))
        if existing:
            note = f"\nВнимание: на этот день уже есть записи ({len(existing)}). Отмените их вручную."
    await call.answer(("День закрыт" if closed else "День открыт") + note, show_alert=bool(note))
    await render_days_off(call)
