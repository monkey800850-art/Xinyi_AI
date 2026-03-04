#!/usr/bin/env bash
set -euo pipefail

# Minimal, robust starter for Xinyi_AI
# - No curl required
# - ss/lsof optional
# - Writes PID file
# - Logs to var/log/xinyi_app.log by default

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

# Defaults (can be overridden by env)
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
PID_FILE="${PID_FILE:-var/run/xinyi_app.pid}"
LOG_PATH="${LOG_PATH:-var/log/xinyi_app.log}"
APP_CMD="${APP_CMD:-python3 app.py}"

mkdir -p "$(dirname "${PID_FILE}")" "$(dirname "${LOG_PATH}")"

echo "== start_app =="
date '+%Y-%m-%d %H:%M (%z)'
echo "HOST=${HOST}"
echo "PORT=${PORT}"
echo "BASE_URL=${BASE_URL}"
echo "PID_FILE=${PID_FILE}"
echo "LOG_PATH=${LOG_PATH}"
echo "APP_CMD=${APP_CMD}"
echo

port_owner() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -E ":${port}\b" || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  else
    echo "[WARN] neither ss nor lsof available to detect port owner"
    return 0
  fi
}

port_is_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE ":${port}\b" && return 0 || return 1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1 && return 0 || return 1
  else
    # can't detect; assume not listening
    return 1
  fi
}

# If already listening, do NOT pretend success; report owner and exit non-zero
if port_is_listening "${PORT}"; then
  echo "[FAIL] port :${PORT} already listening; refusing to start to avoid ambiguity." >&2
  port_owner "${PORT}" >&2 || true
  exit 1
fi

# Start in background, write pid
# shellcheck disable=SC2086
nohup ${APP_CMD} >> "${LOG_PATH}" 2>&1 &
pid=$!
echo "${pid}" > "${PID_FILE}"
echo "[OK] started pid=${pid}"

# Best-effort small wait then re-check port (no curl)
sleep 1
if port_is_listening "${PORT}"; then
  echo "[OK] port :${PORT} is listening"
  port_owner "${PORT}" || true
else
  echo "[WARN] port :${PORT} not detected as listening yet (may take longer)."
  port_owner "${PORT}" || true
fi
