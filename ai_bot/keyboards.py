"""Клавиатуры ИИ-консультанта."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_MANAGER = "👤 Позвать менеджера"
BTN_RESET = "🔄 Новый диалог"
BTN_CONTACTS = "📍 Контакты"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_MANAGER)],
            [KeyboardButton(text=BTN_RESET), KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Задайте вопрос…",
    )


def call_manager() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BTN_MANAGER, callback_data="call_manager")]
    ])


def operator_exit() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Вернуться к консультанту", callback_data="operator_exit")]
    ])
