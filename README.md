# Telegram-боты: демо-проекты

## 1. Бот записи на услуги — папка `booking_bot`
Клиент сам выбирает услугу, день и свободное время из предложенных — и записан, без звонков.
Бот напоминает о визите за сутки, мастер управляет расписанием прямо в Telegram.
Для: маникюр, барберы, массаж, репетиторы — все, у кого есть расписание.
Пример в демо: студия маникюра «Лак» — @sokol_booking_demo_bot

## 2. Бот приёма заявок — папка `leads_bot`
Клиент считает примерную цену и оставляет заявку, менеджер перезванивает.
Заявки приходят менеджеру со статусами и складываются в Google Таблицу.
Для: клининг, ремонт, грузоперевозки, юристы — где цену и время обсуждают с человеком.
Пример в демо: клининг «Чистый дом» — @sokol_leads_demo_bot

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
