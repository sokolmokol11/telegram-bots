"""
Клиентская часть: главное меню и пошаговая запись.

Запись — это «машина состояний» (FSM): бот помнит, на каком шаге клиент
и что он уже выбрал (услуга → день → время → имя → телефон → подтверждение).
"""
import html
import logging
import re
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
from schedule import candidate_dates, fmt_day, fmt_dt, free_slots, now

router = Router()
log = logging.getLogger(__name__)


class Booking(StatesGroup):
    service = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


# ---------- Вспомогательные функции ----------

def available_dates(service: dict) -> list[date]:
    """Дни, в которые есть хотя бы одно свободное окно под эту услугу."""
    current = now()
    return [
        d for d in candidate_dates(db.days_off(), current)
        if free_slots(d, service["minutes"], db.busy_intervals(d), current)
    ]


def summary(data: dict) -> str:
    service = config.get_service(data["service_id"])
    start = datetime.fromisoformat(f"{data['day']} {data['time']}")
    return (
        "Проверьте запись:\n\n"
        f"💅 <b>{service['name']}</b> — {service['price']} ₽\n"
        f"🕒 {fmt_dt(start)} ({service['minutes']} мин)\n"
        f"👤 {html.escape(data['name'])}\n"
        f"📞 {data['phone']}"
    )


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:  # админ мог не запускать бота
            log.warning("Не удалось уведомить админа %s: %s", admin_id, e)


def normalize_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    if 10 <= len(digits) <= 15 and text.strip().startswith("+"):
        return "+" + digits
    return None


# ---------- Главное меню (работает из любого шага) ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = config.WELCOME_TEXT
    if config.DEMO_CONTACT:
        text += (
            f"\n\n🛠 <i>Это демо: {config.BOT_KIND}. Компания вымышленная, заявки уходят разработчику, "
            f"никто не приедет 🙂 Хотите такого бота для своего бизнеса? Пишите: {config.DEMO_CONTACT}</i>"
        )
    await message.answer(text, reply_markup=kb.main_menu())


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")


@router.message(F.text == kb.BTN_PRICES)
async def show_prices(message: Message, state: FSMContext):
    await state.clear()
    lines = [f"• {s['name']} — <b>{s['price']} ₽</b> ({s['minutes']} мин)" for s in config.SERVICES]
    await message.answer("Наши услуги:\n\n" + "\n".join(lines), reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_CONTACTS)
async def show_contacts(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f"<b>{config.BUSINESS_NAME}</b>\n\n{config.CONTACTS_TEXT}",
                         reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_MY)
async def show_my(message: Message, state: FSMContext):
    await state.clear()
    appts = db.user_upcoming(message.from_user.id, now())
    if not appts:
        await message.answer("У вас нет предстоящих записей.", reply_markup=kb.main_menu())
        return
    lines = [
        f"• {fmt_dt(db.from_str(a['start_at']))} — {a['service_name']}"
        for a in appts
    ]
    await message.answer("Ваши записи:\n\n" + "\n".join(lines),
                         reply_markup=kb.my_appointments(appts))


@router.callback_query(F.data.startswith("ucancel:"))
async def user_cancel(call: CallbackQuery, bot: Bot):
    appt = db.get_appointment(int(call.data.split(":")[1]))
    if not appt or appt["user_id"] != call.from_user.id or not db.cancel_appointment(appt["id"]):
        await call.answer("Запись уже отменена", show_alert=True)
        return
    when = fmt_dt(db.from_str(appt["start_at"]))
    await call.message.edit_text(f"❌ Запись на {when} отменена.")
    await call.answer()
    await notify_admins(bot, f"❌ Клиент отменил запись\n{when} — {appt['service_name']}\n"
                             f"👤 {html.escape(appt['client_name'])}, {appt['phone']}")


# ---------- Шаг 1: услуга ----------

@router.message(F.text == kb.BTN_BOOK)
async def book_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Booking.service)
    await message.answer("Выберите услугу:", reply_markup=kb.services())


@router.callback_query(F.data == "back:services")
async def back_to_services(call: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.service)
    await call.message.edit_text("Выберите услугу:", reply_markup=kb.services())
    await call.answer()


@router.callback_query(F.data == "book_cancel")
async def book_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Запись отменена. Если передумаете — нажмите «Записаться».")
    await call.answer()


# ---------- Шаг 2: день ----------

async def show_dates(call: CallbackQuery, state: FSMContext, service: dict,
                     answered: bool = False):
    """Показывает дни. answered=True, если на нажатие кнопки уже ответили."""
    days = available_dates(service)
    if not days:
        if not answered:
            await call.answer("На ближайшие две недели свободного времени нет 😔", show_alert=True)
        return
    await state.set_state(Booking.day)
    await call.message.edit_text(
        f"💅 {service['name']}\n\nВыберите день:", reply_markup=kb.dates(days)
    )
    if not answered:
        await call.answer()


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_service(call: CallbackQuery, state: FSMContext):
    service = config.get_service(call.data.split(":")[1])
    if not service:
        await call.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(service_id=service["id"])
    await show_dates(call, state, service)


