"""
Покупатель: каталог → корзина → оплата звёздами Telegram → моментальная выдача.

Как проходит оплата:
1. «Оформить заказ» → бот создаёт заказ и присылает счёт в звёздах (⭐).
2. Telegram перед списанием спрашивает бота «можно?» (pre_checkout) — бот проверяет склад.
3. После оплаты приходит successful_payment — бот выдаёт товар.
   Если товар внезапно закончился, звёзды автоматически возвращаются.
"""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

import config
import db
import keyboards as kb

router = Router()
log = logging.getLogger(__name__)


# ---------- Тексты ----------

def product_text(p: dict) -> str:
    left = db.available(p["id"])
    if p["type"] == "text":
        stock = "⚡ Моментальная выдача"
    elif left:
        stock = f"✅ В наличии: {left} шт."
    else:
        stock = "❌ Нет в наличии"
    return f"<b>{html.escape(p['name'])}</b>\n\n{html.escape(p['description'])}\n\n💰 {p['price']} ⭐\n{stock}"


def cart_text(items: list[dict]) -> tuple[str, int]:
    if not items:
        return "🛒 Корзина пуста.", 0
    total = sum(i["sum"] for i in items)
    lines = [f"• {html.escape(i['product']['name'])} × {i['qty']} = {i['sum']} ⭐" for i in items]
    return "🛒 <b>Корзина</b>\n\n" + "\n".join(lines) + f"\n\n<b>Итого: {total} ⭐</b>", total


def delivery_text(order: dict) -> str:
    parts = [f"✅ <b>Заказ №{order['id']} оплачен!</b> Ваши товары:\n"]
    for item in order["items"]:
        product = config.get_product(item["product_id"])
        name = html.escape(product["name"] if product else item["product_id"])
        content = order["delivered"].get(item["product_id"])
        if isinstance(content, list):
            codes = "\n".join(f"<code>{html.escape(c)}</code>" for c in content)
            parts.append(f"<b>{name}</b>:\n{codes}")
        else:
            parts.append(f"<b>{name}</b>:\n{html.escape(content or '')}")
    parts.append("\nКоды копируются нажатием. Все покупки — в разделе «📦 Мои покупки».")
    return "\n\n".join(parts)


def max_qty(p: dict) -> int:
    """Текстовый товар (ссылка, гайд) нет смысла брать дважды."""
    return 1 if p["type"] == "text" else db.available(p["id"])


# ---------- Меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message):
    text = config.WELCOME_TEXT
    if config.DEMO_CONTACT:
        text += (
            f"\n\n🛠 <i>Это демо: {config.BOT_KIND}. Магазин и товары вымышленные"
            + (", оплатить можно тестово, бесплатно" if config.DEMO_PAYMENTS else "")
            + f". Хотите такого бота для своего бизнеса? Пишите: {config.DEMO_CONTACT}</i>"
        )
    await message.answer(text, reply_markup=kb.main_menu())


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")


@router.message(F.text == kb.BTN_SUPPORT)
async def support(message: Message):
    await message.answer(config.SUPPORT_TEXT)


# ---------- Каталог ----------

@router.message(F.text == kb.BTN_CATALOG)
async def catalog(message: Message):
    await message.answer("Выберите категорию:", reply_markup=kb.categories())


@router.callback_query(F.data == "cats")
async def catalog_cb(call: CallbackQuery):
    await call.message.edit_text("Выберите категорию:", reply_markup=kb.categories())
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def category(call: CallbackQuery):
    cat = config.get_category(call.data.split(":", 1)[1])
    if not cat:
        await call.answer()
        return
    await call.message.edit_text(cat["name"], reply_markup=kb.products(cat["id"]))
    await call.answer()


async def show_product(call: CallbackQuery, p: dict) -> None:
    in_cart = db.cart_qty(call.from_user.id, p["id"])
    await call.message.edit_text(product_text(p),
                                 reply_markup=kb.product(p, in_cart, max_qty(p) > 0))


