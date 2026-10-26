"""
Админка магазина: статистика продаж, остатки, пополнение склада кодами, возвраты.
"""
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


class Stock(StatesGroup):
    codes = State()


def admin_text() -> str:
    s = db.stats()
    lines = [
        "📊 <b>Продажи</b>",
        f"Сегодня: заказов — {s['orders_today']}, выручка — {s['revenue_today']} ⭐",
        f"Всего: заказов — {s['orders']}, выручка — {s['revenue']} ⭐",
        "",
        "📦 <b>Склад</b>",
    ]
    for p in config.PRODUCTS:
        left = "∞" if p["type"] == "text" else db.available(p["id"])
        lines.append(f"{p['name']}: {left}")
    lines += ["", "Возврат звёзд: <code>/refund номер_заказа</code>"]
    return "\n".join(lines)


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(admin_text(), reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm_stock")
async def stock_choose(call: CallbackQuery):
    await call.message.answer("Какой товар пополнить?", reply_markup=kb.stock_products())
    await call.answer()


@router.callback_query(F.data.startswith("adm_stock:"))
async def stock_product(call: CallbackQuery, state: FSMContext):
    p = config.get_product(call.data.split(":", 1)[1])
    if not p or p["type"] != "codes":
        await call.answer()
        return
    await state.set_state(Stock.codes)
    await state.update_data(product_id=p["id"])
    await call.message.answer(f"Пришлите коды для «{p['name']}» — каждый с новой строки. "
                              "Отмена: /admin")
    await call.answer()


@router.message(Stock.codes, F.text)
async def stock_codes(message: Message, state: FSMContext):
    data = await state.get_data()
    added = db.add_stock(data["product_id"], message.text.splitlines())
    await state.clear()
    p = config.get_product(data["product_id"])
    await message.answer(f"✅ Добавлено кодов: {added}. Теперь в наличии «{p['name']}»: "
                         f"{db.available(p['id'])}")


@router.message(Command("refund"))
async def refund(message: Message, command: CommandObject, bot: Bot):
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Формат: <code>/refund 12</code> — где 12 номер заказа")
        return
    order = db.get_order(int(command.args.strip()))
    if not order or order["status"] != "paid":
        await message.answer("Оплаченный заказ с таким номером не найден.")
        return
    if order["charge_id"] == "demo":
        db.set_refunded(order["id"])
        await message.answer("Это была тестовая оплата — заказ просто помечен как возвращённый.")
        return
    try:
        await bot.refund_star_payment(user_id=order["user_id"],
                                      telegram_payment_charge_id=order["charge_id"])
    except Exception as e:
        await message.answer(f"❌ Telegram не принял возврат: {e}")
        return
    db.set_refunded(order["id"])
    await message.answer(f"✅ Звёзды по заказу №{order['id']} возвращены покупателю.")
    try:
        await bot.send_message(order["user_id"], f"Звёзды за заказ №{order['id']} возвращены на ваш счёт.")
    except Exception:
        pass
