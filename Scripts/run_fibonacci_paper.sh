#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/cameronrichardson/PycharmProjects/PythonProject"
PYTHON="/Users/cameronrichardson/PycharmProjects/PythonProjects/bin/python"

LOCK_DIR="/tmp/cameron-fibonacci-paper.lock"
LOG_FILE="$PROJECT_DIR/logs/fibonacci-paper-launch.log"

RUN_DATE="$(TZ=America/New_York date +%F)"
COMPLETION_FILE="$PROJECT_DIR/logs/fibonacci-paper-complete-$RUN_DATE"

cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs"

{
  echo
  echo "========================================"
  echo "Fibonacci paper launch: $(date)"
  echo "Trading date: $RUN_DATE"
  echo "========================================"
} >> "$LOG_FILE"

if [[ -f "$COMPLETION_FILE" ]]; then
  echo "Paper check skipped: $RUN_DATE already completed." \
    | tee -a "$LOG_FILE"
  exit 0
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" \
    | tee -a "$LOG_FILE"
  exit 1
fi

echo "Checking NYSE trading calendar for $RUN_DATE..." \
  | tee -a "$LOG_FILE"

set +e
"$PYTHON" main.py market-day "$RUN_DATE" 2>&1 \
  | tee -a "$LOG_FILE"
MARKET_DAY_EXIT=${pipestatus[1]}
set -e

if [[ "$MARKET_DAY_EXIT" -eq 2 ]]; then
  echo "Paper check skipped: NYSE was closed." \
    | tee -a "$LOG_FILE"
  touch "$COMPLETION_FILE"
  exit 0
fi

if [[ "$MARKET_DAY_EXIT" -ne 0 ]]; then
  echo "Paper check failed: market calendar check failed." \
    | tee -a "$LOG_FILE"
  exit 1
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Paper check skipped: another paper process is running." \
    | tee -a "$LOG_FILE"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

export ALPACA_DATA_FEED="iex"
export PYTHONUNBUFFERED="1"

echo "Starting Fibonacci paper evaluation..." \
  | tee -a "$LOG_FILE"

"$PYTHON" main.py fibonacci-paper "$RUN_DATE" \
  --feed iex \
  --slippage-bps 15 2>&1 \
  | tee -a "$LOG_FILE"

touch "$COMPLETION_FILE"

echo "Publishing Fibonacci paper dashboard status..." \
  | tee -a "$LOG_FILE"

"$PYTHON" main.py fibonacci-paper-publish 2>&1 \
  | tee -a "$LOG_FILE"

echo "Fibonacci paper evaluation completed: $(date)" \
  | tee -a "$LOG_FILE"
