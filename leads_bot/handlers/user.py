"""
Клиентская часть: меню, калькулятор, FAQ и анкета заявки.

Анкета работает по списку вопросов FORM из config.py: бот задаёт их по одному
и складывает ответы в словарь. Поэтому вопросы можно менять без правки кода.
"""
import asyncio
import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
import sheets

router = Router()
log = logging.getLogger(__name__)


class Calc(StatesGroup):
    area = State()


class Form(StatesGroup):
    filling = State()
    confirm = State()


# ---------- Вспомогательные функции ----------

def parse_number(text: str) -> float | None:
    """«54», «54,5», «около 60 м2» → число. Мусор → None."""
    m = re.search(r"\d+(?:[.,]\d+)?", text or "")
    if not m:
        return None
    value = float(m.group().replace(",", "."))
    return value if 1 <= value <= 10000 else None


def normalize_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    if 10 <= len(digits) <= 15 and text.strip().startswith("+"):
        return "+" + digits
    return None


def fmt_value(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return html.escape(str(value)) if value != "" else "—"


def lead_text(answers: dict) -> str:
    return "\n".join(
        f"<b>{q['label']}:</b> {fmt_value(answers.get(q['key'], ''))}" for q in config.FORM
    )


def admin_card(lead: dict) -> str:
    who = f"@{lead['username']}" if lead["username"] else f"id {lead['user_id']}"
    return (
        f"<b>Заявка №{lead['id']}</b> · {config.STATUSES[lead['status']]}\n"
        f"{lead['created_at']} · {who}\n\n{lead_text(lead['answers'])}"
    )


async def notify_admins(bot: Bot, lead: dict) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_card(lead),
                                   reply_markup=kb.lead_status(lead["id"], lead["status"]))
        except Exception as e:
            log.warning("Не удалось уведомить админа %s: %s", admin_id, e)


# ---------- Меню ----------

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


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(f"<b>{config.BUSINESS_NAME}</b>\n\n{config.CONTACTS_TEXT}",
                         reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_FAQ)
