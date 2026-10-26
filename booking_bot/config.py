"""
Настройки бота.

Чтобы сделать бота для другого бизнеса (репетитор, барбершоп, массаж),
почти всегда достаточно поменять только этот файл.
"""
import os
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent


def _load_env(path: Path) -> None:
    """Читает файл .env (строки вида КЛЮЧ=значение) в переменные окружения."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")

# ---------- Секретные настройки (берутся из файла .env) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# ID администраторов через запятую. Свой ID можно узнать командой /myid в боте.
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
}
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))


def _normalize_proxy(raw: str) -> str:
    """
    Прокси для доступа к Telegram (нужен, если сервер в России).
    Понимает оба формата:
      socks5://user:pass@host:port   — стандартный
      socks5://host:port:user:pass   — как часто выдают продавцы прокси
    """
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


PROXY = _normalize_proxy(os.getenv("PROXY", ""))

# Контакт разработчика для демо-версии (например @username).
# Если задан — бот в приветствии пишет, что он демонстрационный.
# Для бота заказчика оставьте пустым.
DEMO_CONTACT = os.getenv("DEMO_CONTACT", "").strip()
DB_PATH = BASE_DIR / "bookings.db"

# ---------- Настройки бизнеса ----------
BUSINESS_NAME = "Студия маникюра «Лак»"
WELCOME_TEXT = (
    "Здравствуйте! 💅 Я бот студии маникюра «Лак».\n\n"
    "Помогу записаться к мастеру за минуту: выберите услугу, день и удобное время."
)
CONTACTS_TEXT = (
    "📍 Санкт-Петербург, ул. Примерная, 10\n"
    "🕙 Пн–Сб, 10:00–20:00\n"
    "📞 +7 (900) 000-00-00"
)

# Услуги: id (латиницей, без пробелов), название, цена в рублях, длительность в минутах
SERVICES = [
    {"id": "classic", "name": "Классический маникюр", "price": 1200, "minutes": 60},
    {"id": "gel", "name": "Маникюр + гель-лак", "price": 2000, "minutes": 90},
    {"id": "design", "name": "Гель-лак + дизайн", "price": 2500, "minutes": 120},
    {"id": "removal", "name": "Снятие покрытия", "price": 500, "minutes": 30},
]

WORK_START = time(10, 0)           # начало рабочего дня
WORK_END = time(20, 0)             # конец рабочего дня (услуга должна закончиться до него)
WORK_WEEKDAYS = {0, 1, 2, 3, 4, 5}  # рабочие дни: 0 = понедельник ... 6 = воскресенье
SLOT_STEP_MINUTES = 30             # шаг, с которым показываются свободные окна
BOOKING_DAYS_AHEAD = 14            # на сколько дней вперёд можно записаться
MIN_HOURS_BEFORE = 2               # минимум часов от «сейчас» до записи
REMIND_HOURS_BEFORE = 24           # за сколько часов напомнить клиенту


def get_service(service_id: str) -> dict | None:
    for service in SERVICES:
        if service["id"] == service_id:
            return service
    return None
