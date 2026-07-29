#!/bin/zsh

set -u

PROJECT_DIR="/Users/cameronrichardson/PycharmProjects/PythonProject"
PYTHON="/Users/cameronrichardson/PycharmProjects/PythonProjects/bin/python"
LAUNCH_LABEL="com.cameron.tradingbot.live"
LAUNCH_DOMAIN="gui/$(id -u)"
LAUNCH_PLIST="$HOME/Library/LaunchAgents/$LAUNCH_LABEL.plist"
PRODUCTION_SCRIPT="$PROJECT_DIR/Scripts/run_live_production.sh"
LOG_FILE="$PROJECT_DIR/logs/production-launch.log"
LOCK_DIR="/tmp/cameron-day-trading-bot.lock"
RUN_DATE="$(TZ=America/New_York date +%F)"
COMPLETION_FILE="$PROJECT_DIR/logs/live-complete-$RUN_DATE"

failures=0
warnings=0

pass() {
  printf "✓ %s\n" "$1"
}

warn() {
  printf "⚠ %s\n" "$1"
  warnings=$((warnings + 1))
}

fail() {
  printf "✗ %s\n" "$1"
  failures=$((failures + 1))
}

echo
echo "========================================"
echo " Trading Bot Production Status"
echo "========================================"
echo "New York date: $RUN_DATE"
echo

echo "FILES"

if [[ -x "$PRODUCTION_SCRIPT" ]]; then
  pass "Production launcher exists and is executable."
else
  fail "Production launcher is missing or not executable."
fi

if [[ -x "$PYTHON" ]]; then
  pass "Python environment exists."
else
  fail "Python environment is missing: $PYTHON"
fi

if [[ -f "$LAUNCH_PLIST" ]]; then
  pass "LaunchAgent plist exists."
else
  fail "LaunchAgent plist is missing."
fi

echo
echo "LAUNCHAGENT"

launch_output="$(
  launchctl print "$LAUNCH_DOMAIN/$LAUNCH_LABEL" 2>&1
)"
launch_exit=$?

if [[ "$launch_exit" -eq 0 ]]; then
  pass "LaunchAgent is loaded."

  service_state="$(
    printf "%s\n" "$launch_output" |
      awk '/^[[:space:]]*state =/ {
        print $3
        exit
      }'
  )"

  last_exit="$(
    printf "%s\n" "$launch_output" |
      awk -F'= ' '/^[[:space:]]*last exit code =/ {
        print $2
        exit
      }'
  )"

  if [[ "$service_state" == "running" ]]; then
    pass "Production job is currently running."
  elif [[ "$service_state" == "not" ]]; then
    pass "Production job is idle and waiting."
  else
    warn "LaunchAgent state could not be interpreted: $service_state"
  fi

  if [[ "$last_exit" == "0" ]]; then
    pass "Most recent LaunchAgent exit code was 0."
  elif [[ "$last_exit" == "(never exited)" ]]; then
    warn "LaunchAgent has not recorded a completed run yet."
  else
    warn "Most recent LaunchAgent exit code: $last_exit"
  fi
else
  fail "LaunchAgent is not loaded."
  printf "%s\n" "$launch_output"
fi

echo
echo "DAILY RUN"

if [[ -f "$COMPLETION_FILE" ]]; then
  pass "Today is marked complete."
else
  warn "Today is not marked complete."
fi

if [[ -d "$LOCK_DIR" ]]; then
  if pgrep -f "run_live_production.sh|main.py live" >/dev/null 2>&1; then
    pass "Run lock exists and a trading-bot process is active."
  else
    fail "Stale production lock exists: $LOCK_DIR"
  fi
else
  pass "No stale production lock detected."
fi

echo
echo "LATEST LOG"

if [[ -f "$LOG_FILE" ]]; then
  pass "Production log exists."
  echo
  tail -12 "$LOG_FILE"
else
  warn "Production log does not exist yet."
fi

echo
echo "========================================"

if [[ "$failures" -gt 0 ]]; then
  echo "Status: FAILED"
  echo "$failures failure(s), $warnings warning(s)"
  exit 1
fi

if [[ "$warnings" -gt 0 ]]; then
  echo "Status: HEALTHY WITH WARNINGS"
  echo "$warnings warning(s)"
  exit 0
fi

echo "Status: HEALTHY"
exit 0
