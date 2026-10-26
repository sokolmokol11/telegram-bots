"""
База SQLite: история диалогов, счётчик вопросов, связка «сообщение у менеджера → клиент».
"""
import sqlite3
from contextlib import closing
from datetime import datetime

import config


def now() -> datetime:
    return datetime.now(config.TZ).replace(tzinfo=None)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role    TEXT NOT NULL,        -- user / assistant
                content TEXT NOT NULL,
                ts      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id, id);
            CREATE TABLE IF NOT EXISTS relay (
                admin_chat_id INTEGER NOT NULL,
                admin_msg_id  INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                PRIMARY KEY (admin_chat_id, admin_msg_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                kind TEXT NOT NULL,           -- ai_answer / handoff / ai_error
                user_id INTEGER,
                ts   TEXT NOT NULL
            );
            """
        )


# ---------- История диалога ----------

def add_message(user_id: int, role: str, content: str) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (user_id, role, content, now().isoformat(timespec="seconds")),
        )


def history(user_id: int, limit: int) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


def questions_today(user_id: int) -> int:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id = ? AND role = 'user' AND substr(ts, 1, 10) = ?",
            (user_id, now().date().isoformat()),
        ).fetchone()[0]


# ---------- Пересылка менеджеру ----------

def save_relay(admin_chat_id: int, admin_msg_id: int, user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO relay VALUES (?, ?, ?)", (admin_chat_id, admin_msg_id, user_id)
        )


def relay_target(admin_chat_id: int, admin_msg_id: int) -> int | None:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT user_id FROM relay WHERE admin_chat_id = ? AND admin_msg_id = ?",
            (admin_chat_id, admin_msg_id),
        ).fetchone()
    return row["user_id"] if row else None


# ---------- Статистика ----------

def log_event(kind: str, user_id: int | None = None) -> None:
    with closing(_connect()) as conn:
        conn.execute("INSERT INTO events VALUES (?, ?, ?)", (kind, user_id, now().isoformat(timespec="seconds")))


def stats() -> dict:
    today = now().date().isoformat()
    with closing(_connect()) as conn:
        users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM messages").fetchone()[0]
        rows = conn.execute(
            "SELECT kind, COUNT(*), SUM(substr(ts, 1, 10) = ?) FROM events GROUP BY kind", (today,)
        ).fetchall()
    by_kind = {r[0]: (r[1], r[2] or 0) for r in rows}
    return {"users": users, "events": by_kind}
