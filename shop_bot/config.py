"""
Настройки магазина цифровых товаров.

Товары и категории — ниже, в CATEGORIES и PRODUCTS.
Оплата — Telegram Stars (⭐): работает без ИП и платёжных договоров,
Telegram сам принимает оплату картой у покупателя.
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
BOT_KIND = "магазин с оплатой и автовыдачей"
# 1 — показывать кнопку «Тестовая оплата», чтобы посетители демо могли пройти покупку бесплатно
DEMO_PAYMENTS = os.getenv("DEMO_PAYMENTS", "0") == "1"
DB_PATH = BASE_DIR / "shop.db"

# ---------- Тексты ----------
SHOP_NAME = "Цифровой магазин «Пиксель»"
WELCOME_TEXT = (
    "Привет! Это магазин «Пиксель» 🟪\n\n"
    "Цифровые товары с моментальной выдачей: оплатили — и товар сразу в этом чате, "
    "в любое время суток."
)
SUPPORT_TEXT = "По любым вопросам пишите в поддержку: @support_example"
LOW_STOCK = 3  # предупреждать админа, когда кодов осталось столько или меньше

# ---------- Каталог ----------
CATEGORIES = [
    {"id": "games", "name": "🎮 Игры"},
    {"id": "guides", "name": "📚 Гайды и шаблоны"},
]

# type: "codes" — уникальный код каждому покупателю (ключи, промокоды, аккаунты);
#               коды загружаются админом командой /stock
#       "text"  — одинаковое содержимое всем (ссылка на скачивание, текст, доступ)
# price — цена в звёздах Telegram (⭐)
PRODUCTS = [
    {"id": "steam_random", "category": "games", "type": "codes", "price": 50,
     "name": "Случайный ключ Steam",
     "description": "Ключ случайной игры для Steam. Активация в клиенте Steam: «Игры → Активировать в Steam»."},
    {"id": "premium_7d", "category": "games", "type": "codes", "price": 30,
     "name": "Промокод на 7 дней премиума",
     "description": "Промокод на неделю премиум-доступа в игре. Действует 30 дней с момента покупки."},
    {"id": "notion_pack", "category": "guides", "type": "text", "price": 25,
     "name": "Шаблоны Notion для учёбы",
     "description": "12 шаблонов: расписание, трекер дедлайнов, конспекты, планер сессии.",
     "content": "Ваша ссылка на шаблоны: https://example.com/notion-pack\n"
                "Откройте её и нажмите «Duplicate» в правом верхнем углу."},
    {"id": "resume_guide", "category": "guides", "type": "text", "price": 40,
     "name": "Гайд: резюме без опыта",
     "description": "PDF-гайд на 20 страниц + 3 шаблона резюме для студентов.",
     "content": "Скачать гайд: https://example.com/resume-guide.pdf"},
]

# Демо-коды, которые бот сам добавит при первом запуске (чтобы в демо было что купить)
SEED_DEMO_STOCK = os.getenv("SEED_DEMO_STOCK", "1") == "1"


def get_product(product_id: str) -> dict | None:
    return next((p for p in PRODUCTS if p["id"] == product_id), None)


def get_category(category_id: str) -> dict | None:
    return next((c for c in CATEGORIES if c["id"] == category_id), None)