@router.callback_query(F.data.startswith("prod:"))
async def product(call: CallbackQuery):
    p = config.get_product(call.data.split(":", 1)[1])
    if not p:
        await call.answer("Товар больше не продаётся", show_alert=True)
        return
    await show_product(call, p)
    await call.answer()


# ---------- Корзина ----------

async def show_cart(call_or_msg, edit: bool) -> None:
    user_id = call_or_msg.from_user.id
    items = db.cart(user_id)
    text, total = cart_text(items)
    markup = kb.cart(items, total)
    if edit:
        await call_or_msg.message.edit_text(text, reply_markup=markup)
    else:
        await call_or_msg.answer(text, reply_markup=markup)


@router.message(F.text == kb.BTN_CART)
async def cart_msg(message: Message):
    await show_cart(message, edit=False)


@router.callback_query(F.data == "cart")
async def cart_cb(call: CallbackQuery):
    await show_cart(call, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith(("inc:", "dec:")))
async def change_qty(call: CallbackQuery):
    action, product_id, where = call.data.split(":")
    p = config.get_product(product_id)
    if not p:
        await call.answer()
        return
    qty = db.cart_qty(call.from_user.id, product_id)
    if action == "inc":
        if qty + 1 > max_qty(p):
            await call.answer("Больше добавить нельзя" if p["type"] == "text" else "Больше нет в наличии",
                              show_alert=True)
            return
        qty += 1
        note = "Добавлено в корзину"
    else:
        qty -= 1
        note = "Убрано"
    db.cart_set(call.from_user.id, product_id, qty)
    if where == "c":
        await show_cart(call, edit=True)
    else:
        await show_product(call, p)
    await call.answer(note)


@router.callback_query(F.data == "cart_clear")
async def cart_clear(call: CallbackQuery):
    db.cart_clear(call.from_user.id)
    await show_cart(call, edit=True)
    await call.answer("Корзина очищена")


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


# ---------- Оформление и оплата ----------

@router.callback_query(F.data == "checkout")
async def checkout(call: CallbackQuery, bot: Bot):
    items = db.cart(call.from_user.id)
    if not items:
        await call.answer("Корзина пуста", show_alert=True)
        return
    short = [i for i in items if i["qty"] > max_qty(i["product"])]
    if short:
        names = ", ".join(i["product"]["name"] for i in short)
        await call.answer(f"Не хватает на складе: {names}. Уменьшите количество.", show_alert=True)
        await show_cart(call, edit=True)
        return

    order = db.create_order(call.from_user.id, call.from_user.username, items)
    description = ", ".join(f"{i['product']['name']} ×{i['qty']}" for i in items)[:255]
    await call.answer()
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Заказ №{order['id']}",
        description=description,
        payload=f"order:{order['id']}",
        currency="XTR",                 # XTR — звёзды Telegram
        prices=[LabeledPrice(label=f"Заказ №{order['id']}", amount=order["total"])],
        provider_token="",              # для звёзд токен платёжки не нужен
    )
    if config.DEMO_PAYMENTS:
        await call.message.answer("Это демо — можно оплатить тестово, без списания звёзд:",
                                  reply_markup=kb.demo_pay(order["id"]))


def order_from_payload(payload: str) -> dict | None:
    if not payload.startswith("order:"):
        return None
    try:
        return db.get_order(int(payload.split(":", 1)[1]))
    except ValueError:
        return None


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    """Последняя проверка перед списанием: заказ не оплачен и товар ещё есть."""
    order = order_from_payload(query.invoice_payload)
    if not order or order["status"] != "pending" or order["user_id"] != query.from_user.id:
        await query.answer(ok=False, error_message="Этот заказ уже оплачен или устарел. Оформите новый.")
    elif not db.order_in_stock(order):
        await query.answer(ok=False, error_message="Товар только что закончился 😔 Обновите корзину.")
    else:
        await query.answer(ok=True)


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            log.warning("Не удалось уведомить админа %s: %s", admin_id, e)