async def faq_list_msg(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите вопрос:", reply_markup=kb.faq())


@router.callback_query(F.data == "faq_list")
async def faq_list_cb(call: CallbackQuery):
    await call.message.edit_text("Выберите вопрос:", reply_markup=kb.faq())
    await call.answer()


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(call: CallbackQuery):
    i = int(call.data.split(":")[1])
    if not 0 <= i < len(config.FAQ):
        await call.answer()
        return
    q, a = config.FAQ[i]
    await call.message.edit_text(f"<b>{q}</b>\n\n{a}", reply_markup=kb.faq_back())
    await call.answer()


# ---------- Калькулятор ----------

@router.message(F.text == kb.BTN_CALC)
async def calc_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Какая уборка нужна?", reply_markup=kb.calc_services())


@router.callback_query(F.data == "calc_again")
async def calc_again(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Какая уборка нужна?", reply_markup=kb.calc_services())
    await call.answer()


@router.callback_query(F.data.startswith("calc:"))
async def calc_service(call: CallbackQuery, state: FSMContext):
    service = config.get_calc_service(call.data.split(":")[1])
    if not service:
        await call.answer()
        return
    await state.set_state(Calc.area)
    await state.update_data(calc_service=service["id"])
    await call.message.edit_text(f"{service['name']}\n\nНапишите площадь в м², например 54.")
    await call.answer()


@router.message(Calc.area, F.text)
async def calc_area(message: Message, state: FSMContext):
    area = parse_number(message.text)
    if area is None:
        await message.answer("Не понял площадь. Напишите число, например 54.")
        return
    data = await state.get_data()
    service = config.get_calc_service(data["calc_service"])
    price = config.calc_price(service, area)
    await state.update_data(calc_area=area)
    price_str = f"{price:,}".replace(",", " ")  # 12500 → «12 500»
    await message.answer(
        f"🧮 <b>{service['name']}</b>, {fmt_value(area)} м²\n\n"
        f"Примерная стоимость: <b>{price_str} ₽</b>\n"
        f"<i>{config.CALC_NOTE}</i>",
        reply_markup=kb.calc_result(),
    )


@router.callback_query(F.data == "calc_lead")
async def calc_to_lead(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = config.get_calc_service(data.get("calc_service", ""))
    prefill = {}
    if service and "calc_area" in data:
        prefill = {"service": service["name"], "area": data["calc_area"]}
    await call.answer()
    await start_form(call.message, state, prefill)


# ---------- Анкета ----------

def next_question(answers: dict) -> tuple[int, dict] | None:
    """Первый вопрос, на который ещё нет ответа (ответы из калькулятора пропускаются)."""
    for i, q in enumerate(config.FORM):
        if q["key"] not in answers:
            return i, q
    return None


async def ask(message: Message, state: FSMContext) -> None:
    """Задаёт следующий вопрос или показывает итог, если вопросы кончились."""
    data = await state.get_data()
    answers = data["answers"]
    nq = next_question(answers)
    if nq is None:
        await state.set_state(Form.confirm)
        await message.answer("Проверьте заявку:\n\n" + lead_text(answers), reply_markup=kb.confirm())
        return
    i, q = nq
    await state.update_data(q=i)
    if q["type"] == "phone":
        await message.answer(q["text"], reply_markup=kb.phone_request())
        await message.answer("Или отмените заявку:", reply_markup=kb.question(q))
    else:
        await message.answer(q["text"], reply_markup=kb.question(q))


async def start_form(message: Message, state: FSMContext, prefill: dict | None = None) -> None:
    await state.clear()
    await state.set_state(Form.filling)
    await state.update_data(answers=dict(prefill or {}))
    await ask(message, state)


async def save_answer(message: Message, state: FSMContext, value) -> None:
    data = await state.get_data()
    q = config.FORM[data["q"]]
    answers = data["answers"]
    answers[q["key"]] = value
    await state.update_data(answers=answers)
    if q["type"] == "phone":
        await message.answer("Спасибо!", reply_markup=kb.main_menu())
    await ask(message, state)


@router.message(F.text == kb.BTN_LEAD)
async def lead_start(message: Message, state: FSMContext):
    await start_form(message, state)


@router.callback_query(Form.filling, F.data.startswith("ans:"))
async def answer_choice(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q = config.FORM[data["q"]]
    i = int(call.data.split(":")[1])
    if q["type"] != "choice" or not 0 <= i < len(q["options"]):
        await call.answer("Эта кнопка устарела", show_alert=True)
        return
    await call.message.edit_text(f"{q['text']}\n<b>{q['options'][i]}</b>")
    await call.answer()
    await save_answer(call.message, state, q["options"][i])


@router.callback_query(Form.filling, F.data == "skip")
async def answer_skip(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not config.FORM[data["q"]].get("optional"):
        await call.answer()
        return
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await save_answer(call.message, state, "")


@router.message(Form.filling, F.contact | F.text)
async def answer_text(message: Message, state: FSMContext):
    data = await state.get_data()
    q = config.FORM[data["q"]]
    raw = message.contact.phone_number if message.contact else message.text

    if q["type"] == "choice":
        await message.answer("Выберите вариант кнопкой выше 👆")
        return
    if q["type"] == "number":
        value = parse_number(raw)
        if value is None:
            await message.answer("Напишите число, например 54.")
            return
    elif q["type"] == "phone":
        value = normalize_phone(raw)
        if not value:
            await message.answer("Не похоже на номер. Пример: +79001234567")
            return
    else:
        value = (raw or "").strip()
        if not 1 <= len(value) <= 500:
            await message.answer("Слишком длинно, сократите до 500 символов.")
            return
    await save_answer(message, state, value)


@router.callback_query(F.data == "form_restart")
async def form_restart(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await start_form(call.message, state)


@router.callback_query(F.data == "form_cancel")
async def form_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Заявка отменена. Вернуться можно через меню 👇")
    await call.message.answer("Главное меню", reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(Form.confirm, F.data == "form_send")
async def form_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    lead = db.add_lead(call.from_user.id, call.from_user.username, data["answers"])
    await call.message.edit_text(
        f"✅ Заявка №{lead['id']} принята!\n\n{config.DONE_TEXT}"
    )
    await call.answer("Отправлено!")
    await notify_admins(bot, lead)
    asyncio.create_task(sheets.append_lead(lead))  # в таблицу пишем в фоне


# ---------- Всё остальное ----------

@router.callback_query()
async def stale_button(call: CallbackQuery):
    await call.answer("Эта кнопка устарела. Начните заново из меню.", show_alert=True)


@router.message()
async def unknown(message: Message):
    await message.answer("Выберите действие в меню 👇", reply_markup=kb.main_menu())
