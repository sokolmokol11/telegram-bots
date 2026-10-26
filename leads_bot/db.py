"""
База данных SQLite (файл leads.db рядом с ботом).
Ответы анкеты хранятся как JSON — так анкету можно менять в config.py,
не трогая структуру базы.
"""
import json
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                username   TEXT,
                answers    TEXT NOT NULL,           -- ответы анкеты в JSON
                status     TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL
            )
            """
        )


def _row_to_dict(row: sqlite3.Row) -> dict:
    lead = dict(row)
    lead["answers"] = json.loads(lead["answers"])
    return lead


def add_lead(user_id: int, username: str | None, answers: dict) -> dict:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO leads (user_id, username, answers, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, json.dumps(answers, ensure_ascii=False), now_str()),
        )
        return get_lead(cur.lastrowid)


def get_lead(lead_id: int) -> dict | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return _row_to_dict(row) if row else None


def set_status(lead_id: int, status: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))


def recent(limit: int = 10) -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def all_leads() -> list[dict]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def stats() -> dict:
    """Количество заявок по статусам + за сегодня."""
    today = now_str()[:10]
    with closing(_connect()) as conn:
        by_status = dict(conn.execute("SELECT status, COUNT(*) FROM leads GROUP BY status").fetchall())
        today_count = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()[0]
    return {"by_status": by_status, "today": today_count, "total": sum(by_status.values())}
