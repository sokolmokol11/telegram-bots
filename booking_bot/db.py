"""
Работа с базой данных SQLite (один файл bookings.db рядом с ботом).
"""
import sqlite3
from contextlib import closing
from datetime import date, datetime

import config

FMT = "%Y-%m-%d %H:%M"


def to_str(dt: datetime) -> str:
    return dt.strftime(FMT)


def from_str(s: str) -> datetime:
    return datetime.strptime(s, FMT)


def _connect() -> sqlite3.Connection:
    # isolation_level=None — каждая команда сохраняется сразу,
    # транзакции открываем вручную там, где это важно
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with closing(_connect()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                username     TEXT,
                client_name  TEXT NOT NULL,
                phone        TEXT NOT NULL,
                service_id   TEXT NOT NULL,
                service_name TEXT NOT NULL,
                price        INTEGER NOT NULL,
                start_at     TEXT NOT NULL,
                end_at       TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'active',  -- active / cancelled
                reminded     INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_start ON appointments(start_at);
            CREATE TABLE IF NOT EXISTS days_off (day TEXT PRIMARY KEY);
            """
        )


# ---------- Записи ----------

def busy_intervals(day: date) -> list[tuple[datetime, datetime]]:
    """Занятые промежутки времени в выбранный день."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT start_at, end_at FROM appointments "
            "WHERE status = 'active' AND substr(start_at, 1, 10) = ?",
            (day.isoformat(),),
        ).fetchall()
    return [(from_str(r["start_at"]), from_str(r["end_at"])) for r in rows]


def add_appointment(
    user_id: int,
    username: str | None,
    client_name: str,
    phone: str,
    service: dict,
    start: datetime,
    end: datetime,
    reminded: bool,
) -> int | None:
    """
    Создаёт запись. Если время уже кто-то занял — возвращает None.
    Проверка и запись идут в одной транзакции, чтобы два человека
    не записались на одно время одновременно.
    """
    with closing(_connect()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            clash = conn.execute(
                "SELECT 1 FROM appointments "
                "WHERE status = 'active' AND start_at < ? AND end_at > ?",
                (to_str(end), to_str(start)),
            ).fetchone()
            if clash:
                conn.execute("ROLLBACK")
                return None
            cur = conn.execute(
                "INSERT INTO appointments (user_id, username, client_name, phone, "
                "service_id, service_name, price, start_at, end_at, reminded, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id, username, client_name, phone,
                    service["id"], service["name"], service["price"],
                    to_str(start), to_str(end), int(reminded),
                    to_str(datetime.now()),
                ),
            )
            conn.execute("COMMIT")
            return cur.lastrowid
        except Exception:
            conn.execute("ROLLBACK")
            raise


def get_appointment(appt_id: int) -> sqlite3.Row | None:
    with closing(_connect()) as conn:
        return conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()


def cancel_appointment(appt_id: int) -> bool:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ? AND status = 'active'",
            (appt_id,),
        )
        return cur.rowcount > 0


def user_upcoming(user_id: int, current: datetime) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM appointments WHERE user_id = ? AND status = 'active' "
            "AND start_at >= ? ORDER BY start_at",
            (user_id, to_str(current)),
        ).fetchall()


def appointments_between(start: datetime, end: datetime) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM appointments WHERE status = 'active' "
            "AND start_at >= ? AND start_at < ? ORDER BY start_at",
            (to_str(start), to_str(end)),
        ).fetchall()


def last_contacts(user_id: int) -> sqlite3.Row | None:
    """Имя и телефон из последней записи клиента — чтобы не спрашивать снова."""
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT client_name, phone FROM appointments WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()


# ---------- Напоминания ----------

def due_reminders(current: datetime, until: datetime) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM appointments WHERE status = 'active' AND reminded = 0 "
            "AND start_at > ? AND start_at <= ?",
            (to_str(current), to_str(until)),
        ).fetchall()


def mark_reminded(appt_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE appointments SET reminded = 1 WHERE id = ?", (appt_id,))


# ---------- Выходные дни ----------

def days_off() -> set[str]:
    with closing(_connect()) as conn:
        return {r["day"] for r in conn.execute("SELECT day FROM days_off")}


def toggle_day_off(day: str) -> bool:
    """Закрывает день, если он открыт, и наоборот. Возвращает True, если день теперь закрыт."""
    with closing(_connect()) as conn:
        if conn.execute("SELECT 1 FROM days_off WHERE day = ?", (day,)).fetchone():
            conn.execute("DELETE FROM days_off WHERE day = ?", (day,))
            return False
        conn.execute("INSERT INTO days_off (day) VALUES (?)", (day,))
        return True
