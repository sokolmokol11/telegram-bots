"""
Клиентская часть ИИ-консультанта.

Обычный режим: каждое текстовое сообщение уходит нейросети вместе с базой знаний
и последними репликами диалога. Если нейросеть не знает ответа или клиенту нужен
человек, бот предлагает позвать менеджера.

Режим менеджера: сообщения клиента пересылаются админам, а их ответы
(через «Ответить» на пересланное сообщение) возвращаются клиенту.
"""
import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ai
import config
import db
import keyboards as kb

router = Router()
log = logging.getLogger(__name__)


class Operator(StatesGroup):
    chatting = State()  # клиент общается с живым менеджером


# ---------- Вспомогательные функции ----------

def split_answer(text: str) -> tuple[str, bool]:
    """Отделяет метку «нужен менеджер» от текста ответа."""
    need_manager = config.MANAGER_MARK in text
    clean = text.replace(config.MANAGER_MARK, "").strip()
    return clean, need_manager


def who(user) -> str:
    name = html.escape(user.full_name or "клиент")
    nick = f" @{user.username}" if user.username else ""
    return f"{name}{nick}, id {user.id}"


def dialog_excerpt(user_id: int) -> str:
    """Последние реплики с ИИ — чтобы менеджер понимал контекст."""
    lines = []
    for m in db.history(user_id, 4):
        who_ = "Клиент" if m["role"] == "user" else "Бот"
        text = m["content"] if len(m["content"]) <= 200 else m["content"][:200] + "…"
        lines.append(f"<i>{who_}:</i> {html.escape(text)}")
    return "\n".join(lines)


async def forward_to_admins(bot: Bot, message: Message) -> int:
    """Пересылает сообщение клиента всем админам. Возвращает, скольким доставлено."""
    header = f"💬 <b>Вопрос клиента</b> ({who(message.from_user)})"
    excerpt = dialog_excerpt(message.from_user.id)
    if excerpt:
        header += f"\n\nНедавний диалог с ботом:\n{excerpt}"
    footer = "\n\n↩️ <i>Ответьте на это сообщение (свайп влево → «Ответить») — ответ уйдёт клиенту.</i>"
    delivered = 0
    for admin_id in config.ADMIN_IDS:
        try:
            if message.text:
                sent = await bot.send_message(
                    admin_id, f"{header}\n\n<b>Сообщение:</b> {html.escape(message.text)}{footer}"
                )
                db.save_relay(admin_id, sent.message_id, message.from_user.id)
            else:  # фото, голосовое, файл — пересылаем копию
                head = await bot.send_message(admin_id, header + footer)
                copy = await bot.copy_message(admin_id, message.chat.id, message.message_id)
                db.save_relay(admin_id, head.message_id, message.from_user.id)
                db.save_relay(admin_id, copy.message_id, message.from_user.id)
            delivered += 1
        except Exception as e:
            log.warning("Не удалось переслать админу %s: %s", admin_id, e)
    if delivered:
        db.log_event("handoff", message.from_user.id)
    return delivered


# ---------- Меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    text = config.WELCOME_TEXT
    if config.DEMO_CONTACT:
        text += (
            f"\n\n🛠 <i>Это демо: {config.BOT_KIND}. Компания вымышленная, вопросы менеджеру "
            f"уходят разработчику. Хотите такого бота для своего бизнеса? Пишите: {config.DEMO_CONTACT}</i>"
        )
    await message.answer(text, reply_markup=kb.main_menu())


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш ID: <code>{message.from_user.id}</code>")


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message):
    await message.answer(f"<b>{config.BUSINESS_NAME}</b>\n\n{config.CONTACTS_TEXT}")


@router.message(F.text == kb.BTN_RESET)
async def reset(message: Message, state: FSMContext):
    await state.clear()
    db.clear_history(message.from_user.id)
    await message.answer("Начнём заново. Чем могу помочь?", reply_markup=kb.main_menu())


# ---------- Режим менеджера ----------

async def start_operator(message: Message, state: FSMContext) -> None:
    await state.set_state(Operator.chatting)
    await message.answer(config.OPERATOR_START_TEXT, reply_markup=kb.operator_exit())


@router.message(F.text == kb.BTN_MANAGER)
async def manager_btn(message: Message, state: FSMContext):
    await start_operator(message, state)


@router.callback_query(F.data == "call_manager")
async def manager_cb(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await start_operator(call.message, state)


@router.callback_query(F.data == "operator_exit")
async def operator_exit(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    await call.message.answer("Снова на связи консультант 🤖 Задавайте вопрос.", reply_markup=kb.main_menu())


@router.message(Operator.chatting)
async def to_manager(message: Message, bot: Bot):
    if await forward_to_admins(bot, message):
        await message.answer("✅ Передал менеджеру. Ответ придёт сюда, в этот чат.",
                             reply_markup=kb.operator_exit())
    else:
        await message.answer(f"Не получилось связаться с менеджером 😔 Позвоните нам:\n{config.CONTACTS_TEXT}")


# ---------- Ответы нейросети ----------

@router.message(F.text)
async def ask_ai(message: Message, bot: Bot):
    user_id = message.from_user.id
    question = message.text.strip()[:1000]
    if question.startswith("/"):
        await message.answer("Такой команды нет. Просто напишите вопрос обычным текстом.")
        return

    if not ai.enabled():
        await message.answer(config.FALLBACK_TEXT, reply_markup=kb.call_manager())
        return
    if db.questions_today(user_id) >= config.DAILY_LIMIT:
        await message.answer("На сегодня лимит вопросов консультанту исчерпан. "
                             "Могу передать вопрос менеджеру 👇", reply_markup=kb.call_manager())
        return

    await bot.send_chat_action(message.chat.id, "typing")
    messages = [{"role": "system", "content": config.system_prompt()}]
    messages += db.history(user_id, config.HISTORY_SIZE)
    messages.append({"role": "user", "content": question})

    try:
        raw = await ai.chat(messages)
    except ai.AIError as e:
        log.warning("Ошибка нейросети: %s", e)
        db.log_event("ai_error", user_id)
        await message.answer(config.FALLBACK_TEXT, reply_markup=kb.call_manager())
        return

    answer, need_manager = split_answer(raw)
    if not answer:
        answer = "Этот вопрос лучше уточнить у менеджера."
        need_manager = True
    db.add_message(user_id, "user", question)
    db.add_message(user_id, "assistant", answer)
    db.log_event("ai_answer", user_id)
    # parse_mode=None — текст нейросети отправляем как есть, без HTML-разметки
    await message.answer(answer, parse_mode=None,
                         reply_markup=kb.call_manager() if need_manager else None)


@router.message()
async def not_text(message: Message):
    await message.answer("Я понимаю только текстовые вопросы. "
                         "Если нужно отправить фото или голосовое — позовите менеджера 👇",
                         reply_markup=kb.call_manager())