async def complete(bot: Bot, order: dict, charge_id: str, chat_id: int) -> bool:
    """Выдаёт товар. Возвращает False, если выдать не получилось."""
    done = db.fulfill(order["id"], charge_id)
    if done is None:
        return False
    db.cart_clear(order["user_id"])
    await bot.send_message(chat_id, delivery_text(done))
    who = f"@{done['username']}" if done["username"] else f"id {done['user_id']}"
    demo = " (тестовая оплата)" if charge_id == "demo" else ""
    await notify_admins(bot, f"💰 Продажа{demo}: заказ №{done['id']} на {done['total']} ⭐ — {who}")
    for item in done["items"]:  # предупреждение о заканчивающихся кодах
        p = config.get_product(item["product_id"])
        if p and p["type"] == "codes":
            left = db.available(p["id"])
            if left <= config.LOW_STOCK:
                await notify_admins(bot, f"⚠️ Заканчиваются коды «{p['name']}»: осталось {left}. "
                                         "Пополните: /admin → «Пополнить склад»")
    return True


@router.message(F.successful_payment)
async def paid(message: Message, bot: Bot):
    payment = message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    order = order_from_payload(payment.invoice_payload)
    if order and await complete(bot, order, charge_id, message.chat.id):
        return
    # Товар не удалось выдать — возвращаем звёзды
    try:
        await bot.refund_star_payment(user_id=message.from_user.id, telegram_payment_charge_id=charge_id)
        if order:
            db.set_refunded(order["id"], charge_id)
        await message.answer("😔 Товар закончился в момент оплаты. Звёзды возвращены на ваш счёт.")
    except Exception:
        log.exception("Не удалось вернуть платёж %s", charge_id)
        await message.answer("😔 Не получилось выдать товар. Мы уже разбираемся — напишите в поддержку.\n"
                             + config.SUPPORT_TEXT)
    await notify_admins(bot, f"❗ Оплата {payment.total_amount} ⭐ без выдачи товара, платёж {charge_id}. "
                             "Проверьте склад.")


@router.callback_query(F.data.startswith("demo_pay:"))
async def demo_pay(call: CallbackQuery, bot: Bot):
    order = db.get_order(int(call.data.split(":")[1]))
    if not config.DEMO_PAYMENTS or not order or order["user_id"] != call.from_user.id:
        await call.answer("Недоступно", show_alert=True)
        return
    if order["status"] != "pending":
        await call.answer("Заказ уже оплачен", show_alert=True)
        return
    if not await complete(bot, order, "demo", call.message.chat.id):
        await call.answer("Товар закончился, обновите корзину", show_alert=True)
        return
    await call.message.edit_text("🧪 Тестовая оплата прошла.")
    await call.answer()


# ---------- Мои покупки ----------

@router.message(F.text == kb.BTN_ORDERS)
async def my_orders(message: Message):
    orders = db.user_orders(message.from_user.id)
    if not orders:
        await message.answer("Покупок пока нет. Загляните в каталог 🛍")
        return
    await message.answer("Ваши покупки — нажмите, чтобы снова получить товар:",
                         reply_markup=kb.orders(orders))


@router.callback_query(F.data.startswith("order:"))
async def show_order(call: CallbackQuery):
    order = db.get_order(int(call.data.split(":")[1]))
    if not order or order["user_id"] != call.from_user.id or order["status"] != "paid":
        await call.answer("Заказ не найден", show_alert=True)
        return
    await call.message.answer(delivery_text(order))
    await call.answer()


# ---------- Всё остальное ----------

@router.callback_query()
async def stale(call: CallbackQuery):
    await call.answer("Кнопка устарела. Откройте каталог заново.", show_alert=True)


@router.message()
async def unknown(message: Message):
    await message.answer("Выберите действие в меню 👇", reply_markup=kb.main_menu())
