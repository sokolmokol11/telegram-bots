"""
Настройки бота для канала: отложенный постинг + модерация чата.
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
BOT_KIND = "бот для канала: автопостинг и модерация чата"
DB_PATH = BASE_DIR / "channel_bot.db"

# Канал для публикаций: @username или числовой id вида -100...
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
# Ссылка на чат для демо (необязательно) — бот покажет её посетителям
DEMO_CHAT_LINK = os.getenv("DEMO_CHAT_LINK", "").strip()

# Нейросеть. По умолчанию GigaChat (Сбер): работает из России, у физлиц бесплатный лимит на год.
# AI_PROVIDER: gigachat — GigaChat; openai — любой OpenAI-совместимый API (DeepSeek, OpenRouter...)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gigachat").strip().lower()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.giga.chat/v1")
AI_MODEL = os.getenv("AI_MODEL", "GigaChat-2")
AI_SCOPE = os.getenv("AI_SCOPE", "GIGACHAT_API_PERS")  # для физлиц; для ИП/юрлиц — GIGACHAT_API_B2B
AI_USE_PROXY = os.getenv("AI_USE_PROXY", "0") == "1"  # 1 — ходить к нейросети через PROXY
# Сертификат НУЦ Минцифры (нужен для GigaChat), лежит рядом с ботом
AI_CA_FILE = BASE_DIR / "russian_trusted_root_ca.crt"

# ---------- Модерация чата ----------
DELETE_LINKS = True          # удалять ссылки от обычных участников
AI_MODERATION = True         # проверять сообщения нейросетью на спам (если задан AI_API_KEY)
AI_MIN_LENGTH = 20           # короткие сообщения нейросетью не проверяем
MAX_WARNINGS = 3             # после стольких нарушений — мут
MUTE_HOURS = 1               # на сколько часов мут
DELETE_JOIN_MESSAGES = True  # удалять служебные «X вступил(а) в группу»
WELCOME_TEXT = "Привет, {name}! 👋 Добро пожаловать в чат. Без рекламы и ссылок, пожалуйста 🙂"
STOP_WORDS = [
    "заработок в интернете", "пассивный доход", "пиши в лс", "пишите в лс",
    "казино", "ставки на спорт", "крипта x10", "раздача", "18+",
]
