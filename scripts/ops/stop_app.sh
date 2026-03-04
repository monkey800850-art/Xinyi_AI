#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${PID_FILE:-var/run/xinyi_app.pid}"
PORT="${PORT:-5000}"

echo "== stop_app =="
date '+%Y-%m-%d %H:%M (%z)'
echo "PID_FILE=${PID_FILE}"
echo "PORT=${PORT}"
echo ""

if [[ ! -f "${PID_FILE}" ]]; then
  echo "[OK] no pid file; nothing to stop."
  exit 0
fi

pid="$(cat "${PID_FILE}" || true)"
if [[ -z "${pid}" || "${pid}" == "unknown" ]]; then
  echo "[WARN] invalid pid file content; removing."
  rm -f "${PID_FILE}" || true
  exit 0
fi

if ! ps -p "${pid}" >/dev/null 2>&1; then
  echo "[WARN] pid not running (${pid}); removing pid file."
  rm -f "${PID_FILE}" || true
  exit 0
fi

echo "[INFO] stopping pid=${pid}"
kill "${pid}" || true

for i in $(seq 1 10); do
  if ! ps -p "${pid}" >/dev/null 2>&1; then
    echo "[OK] stopped (t=${i}s)"
    rm -f "${PID_FILE}" || true
    exit 0
  fi
  sleep 1
done

echo "[WARN] still running; sending SIGKILL"
kill -9 "${pid}" || true
rm -f "${PID_FILE}" || true
echo "[OK] force-stopped"
