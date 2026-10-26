#!/usr/bin/env bash
# Ставит бота на сервер (Ubuntu/Debian или AlmaLinux/Rocky) как службу: работает 24/7,
# сам перезапускается при сбое и после перезагрузки сервера.
#
# Использование (рядом должна лежать папка <имя> или архив <имя>.zip):
#   bash install.sh booking_bot
#   bash install.sh leads_bot
#
# Повторный запуск обновляет код бота, не трогая .env и базу данных.
set -euo pipefail

NAME="${1:?Укажите имя бота, например: bash install.sh booking_bot}"
ZIP="$NAME.zip"
DIR="/opt/bots/$NAME"
SERVICE="bot-$NAME"

[ -d "$NAME" ] || [ -f "$ZIP" ] || { echo "Не найдена папка $NAME или архив $ZIP в текущей папке"; exit 1; }

echo "==> Ставлю Python и нужные пакеты (один раз, может занять пару минут)"
if command -v apt-get >/dev/null 2>&1; then          # Ubuntu / Debian
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip unzip nano >/dev/null
  PY=python3
elif command -v dnf >/dev/null 2>&1; then            # AlmaLinux / Rocky / CentOS 8+
  # системный python3 здесь старый (3.6) — ставим 3.11 рядом, системный не трогаем
  dnf install -y -q python3.11 python3.11-pip unzip nano >/dev/null
  PY=python3.11
else
  echo "Не знаю, как ставить пакеты на этой системе (нет ни apt-get, ни dnf)"; exit 1
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "Нужен Python 3.10 или новее, а $PY старше"; exit 1; }

echo "==> Копирую код в $DIR"
mkdir -p "$DIR"
if [ -d "$NAME" ]; then                       # папка (например, из git clone)
  cp -r "$NAME/." "$DIR/"
else                                          # или zip-архив
  TMP="$(mktemp -d)"
  unzip -q -o "$ZIP" -d "$TMP"
  cp -r "$TMP/$NAME/." "$DIR/"
  rm -rf "$TMP"
fi
# в исходниках нет .env и базы, поэтому при обновлении они не перезапишутся

echo "==> Создаю виртуальное окружение и ставлю библиотеки"
[ -d "$DIR/venv" ] || "$PY" -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"

if [ ! -f "$DIR/.env" ]; then
  if [ -f "$DIR/.env.example" ]; then
    cp "$DIR/.env.example" "$DIR/.env"
  else  # на случай, если файл с точкой в начале имени потерялся при загрузке
    printf 'BOT_TOKEN=1234567890:AAAA\nADMIN_IDS=\nTIMEZONE=Europe/Moscow\nPROXY=\nDEMO_CONTACT=\n' > "$DIR/.env"
  fi
fi

echo "==> Регистрирую службу $SERVICE"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Telegram bot $NAME
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1

if grep -q "^BOT_TOKEN=1234567890" "$DIR/.env"; then
  echo
  echo "Готово почти: осталось вписать токен."
  echo "  1) nano $DIR/.env       (вписать BOT_TOKEN, сохранить: Ctrl+O, Enter, Ctrl+X)"
  echo "  2) systemctl restart $SERVICE"
else
  systemctl restart "$SERVICE"
  sleep 3
  echo
  systemctl --no-pager --lines=5 status "$SERVICE" || true
fi
