"""
Запись заявок в Google Таблицу через сервисный аккаунт (библиотека gspread).

Если таблица не настроена или Google недоступен, бот продолжает работать:
заявки всё равно сохраняются в базе и приходят админу.
Как настроить — см. README.md, раздел «Google Таблица».
"""
import asyncio
import logging

import config

log = logging.getLogger(__name__)

HEADERS = ["№", "Дата", "Статус", "Telegram"] + [q["label"] for q in config.FORM]

_worksheet = None


def enabled() -> bool:
    return bool(config.GOOGLE_SHEET_ID)


def _get_worksheet():
    """Подключается к таблице один раз и запоминает лист."""
    global _worksheet
    if _worksheet is None:
        import gspread  # импорт здесь, чтобы бот запускался и без этой библиотеки

        client = gspread.service_account(filename=config.GOOGLE_CREDENTIALS)
        ws = client.open_by_key(config.GOOGLE_SHEET_ID).sheet1
        if not ws.row_values(1):
            ws.append_row(HEADERS)
        _worksheet = ws
    return _worksheet


def lead_to_row(lead: dict) -> list:
    tg = f"@{lead['username']}" if lead.get("username") else str(lead["user_id"])
    return [lead["id"], lead["created_at"], config.STATUSES[lead["status"]], tg] + [
        lead["answers"].get(q["key"], "") for q in config.FORM
    ]


def _append(lead: dict) -> None:
    _get_worksheet().append_row(lead_to_row(lead), value_input_option="USER_ENTERED")


def _update_status(lead_id: int, status: str) -> None:
    ws = _get_worksheet()
    cell = ws.find(str(lead_id), in_column=1)
    if cell:
        ws.update_cell(cell.row, 3, config.STATUSES[status])


async def append_lead(lead: dict) -> None:
    if not enabled():
        return
    try:
        # gspread работает синхронно — выносим в отдельный поток, чтобы бот не «замирал»
        await asyncio.to_thread(_append, lead)
    except Exception:
        log.exception("Не удалось записать заявку №%s в Google Таблицу", lead["id"])


async def update_status(lead_id: int, status: str) -> None:
    if not enabled():
        return
    try:
        await asyncio.to_thread(_update_status, lead_id, status)
    except Exception:
        log.exception("Не удалось обновить статус заявки №%s в Google Таблице", lead_id)
