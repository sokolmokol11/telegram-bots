"""
База SQLite: корзины, склад кодов, заказы.
"""
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

import config


def now_str() -> str:
    return datetime.now(config.TZ).strftime("%Y-%m-%d %H:%M")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cart (
                user_id    INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                qty        INTEGER NOT NULL,
                PRIMARY KEY (user_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS stock (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                code       TEXT NOT NULL,
                order_id   INTEGER            -- NULL = не продан
            );
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                username   TEXT,
                items      TEXT NOT NULL,     -- JSON: [{"product_id", "qty", "price"}]
                total      INTEGER NOT NULL,  -- в звёздах
                status     TEXT NOT NULL,     -- pending / paid / refunded
                charge_id  TEXT,              -- id платежа Telegram (для возврата)
                delivered  TEXT,              -- JSON: {"product_id": ["код", ...] или "текст"}
                created_at TEXT NOT NULL,
                paid_at    TEXT
            );
            """
        )
    if config.SEED_DEMO_STOCK:
        with closing(_connect()) as conn:
            for p in config.PRODUCTS:
                if p["type"] != "codes":
                    continue
                exists = conn.execute("SELECT 1 FROM stock WHERE product_id = ?", (p["id"],)).fetchone()
                if not exists:
                    for _ in range(10):
                        code = "DEMO-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
                        conn.execute("INSERT INTO stock (product_id, code) VALUES (?, ?)", (p["id"], code))


# ---------- Склад ----------

def available(product_id: str) -> int:
    """Сколько можно купить: для кодов — остаток, для текстовых товаров — без ограничений."""
    product = config.get_product(product_id)
    if not product:
        return 0
    if product["type"] == "text":
        return 10**6
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM stock WHERE product_id = ? AND order_id IS NULL", (product_id,)
        ).fetchone()[0]


def add_stock(product_id: str, codes: list[str]) -> int:
    codes = [c.strip() for c in codes if c.strip()]
    with closing(_connect()) as conn:
        conn.executemany("INSERT INTO stock (product_id, code) VALUES (?, ?)",
                         [(product_id, c) for c in codes])
    return len(codes)


# ---------- Корзина ----------

def cart(user_id: int) -> list[dict]:
    """Позиции корзины с данными товара. Пропавшие из каталога товары отбрасываются."""
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT product_id, qty FROM cart WHERE user_id = ?", (user_id,)).fetchall()
    items = []
    for r in rows:
        product = config.get_product(r["product_id"])
        if product:
            items.append({"product": product, "qty": r["qty"], "sum": product["price"] * r["qty"]})
    return items


def cart_set(user_id: int, product_id: str, qty: int) -> None:
    with closing(_connect()) as conn:
        if qty <= 0:
            conn.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        else:
            conn.execute(
                "INSERT INTO cart VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, product_id) DO UPDATE SET qty = excluded.qty",
                (user_id, product_id, qty),
            )


def cart_qty(user_id: int, product_id: str) -> int:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT qty FROM cart WHERE user_id = ? AND product_id = ?",
                           (user_id, product_id)).fetchone()
    return row["qty"] if row else 0


def cart_clear(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))


# ---------- Заказы ----------

def _order(row) -> dict | None:
    if not row:
        return None
    o = dict(row)
    o["items"] = json.loads(o["items"])
    o["delivered"] = json.loads(o["delivered"]) if o["delivered"] else None
    return o


def create_order(user_id: int, username: str | None, items: list[dict]) -> dict:
    data = [{"product_id": i["product"]["id"], "qty": i["qty"], "price": i["product"]["price"]} for i in items]
    total = sum(i["sum"] for i in items)
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, username, items, total, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (user_id, username, json.dumps(data), total, now_str()),
        )
        return get_order(cur.lastrowid)


def get_order(order_id: int) -> dict | None:
    with closing(_connect()) as conn:
        return _order(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())


def order_in_stock(order: dict) -> bool:
    return all(available(i["product_id"]) >= i["qty"] for i in order["items"])


def fulfill(order_id: int, charge_id: str) -> dict | None:
    """
    Отмечает заказ оплаченным и выдаёт коды — одной транзакцией, чтобы один код
    не достался двоим. Возвращает заказ с выданным товаром или None, если кодов не хватило.
    Повторный вызов для уже оплаченного заказа просто возвращает его.
    """
    with closing(_connect()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            order = _order(conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone())
            if order is None:
                conn.execute("ROLLBACK")
                return None
            if order["status"] == "paid":
                conn.execute("ROLLBACK")
                return order
            delivered = {}
            for item in order["items"]:
                product = config.get_product(item["product_id"])
                if product is None:
                    conn.execute("ROLLBACK")
                    return None
                if product["type"] == "text":
                    delivered[product["id"]] = product["content"]
                    continue
                rows = conn.execute(
                    "SELECT id, code FROM stock WHERE product_id = ? AND order_id IS NULL ORDER BY id LIMIT ?",
                    (product["id"], item["qty"]),
                ).fetchall()
                if len(rows) < item["qty"]:
                    conn.execute("ROLLBACK")
                    return None
                conn.executemany("UPDATE stock SET order_id = ? WHERE id = ?",
                                 [(order_id, r["id"]) for r in rows])
                delivered[product["id"]] = [r["code"] for r in rows]
            conn.execute(
                "UPDATE orders SET status = 'paid', charge_id = ?, delivered = ?, paid_at = ? WHERE id = ?",
                (charge_id, json.dumps(delivered, ensure_ascii=False), now_str(), order_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return get_order(order_id)


def set_refunded(order_id: int, charge_id: str | None = None) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE orders SET status = 'refunded', charge_id = COALESCE(?, charge_id) WHERE id = ?",
                     (charge_id, order_id))


def user_orders(user_id: int, limit: int = 10) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status = 'paid' ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [_order(r) for r in rows]


def stats() -> dict:
    today = now_str()[:10]
    with closing(_connect()) as conn:
        paid = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders WHERE status = 'paid'"
        ).fetchone()
        paid_today = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders WHERE status = 'paid' "
            "AND substr(paid_at, 1, 10) = ?", (today,)
        ).fetchone()
    return {"orders": paid[0], "revenue": paid[1], "orders_today": paid_today[0], "revenue_today": paid_today[1]}
