"""
База SQLite: очередь постов, предупреждения участников, журнал модерации.
"""
import sqlite3
from contextlib import closing
from datetime import datetime

import config

FMT = "%Y-%m-%d %H:%M"


def now() -> datetime:
    return datetime.now(config.TZ).replace(tzinfo=None, second=0, microsecond=0)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                created_by     INTEGER NOT NULL,
                from_chat_id   INTEGER NOT NULL,   -- откуда копировать (чат админа с ботом)
                message_id     INTEGER NOT NULL,
                preview        TEXT NOT NULL,
                publish_at     TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled/published/cancelled/failed
                channel_msg_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count   INTEGER NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS mod_log (
                ts      TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action  TEXT NOT NULL,   -- deleted / muted
                reason  TEXT NOT NULL
            );
            """
        )


# ---------- Посты ----------

def add_post(created_by: int, from_chat_id: int, message_id: int, preview: str, publish_at: datetime) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO posts (created_by, from_chat_id, message_id, preview, publish_at) VALUES (?, ?, ?, ?, ?)",
            (created_by, from_chat_id, message_id, preview, publish_at.strftime(FMT)),
        )
        return cur.lastrowid


def due_posts(moment: datetime) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' AND publish_at <= ? ORDER BY publish_at",
            (moment.strftime(FMT),),
        ).fetchall()


def scheduled() -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' ORDER BY publish_at"
        ).fetchall()


def set_post_status(post_id: int, status: str, channel_msg_id: int | None = None) -> bool:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "UPDATE posts SET status = ?, channel_msg_id = COALESCE(?, channel_msg_id) "
            "WHERE id = ? AND status = 'scheduled'",
            (status, channel_msg_id, post_id),
        )
        return cur.rowcount > 0


def post_counts() -> dict:
    with closing(_connect()) as conn:
        return dict(conn.execute("SELECT status, COUNT(*) FROM posts GROUP BY status").fetchall())


# ---------- Модерация ----------

def add_warning(chat_id: int, user_id: int) -> int:
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO warnings VALUES (?, ?, 1) "
            "ON CONFLICT(chat_id, user_id) DO UPDATE SET count = count + 1",
            (chat_id, user_id),
        )
        return conn.execute("SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
                            (chat_id, user_id)).fetchone()[0]


def reset_warnings(chat_id: int, user_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))


def log_action(chat_id: int, user_id: int, action: str, reason: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("INSERT INTO mod_log VALUES (?, ?, ?, ?, ?)",
                     (now().strftime(FMT), chat_id, user_id, action, reason))


def mod_stats() -> dict:
    today = now().strftime("%Y-%m-%d")
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT action, COUNT(*), SUM(substr(ts, 1, 10) = ?) FROM mod_log GROUP BY action", (today,)
        ).fetchall()
    return {r[0]: (r[1], r[2] or 0) for r in rows}
