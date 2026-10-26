# Telegram-боты: демо-проекты

| Бот | Что делает | Демо |
|---|---|---|
| [booking_bot](booking_bot) | онлайн-запись на услуги: свободные окна, напоминания, админка мастера | @Lakstudiodemobot |
| [leads_bot](leads_bot) | приём заявок: калькулятор стоимости, анкета, статусы, Google Таблица | @CleaningServicesDemobot |

Стек: Python 3.10+, aiogram 3, SQLite.

## Установка на сервер

```bash
git clone https://github.com/<аккаунт>/<репозиторий>.git bots
cd bots
bash install.sh booking_bot
bash install.sh leads_bot
nano /opt/bots/booking_bot/.env    # BOT_TOKEN, PROXY, DEMO_CONTACT
nano /opt/bots/leads_bot/.env
systemctl restart bot-booking_bot bot-leads_bot
```

Обновление: `cd bots && git pull && bash install.sh booking_bot && bash install.sh leads_bot`
(токены и базы сохраняются).

Логи: `journalctl -u bot-leads_bot -n 50`
