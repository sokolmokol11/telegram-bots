"""Клавиатуры магазина."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config

BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📦 Мои покупки"
BTN_SUPPORT = "💬 Поддержка"


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)],
            [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_SUPPORT)],
        ],
        resize_keyboard=True,
    )


def categories() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(c["name"], f"cat:{c['id']}")] for c in config.CATEGORIES
    ])


def products(category_id: str) -> InlineKeyboardMarkup:
    rows = [
        [ib(f"{p['name']} — {p['price']} ⭐", f"prod:{p['id']}")]
        for p in config.PRODUCTS if p["category"] == category_id
    ]
    rows.append([ib("⬅️ Категории", "cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product(p: dict, in_cart: int, can_add: bool) -> InlineKeyboardMarkup:
    rows = []
    if in_cart:
        rows.append([ib("➖", f"dec:{p['id']}:p"), ib(f"В корзине: {in_cart}", "noop"),
                     ib("➕", f"inc:{p['id']}:p")])
        rows.append([ib("🛒 Перейти в корзину", "cart")])
    elif can_add:
        rows.append([ib("➕ В корзину", f"inc:{p['id']}:p")])
    rows.append([ib("⬅️ Назад", f"cat:{p['category']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart(items: list[dict], total: int) -> InlineKeyboardMarkup:
    rows = []
    for i in items:
        pid = i["product"]["id"]
        rows.append([ib("➖", f"dec:{pid}:c"), ib(f"{i['product']['name'][:22]} ×{i['qty']}", f"prod:{pid}"),
                     ib("➕", f"inc:{pid}:c")])
    if items:
        rows.append([ib(f"💳 Оформить заказ — {total} ⭐", "checkout")])
        rows.append([ib("🗑 Очистить", "cart_clear")])
    else:
        rows.append([ib("🛍 В каталог", "cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def demo_pay(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[ib("🧪 Тестовая оплата (демо)", f"demo_pay:{order_id}")]])


def orders(orders_: list[dict]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(f"Заказ №{o['id']} от {o['paid_at'][:10]} — {o['total']} ⭐", f"order:{o['id']}")]
        for o in orders_
    ])


# ---------- Админка ----------

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[ib("📦 Пополнить склад", "adm_stock")]])


def stock_products() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(p["name"], f"adm_stock:{p['id']}")] for p in config.PRODUCTS if p["type"] == "codes"
    ])
