"""
Разбор времени публикации, которое админ пишет текстом.

Понимает: «18:30» (сегодня, а если уже прошло — завтра), «27.10 18:30»,
«27.10.2026 18:30», «завтра 10:00», «через 2 часа», «через 30 минут».
"""
import re
from datetime import datetime, timedelta

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def parse_when(text: str, now: datetime) -> datetime | None:
    t = text.strip().lower().replace("ё", "е")

    m = re.fullmatch(r"через\s+(\d{1,3})\s*(мин\w*|м|час\w*|ч)", t)
    if m:
        n = int(m.group(1))
        delta = timedelta(minutes=n) if m.group(2).startswith("м") else timedelta(hours=n)
        return now + delta

    m = re.fullmatch(r"(завтра\s+)?(\d{1,2})[:.](\d{2})", t)
    if m:
        hour, minute = int(m.group(2)), int(m.group(3))
        if hour > 23 or minute > 59:
            return None
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if m.group(1) or result <= now:
            result += timedelta(days=1)
        return result

    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s+(\d{1,2})[:.](\d{2})", t)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        try:
            result = datetime(year, month, day, int(m.group(4)), int(m.group(5)))
        except ValueError:
            return None
        if not m.group(3) and result < now - timedelta(days=1):
            result = result.replace(year=year + 1)  # «05.01» в декабре — это следующий год
        return result

    return None


def preset(name: str, now: datetime) -> datetime | None:
    if name == "now":
        return now
    if name == "1h":
        return now + timedelta(hours=1)
    if name == "evening":
        result = now.replace(hour=19, minute=0, second=0, microsecond=0)
        return result if result > now else result + timedelta(days=1)
    if name == "morning":
        return (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return None


def fmt(dt: datetime) -> str:
    return f"{WEEKDAYS[dt.weekday()]}, {dt:%d.%m} в {dt:%H:%M}"
