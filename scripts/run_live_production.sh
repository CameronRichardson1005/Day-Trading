#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/cameronrichardson/PycharmProjects/PythonProject"
PYTHON="/Users/cameronrichardson/PycharmProjects/PythonProjects/bin/python"
LOCK_DIR="/tmp/cameron-day-trading-bot.lock"
LOG_FILE="$PROJECT_DIR/logs/production-launch.log"
RUN_DATE="$(TZ=America/New_York date +%F)"
COMPLETION_FILE="$PROJECT_DIR/logs/live-complete-$RUN_DATE"

cd "$PROJECT_DIR"

if [[ -f "$COMPLETION_FILE" ]]; then
  echo "Production launch skipped: $RUN_DATE already completed." \
    | tee -a "$LOG_FILE"
  exit 0
fi

echo "Checking NYSE trading calendar for $RUN_DATE..." \
  | tee -a "$LOG_FILE"

set +e
"$PYTHON" main.py market-day "$RUN_DATE" 2>&1 \
  | tee -a "$LOG_FILE"
MARKET_DAY_EXIT=${pipestatus[1]}
set -e

if [[ "$MARKET_DAY_EXIT" -eq 2 ]]; then
  echo "Production launch skipped: NYSE is closed today." \
    | tee -a "$LOG_FILE"
  exit 0
fi

if [[ "$MARKET_DAY_EXIT" -ne 0 ]]; then
  echo "Production launch failed: market calendar check failed." \
    | tee -a "$LOG_FILE"
  exit 1
fi

{
  echo
  echo "========================================"
  echo "Production launch: $(date)"
  echo "========================================"
} >> "$LOG_FILE"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Bot launch skipped: another process is already running." \
    | tee -a "$LOG_FILE"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" \
    | tee -a "$LOG_FILE"
  exit 1
fi

export ALPACA_DATA_FEED="sip"
export PYTHONUNBUFFERED="1"

echo "Running production preflight..." \
  | tee -a "$LOG_FILE"

"$PYTHON" main.py preflight 2>&1 \
  | tee -a "$LOG_FILE"

echo "Starting live trading-data workflow..." \
  | tee -a "$LOG_FILE"

"$PYTHON" main.py live 2>&1 \
  | tee -a "$LOG_FILE"

touch "$COMPLETION_FILE"

echo "Production workflow finished: $(date)" \
  | tee -a "$LOG_FILE"
