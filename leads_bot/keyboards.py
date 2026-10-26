"""Все клавиатуры бота."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config

BTN_CALC = "🧮 Рассчитать стоимость"
BTN_LEAD = "📝 Оставить заявку"
BTN_FAQ = "❓ Частые вопросы"
BTN_CONTACTS = "📍 Контакты"


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CALC), KeyboardButton(text=BTN_LEAD)],
            [KeyboardButton(text=BTN_FAQ), KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def phone_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


CANCEL = ib("✖️ Отменить", "form_cancel")


def calc_services() -> InlineKeyboardMarkup:
    rows = [[ib(f"{s['name']} — от {s['per_m2']} ₽/м²", f"calc:{s['id']}")] for s in config.CALC_SERVICES]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calc_result() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("📝 Оставить заявку на эту уборку", "calc_lead")],
        [ib("🔁 Посчитать другую", "calc_again")],
    ])


def question(q: dict) -> InlineKeyboardMarkup:
    """Кнопки под вопросом анкеты: варианты ответа, «Пропустить», «Отменить»."""
    rows = []
    if q["type"] == "choice":
        rows += [[ib(opt, f"ans:{i}")] for i, opt in enumerate(q["options"])]
    if q.get("optional"):
        rows.append([ib("➡️ Пропустить", "skip")])
    rows.append([CANCEL])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("✅ Отправить заявку", "form_send")],
        [ib("🔁 Заполнить заново", "form_restart")],
        [CANCEL],
    ])


def faq() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(q, f"faq:{i}")] for i, (q, _) in enumerate(config.FAQ)
    ])


def faq_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[ib("⬅️ Все вопросы", "faq_list")]])


# ---------- Админка ----------

def lead_status(lead_id: int, current: str) -> InlineKeyboardMarkup:
    """Кнопки смены статуса под заявкой (текущий статус не показываем)."""
    buttons = [
        ib(label, f"st:{lead_id}:{code}")
        for code, label in config.STATUSES.items()
        if code not in (current, "new")
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("📋 Последние заявки", "adm:recent")],
        [ib("📥 Выгрузить всё в Excel (CSV)", "adm:csv")],
    ])
