"""
Админка: статусы заявок, последние заявки, выгрузка в CSV (открывается в Excel).
Работает только для ID из ADMIN_IDS.
"""
import csv
import io
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import config
import db
import keyboards as kb
import sheets
from handlers.user import admin_card

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


def stats_text() -> str:
    s = db.stats()
    lines = [f"📊 Заявок всего: <b>{s['total']}</b>, сегодня: <b>{s['today']}</b>\n"]
    for code, label in config.STATUSES.items():
        lines.append(f"{label}: {s['by_status'].get(code, 0)}")
    return "\n".join(lines)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(stats_text(), reply_markup=kb.admin_menu())


@router.callback_query(F.data.startswith("st:"))
async def change_status(call: CallbackQuery, bot: Bot):
    _, lead_id, status = call.data.split(":")
    lead = db.get_lead(int(lead_id))
    if not lead or status not in config.STATUSES:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    db.set_status(lead["id"], status)
    lead["status"] = status
    await call.message.edit_text(admin_card(lead), reply_markup=kb.lead_status(lead["id"], status))
    await call.answer(config.STATUSES[status])

    text = config.CLIENT_STATUS_TEXT.get(status)
    if text:
        try:
            await bot.send_message(lead["user_id"], text.format(id=lead["id"]))
        except Exception:
            pass  # клиент мог заблокировать бота
    await sheets.update_status(lead["id"], status)


@router.callback_query(F.data == "adm:recent")
async def show_recent(call: CallbackQuery):
    leads = db.recent(10)
    await call.answer()
    if not leads:
        await call.message.answer("Заявок пока нет.")
        return
    for lead in reversed(leads):  # старые сверху, новые внизу — как в чате
        await call.message.answer(admin_card(lead),
                                  reply_markup=kb.lead_status(lead["id"], lead["status"]))


def build_csv() -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")  # «;» — чтобы русский Excel сразу разбил по столбцам
    writer.writerow(sheets.HEADERS)
    for lead in db.all_leads():
        writer.writerow(sheets.lead_to_row(lead))
    return buf.getvalue().encode("utf-8-sig")  # BOM — чтобы Excel понял кириллицу


@router.callback_query(F.data == "adm:csv")
async def export_csv(call: CallbackQuery):
    name = f"zayavki_{datetime.now(config.TZ):%Y-%m-%d}.csv"
    await call.message.answer_document(BufferedInputFile(build_csv(), filename=name),
                                       caption="Все заявки")
    await call.answer()
