"""
Админ в личке с ботом: отправляет пост → выбирает время → пост уходит в канал.
"""
import html
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import db
import publisher
from timeparse import fmt, parse_when, preset

router = Router()
router.message.filter(F.chat.type == "private", F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

HELP_TEXT = (
    "📢 <b>Как публиковать</b>\n\n"
    "Пришлите мне пост — текст, фото с подписью, видео или файл — так, как он должен выглядеть "
    "в канале. Я спрошу, когда его опубликовать.\n\n"
    "/queue — запланированные посты (можно отменить)\n"
    "/admin — статистика постов и модерации\n\n"
    "Время можно написать текстом: <code>18:30</code>, <code>27.10 18:30</code>, "
    "<code>завтра 10:00</code>, <code>через 2 часа</code>."
)


class Custom(StatesGroup):
    when = State()


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def when_keyboard(msg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("🚀 Сейчас", f"sch:{msg_id}:now"), ib("⏱ Через час", f"sch:{msg_id}:1h")],
        [ib("🌆 Сегодня в 19:00", f"sch:{msg_id}:evening"), ib("☀️ Завтра в 10:00", f"sch:{msg_id}:morning")],
        [ib("✏️ Своё время", f"sch:{msg_id}:custom"), ib("✖️ Не публиковать", f"sch:{msg_id}:no")],
    ])


def preview_of(message: Message | None) -> str:
    if message is None:
        return "пост"
    text = message.text or message.caption or ""
    kind = ("📷 " if message.photo else "🎬 " if message.video else "📎 " if message.document else "")
    text = " ".join(text.split())
    return (kind + (text[:40] + "…" if len(text) > 40 else text)).strip() or kind.strip() or "пост"


async def schedule(bot: Bot, admin_id: int, chat_id: int, msg_id: int, preview: str, when) -> str:
    post_id = db.add_post(admin_id, chat_id, msg_id, preview, when)
    if when <= db.now():
        post = next(p for p in db.due_posts(db.now()) if p["id"] == post_id)
        await publisher.publish(bot, post)
        return f"Публикую пост №{post_id}…"
    return f"✅ Пост №{post_id} запланирован на {fmt(when)}. Очередь: /queue"


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    channel = config.CHANNEL_ID or "не задан (впишите CHANNEL_ID в .env)"
    await message.answer(f"{HELP_TEXT}\n\nКанал: {html.escape(channel)}")


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")


@router.message(Command("queue"))
async def cmd_queue(message: Message):
    posts = db.scheduled()
    if not posts:
        await message.answer("Очередь пуста. Пришлите пост, чтобы запланировать.")
        return
    lines = [f"№{p['id']} — {fmt(datetime.strptime(p['publish_at'], db.FMT))} — "
             f"{html.escape(p['preview'])}" for p in posts]
    buttons = [[ib(f"✖️ Отменить №{p['id']}", f"cancel_post:{p['id']}")] for p in posts]
    await message.answer("🗓 <b>Запланировано:</b>\n\n" + "\n".join(lines),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("cancel_post:"))
async def cancel_post(call: CallbackQuery):
    post_id = int(call.data.split(":")[1])
    ok = db.set_post_status(post_id, "cancelled")
    await call.answer(f"Пост №{post_id} отменён" if ok else "Уже опубликован или отменён", show_alert=not ok)
    if ok:
        await call.message.edit_reply_markup(reply_markup=None)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    pc = db.post_counts()
    ms = db.mod_stats()

    def mod(action: str) -> str:
        total, today = ms.get(action, (0, 0))
        return f"{today} сегодня / {total} всего"

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"Постов в очереди: {pc.get('scheduled', 0)}\n"
        f"Опубликовано: {pc.get('published', 0)}\n"
        f"Ошибок публикации: {pc.get('failed', 0)}\n\n"
        f"Удалено нарушений в чате: {mod('deleted')}\n"
        f"Выдано мутов: {mod('muted')}"
    )


# ---------- Планирование ----------

@router.callback_query(F.data.startswith("sch:"))
async def choose_when(call: CallbackQuery, state: FSMContext, bot: Bot):
    _, msg_id, choice = call.data.split(":")
    msg_id = int(msg_id)
    if choice == "no":
        await call.message.edit_text("Ок, не публикую.")
        await call.answer()
        return
    if choice == "custom":
        await state.set_state(Custom.when)
        await state.update_data(msg_id=msg_id, preview=preview_of(call.message.reply_to_message))
        await call.message.edit_text("Напишите время: <code>18:30</code>, <code>27.10 18:30</code>, "
                                     "<code>завтра 10:00</code> или <code>через 2 часа</code>.")
        await call.answer()
        return
    when = preset(choice, db.now())
    if when is None:
        await call.answer()
        return
    await call.answer()
    text = await schedule(bot, call.from_user.id, call.message.chat.id, msg_id,
                          preview_of(call.message.reply_to_message), when)
    await call.message.edit_text(text)


@router.message(Custom.when, F.text)
async def custom_when(message: Message, state: FSMContext, bot: Bot):
    when = parse_when(message.text, db.now())
    if when is None:
        await message.answer("Не понял время 🤔 Примеры: <code>18:30</code>, <code>27.10 18:30</code>, "
                             "<code>через 2 часа</code>")
        return
    if when < db.now():
        await message.answer("Это время уже прошло. Напишите время в будущем.")
        return
    data = await state.get_data()
    await state.clear()
    await message.answer(await schedule(bot, message.from_user.id, message.chat.id,
                                        data["msg_id"], data["preview"], when))


@router.message(F.media_group_id)
async def album(message: Message):
    await message.answer("Альбомы из нескольких фото пока не поддерживаются — "
                         "пришлите одно фото или видео с подписью.")


@router.message(lambda m: not (m.text or "").startswith("/"))
async def new_post(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Когда опубликовать этот пост?", reply_markup=when_keyboard(message.message_id))
