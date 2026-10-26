"""
Настройки бота приёма заявок.

Под другой бизнес (ремонт, автосервис, юрист, курсы) обычно меняется
только этот файл: тексты, услуги калькулятора, вопросы анкеты, FAQ.
"""
import os
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

# ---------- Секретные настройки (файл .env) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
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
DB_PATH = BASE_DIR / "leads.db"

# Google Таблица (необязательно). Если не заполнено — бот работает без неё.
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", str(BASE_DIR / "credentials.json"))

# ---------- Тексты ----------
BUSINESS_NAME = "Клининг «Чистый дом»"
WELCOME_TEXT = (
    "Здравствуйте! Я бот клининговой компании «Чистый дом» 🧽\n\n"
    "Посчитаю стоимость уборки за 10 секунд и приму заявку — "
    "менеджер перезвонит и всё уточнит."
)
CONTACTS_TEXT = (
    "📍 Санкт-Петербург и Ленобласть\n"
    "🕘 Ежедневно, 9:00–21:00\n"
    "📞 +7 (900) 000-00-00"
)
DONE_TEXT = (
    "Менеджер свяжется с вами в течение 15 минут (в рабочее время 9:00–21:00)."
)

# ---------- Калькулятор ----------
# Цена = площадь × цена за м², но не меньше минимальной стоимости
CALC_SERVICES = [
    {"id": "regular", "name": "Поддерживающая уборка", "per_m2": 60, "min": 2500},
    {"id": "general", "name": "Генеральная уборка", "per_m2": 120, "min": 5000},
    {"id": "repair", "name": "Уборка после ремонта", "per_m2": 180, "min": 7000},
]
CALC_NOTE = "Точную стоимость менеджер подтвердит после уточнения деталей."

# ---------- Анкета заявки ----------
# type: choice — кнопки; text — любой текст; number — число; phone — телефон
# optional: True — вопрос можно пропустить
FORM = [
    {"key": "service", "label": "Услуга", "type": "choice",
     "text": "Какая уборка нужна?",
     "options": [s["name"] for s in CALC_SERVICES] + ["Другое"]},
    {"key": "area", "label": "Площадь, м²", "type": "number",
     "text": "Какая площадь помещения в м²? Напишите число, например 54."},
    {"key": "address", "label": "Адрес / район", "type": "text",
     "text": "Укажите район или адрес."},
    {"key": "date", "label": "Когда удобно", "type": "text",
     "text": "Когда удобно провести уборку? Например: «в субботу утром»."},
    {"key": "name", "label": "Имя", "type": "text",
     "text": "Как к вам обращаться?"},
    {"key": "phone", "label": "Телефон", "type": "phone",
     "text": "Оставьте телефон: нажмите кнопку ниже или напишите номер."},
    {"key": "comment", "label": "Комментарий", "type": "text", "optional": True,
     "text": "Есть пожелания? Напишите или нажмите «Пропустить»."},
]

# ---------- Частые вопросы ----------
FAQ = [
    ("Нужно ли что-то готовить к приезду?",
     "Нет. Клинеры привозят всё с собой: химию, инвентарь, пылесос."),
    ("Какие средства вы используете?",
     "Профессиональную химию, безопасную для детей и животных."),
    ("Сколько длится уборка?",
     "Поддерживающая квартиры до 50 м² — около 3 часов, генеральная — 5–7 часов."),
    ("Как оплатить?",
     "Наличными или переводом после уборки, когда вы всё проверите."),
]

# ---------- Статусы заявки ----------
STATUSES = {
    "new": "🆕 Новая",
    "work": "🔧 В работе",
    "done": "✅ Выполнена",
    "rejected": "❌ Отказ",
}
# Сообщения клиенту при смене статуса (статусы без текста клиенту не пишут)
CLIENT_STATUS_TEXT = {
    "work": "Ваша заявка №{id} взята в работу 👍 Скоро свяжемся с вами.",
}


def get_calc_service(service_id: str) -> dict | None:
    return next((s for s in CALC_SERVICES if s["id"] == service_id), None)


def calc_price(service: dict, area: float) -> int:
    return max(service["min"], round(area * service["per_m2"]))
