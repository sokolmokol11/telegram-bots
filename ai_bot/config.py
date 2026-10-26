"""
Настройки ИИ-консультанта.

Под другой бизнес меняются: тексты ниже и файл knowledge.md (база знаний).
"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")


def _normalize_proxy(raw: str) -> str:
    """socks5://user:pass@host:port или socks5://host:port:user:pass → стандартный вид."""
    raw = raw.strip()
    if not raw:
        return ""
    scheme, _, rest = raw.partition("://")
    if not rest:
        scheme, rest = "socks5", raw
    if "@" not in rest and rest.count(":") == 3:
        host, port, user, password = rest.split(":")
        rest = f"{user}:{password}@{host}:{port}"
    return f"{scheme}://{rest}"


# ---------- Секретные настройки (файл .env) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
}
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))
PROXY = _normalize_proxy(os.getenv("PROXY", ""))
DEMO_CONTACT = os.getenv("DEMO_CONTACT", "").strip()
BOT_KIND = "ИИ-консультант"
DB_PATH = BASE_DIR / "ai_bot.db"

# Нейросеть. По умолчанию Groq — бесплатный тариф, ключ: https://console.groq.com/keys
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
AI_USE_PROXY = os.getenv("AI_USE_PROXY", "1") == "1"  # ходить к нейросети через PROXY

DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "30"))  # вопросов к ИИ на одного человека в день
HISTORY_SIZE = 8  # сколько последних сообщений диалога помнит ИИ

# ---------- Тексты ----------
BUSINESS_NAME = "Автосервис «Гараж 24»"
WELCOME_TEXT = (
    "Здравствуйте! Я онлайн-консультант автосервиса «Гараж 24» 🚗\n\n"
    "Спросите что угодно: цены, сроки, запись, гарантия, адрес — отвечу сразу, "
    "в любое время. Если вопрос сложный — позову живого менеджера."
)
OPERATOR_START_TEXT = (
    "Напишите ваш вопрос одним сообщением — менеджер ответит здесь же, в этом чате. "
    "Обычно в течение 15 минут в рабочее время."
)
CONTACTS_TEXT = (
    "📍 Санкт-Петербург, ул. Примерная, 24 (вход со двора)\n"
    "🕘 Ежедневно, 9:00–21:00\n"
    "📞 +7 (900) 000-00-24"
)
FALLBACK_TEXT = "Не смог ответить прямо сейчас. Хотите, передам вопрос менеджеру?"

KNOWLEDGE_FILE = BASE_DIR / "knowledge.md"
MANAGER_MARK = "[MANAGER]"


def system_prompt() -> str:
    knowledge = KNOWLEDGE_FILE.read_text(encoding="utf-8") if KNOWLEDGE_FILE.exists() else ""
    return (
        f"Ты — вежливый онлайн-консультант компании «{BUSINESS_NAME}». "
        "Отвечай по-русски, коротко (1–4 предложения), дружелюбно, без markdown и без списков из звёздочек. "
        "Используй ТОЛЬКО факты из базы знаний ниже, ничего не выдумывай: ни цен, ни скидок, ни сроков. "
        "Если ответа нет в базе знаний, клиент хочет записаться, согласовать точную цену, "
        "жалуется или просит человека — ответь коротко и добавь в самом конце метку "
        f"{MANAGER_MARK}. Не рассказывай, что ты нейросеть и что у тебя есть база знаний.\n\n"
        f"БАЗА ЗНАНИЙ:\n{knowledge}"
    )