@router.callback_query(F.data == "back:dates")
async def back_to_dates(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = config.get_service(data.get("service_id", ""))
    if not service:
        await back_to_services(call, state)
        return
    await show_dates(call, state, service)


# ---------- Шаг 3: время ----------

@router.callback_query(Booking.day, F.data.startswith("date:"))
async def choose_day(call: CallbackQuery, state: FSMContext):
    day = date.fromisoformat(call.data.split(":")[1])
    data = await state.get_data()
    service = config.get_service(data["service_id"])
    slots = free_slots(day, service["minutes"], db.busy_intervals(day), now())
    if not slots:
        await call.answer("На этот день окна закончились, выберите другой", show_alert=True)
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(Booking.time)
    await call.message.edit_text(
        f"💅 {service['name']}\n📅 {fmt_day(day)}\n\n"
        "Выберите время:",
        reply_markup=kb.times(slots),
    )
    await call.answer()


# ---------- Шаг 4–5: имя и телефон ----------

@router.callback_query(Booking.time, F.data.startswith("time:"))
async def choose_time(call: CallbackQuery, state: FSMContext):
    await state.update_data(time=call.data.split(":", 1)[1])
    await call.answer()

    # Постоянному клиенту не задаём лишних вопросов
    known = db.last_contacts(call.from_user.id)
    if known:
        await state.update_data(name=known["client_name"], phone=known["phone"])
        await state.set_state(Booking.confirm)
        await call.message.edit_text(summary(await state.get_data()), reply_markup=kb.confirm())
        return

    await state.set_state(Booking.name)
    await call.message.edit_text("Как к вам обращаться? Напишите имя.")


@router.callback_query(Booking.confirm, F.data == "book_edit_contacts")
async def edit_contacts(call: CallbackQuery, state: FSMContext):
    await state.set_state(Booking.name)
    await call.message.edit_text("Как к вам обращаться? Напишите имя.")
    await call.answer()


@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Имя должно быть от 2 до 50 символов. Попробуйте ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer(
        "Отправьте номер телефона кнопкой ниже или напишите его, например +79001234567.",
        reply_markup=kb.phone_request(),
    )


@router.message(Booking.phone, F.contact | F.text)
async def enter_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if not phone:
        await message.answer("Не похоже на номер телефона. Пример: +79001234567")
        return
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    await message.answer("Отлично!", reply_markup=kb.main_menu())
    await message.answer(summary(await state.get_data()), reply_markup=kb.confirm())


# ---------- Шаг 6: подтверждение ----------

@router.callback_query(Booking.confirm, F.data == "book_confirm")
async def confirm_booking(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    service = config.get_service(data["service_id"])
    start = datetime.fromisoformat(f"{data['day']} {data['time']}")
    end = start + timedelta(minutes=service["minutes"])

    current = now()
    if start < current + timedelta(hours=config.MIN_HOURS_BEFORE):
        await call.answer("Это время уже прошло, выберите другое", show_alert=True)
        await state.set_state(Booking.service)
        await call.message.edit_text("Выберите услугу:", reply_markup=kb.services())
        return

    # Если до визита меньше суток, напоминание не нужно — клиент только что записался
    soon = start - current <= timedelta(hours=config.REMIND_HOURS_BEFORE)
    appt_id = db.add_appointment(
        user_id=call.from_user.id,
        username=call.from_user.username,
        client_name=data["name"],
        phone=data["phone"],
        service=service,
        start=start,
        end=end,
        reminded=soon,
    )
    if appt_id is None:
        await call.answer("Ой, это время только что заняли. Выберите другое.", show_alert=True)
        await show_dates(call, state, service, answered=True)
        return

    await state.clear()
    await call.message.edit_text(
        f"✅ Вы записаны!\n\n💅 {service['name']}\n🕒 {fmt_dt(start)}\n\n"
        f"{config.CONTACTS_TEXT}\n\n"
        "Напомню о визите заранее. Отменить запись можно в разделе «Мои записи»."
    )
    await call.answer("Готово!")

    username = f" (@{call.from_user.username})" if call.from_user.username else ""
    await notify_admins(
        bot,
        f"🆕 Новая запись #{appt_id}\n"
        f"🕒 {fmt_dt(start)} — {service['name']}, {service['price']} ₽\n"
        f"👤 {html.escape(data['name'])}{username}\n📞 {data['phone']}",
    )


# ---------- Всё остальное ----------

@router.callback_query()
async def stale_button(call: CallbackQuery):
    """Нажатие на кнопку из старого сообщения, когда шаг уже пройден."""
    await call.answer("Эта кнопка устарела. Начните заново: «Записаться».", show_alert=True)


@router.message()
async def unknown(message: Message):
    await message.answer("Выберите действие в меню 👇", reply_markup=kb.main_menu())
