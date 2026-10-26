"""
Расчёт расписания: рабочие дни, свободные окна, красивый вывод дат.
Здесь нет ничего от Telegram — чистая логика, её легко проверять.
"""
from datetime import date, datetime, timedelta

import config

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def now() -> datetime:
    """Текущее время в часовом поясе бизнеса (без tzinfo, как хранится в базе)."""
    return datetime.now(config.TZ).replace(tzinfo=None, second=0, microsecond=0)


def candidate_dates(days_off: set[str], current: datetime) -> list[date]:
    """Рабочие дни на ближайшие BOOKING_DAYS_AHEAD дней, кроме закрытых."""
    result = []
    for i in range(config.BOOKING_DAYS_AHEAD + 1):
        day = current.date() + timedelta(days=i)
        if day.weekday() in config.WORK_WEEKDAYS and day.isoformat() not in days_off:
            result.append(day)
    return result


def free_slots(
    day: date,
    duration_min: int,
    busy: list[tuple[datetime, datetime]],
    current: datetime,
) -> list[datetime]:
    """
    Все время начала, когда услуга длиной duration_min помещается в рабочий день
    и не пересекается ни с одной занятой записью.
    """
    duration = timedelta(minutes=duration_min)
    step = timedelta(minutes=config.SLOT_STEP_MINUTES)
    start = datetime.combine(day, config.WORK_START)
    day_end = datetime.combine(day, config.WORK_END)
    earliest = current + timedelta(hours=config.MIN_HOURS_BEFORE)

    slots = []
    t = start
    while t + duration <= day_end:
        end = t + duration
        overlaps = any(t < b_end and b_start < end for b_start, b_end in busy)
        if t >= earliest and not overlaps:
            slots.append(t)
        t += step
    return slots


def fmt_day(day: date) -> str:
    """Пн, 20.10"""
    return f"{WEEKDAYS[day.weekday()]}, {day:%d.%m}"


def fmt_dt(dt: datetime) -> str:
    """Пн, 20.10 в 14:30"""
    return f"{fmt_day(dt.date())} в {dt:%H:%M}"
