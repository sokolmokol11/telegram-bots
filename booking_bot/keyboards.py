"""
Все клавиатуры бота.

ReplyKeyboard — большие кнопки внизу экрана (главное меню).
InlineKeyboard — кнопки под сообщением. Нажатие присылает боту callback_data.
"""
from datetime import date, datetime

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config
from schedule import fmt_day, fmt_dt

# Тексты кнопок главного меню (используются и в хендлерах)
BTN_BOOK = "📅 Записаться"
BTN_MY = "🗂 Мои записи"
BTN_PRICES = "💅 Услуги и цены"
BTN_CONTACTS = "📍 Контакты"


def _rows(buttons: list, per_row: int) -> list[list]:
    """Разбивает список кнопок на ряды по per_row штук."""
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK), KeyboardButton(text=BTN_MY)],
            [KeyboardButton(text=BTN_PRICES), KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def phone_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


CANCEL_BTN = InlineKeyboardButton(text="✖️ Отменить", callback_data="book_cancel")


def services() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"{s['name']} — {s['price']} ₽",
            callback_data=f"svc:{s['id']}",
        )]
        for s in config.SERVICES
    ]
    buttons.append([CANCEL_BTN])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dates(days: list[date]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=fmt_day(d), callback_data=f"date:{d.isoformat()}")
        for d in days
    ]
    rows = _rows(buttons, 3)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:services"), CANCEL_BTN])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times(slots: list[datetime]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{t:%H:%M}", callback_data=f"time:{t:%H:%M}")
        for t in slots
    ]
    rows = _rows(buttons, 4)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:dates"), CANCEL_BTN])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="book_confirm")],
        [InlineKeyboardButton(text="✏️ Изменить имя и телефон", callback_data="book_edit_contacts")],
        [CANCEL_BTN],
    ])


def my_appointments(appts) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"✖️ Отменить {fmt_dt(datetime.strptime(a['start_at'], '%Y-%m-%d %H:%M'))}",
            callback_data=f"ucancel:{a['id']}",
        )]
        for a in appts
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Админка ----------

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="adm:today"),
            InlineKeyboardButton(text="Завтра", callback_data="adm:tomorrow"),
            InlineKeyboardButton(text="7 дней", callback_data="adm:week"),
        ],
        [InlineKeyboardButton(text="🗓 Выходные дни", callback_data="adm:daysoff")],
    ])


def admin_appointments(appts) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"✖️ {a['start_at'][8:10]}.{a['start_at'][5:7]} {a['start_at'][11:]} — {a['client_name']}",
            callback_data=f"acancel:{a['id']}",
        )]
        for a in appts
    ]
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_days_off(days: list[date], closed: set[str]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=("🔒 " if d.isoformat() in closed else "✅ ") + fmt_day(d),
            callback_data=f"dayoff:{d.isoformat()}",
        )
        for d in days
    ]
    rows = _rows(buttons, 3)
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
