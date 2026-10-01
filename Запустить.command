#!/bin/zsh
cd "$(dirname "$0")" || exit 1
export YOLO_CONFIG_DIR="$PWD/.yolo"
export MPLCONFIGDIR="$PWD/.matplotlib"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers"
fail() { echo "Не удалось выполнить шаг. Скопируй сообщение выше."; read "?Нажми Enter для закрытия..."; exit 1; }
if ! command -v python3 >/dev/null 2>&1; then
  echo "Установи Python 3 с https://www.python.org/downloads/macos/ и запусти файл снова."
  read "?Нажми Enter..."
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  echo "Первый запуск: устанавливаю библиотеки. Это займёт несколько минут."
  python3 -m venv .venv || fail
fi
if [[ ! -f .setup-complete ]]; then
  .venv/bin/python -m pip install -r requirements.txt || fail
  .venv/bin/python -m playwright install chromium || fail
  touch .setup-complete
fi
.venv/bin/python app.py
read "?Нажми Enter для закрытия..."
