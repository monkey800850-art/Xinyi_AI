#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
LOG_DIR="${LOG_DIR:-var/log}"
LOG_FILE="${LOG_FILE:-xinyi_app.log}"
LOG_PATH_HINT="${LOG_PATH_HINT:-${LOG_DIR}/${LOG_FILE}}"
EFFECTIVE_LOG_PATH="${XINYI_EFFECTIVE_LOG_PATH:-${LOG_PATH:-}}"

if [[ -z "${EFFECTIVE_LOG_PATH}" ]]; then
  if [[ -n "${LOG_FILE}" && -n "${LOG_DIR}" ]]; then
    EFFECTIVE_LOG_PATH="${LOG_DIR}/${LOG_FILE}"
  elif [[ -n "${LOG_FILE}" ]]; then
    EFFECTIVE_LOG_PATH="var/log/${LOG_FILE}"
  else
    EFFECTIVE_LOG_PATH="var/log/xinyi_app.log"
  fi
fi

if [[ ! -f "${EFFECTIVE_LOG_PATH}" && -f "/tmp/xinyi_app.log" ]]; then
  EFFECTIVE_LOG_PATH="/tmp/xinyi_app.log"
fi

fail() { echo "[FAIL] $*"; exit 1; }
warn() { echo "[WARN] $*"; }
ok()   { echo "[OK] $*"; }

http_status() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' --max-time 3 "${url}" || echo "000"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$url" <<'PY'
import sys
import socket
from urllib.parse import urlparse

raw = sys.argv[1]
u = urlparse(raw)
host = u.hostname or "127.0.0.1"
port = u.port or (443 if u.scheme == "https" else 80)
path = (u.path or "/") + (("?" + u.query) if u.query else "")

try:
    with socket.create_connection((host, port), timeout=3) as s:
        req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        s.sendall(req.encode("ascii", "ignore"))
        line = b""
        while not line.endswith(b"\r\n"):
            chunk = s.recv(1)
            if not chunk:
                break
            line += chunk
        parts = line.decode("iso-8859-1", "replace").strip().split()
        if len(parts) >= 2 and parts[1].isdigit():
            print(parts[1])
        else:
            print("000")
except Exception:
    print("000")
PY
    return
  fi

  echo "000"
}

echo "== health_check =="
date '+%Y-%m-%d %H:%M (%z)'
echo "pwd=$(pwd)"
echo "git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
echo "git_head=$(git rev-parse --short HEAD 2>/dev/null || true)"
echo ""

echo "== listen check (:${PORT}) =="
if command -v ss >/dev/null 2>&1; then
  ss -ltnp | grep -E ":${PORT}\\b" || warn "ss: not listening on :${PORT}"
elif command -v netstat >/dev/null 2>&1; then
  netstat -ltnp 2>/dev/null | grep -E ":${PORT}\\b" || warn "netstat: not listening on :${PORT}"
elif command -v lsof >/dev/null 2>&1; then
  lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | grep -E ":${PORT}\\b" || warn "lsof: not listening on :${PORT}"
else
  warn "ss/netstat/lsof not found; skip listen check."
fi
echo ""

echo "== http root =="
ROOT_STATUS="$(http_status "${BASE_URL}/")"
echo "GET / -> ${ROOT_STATUS}"
[[ "${ROOT_STATUS}" =~ ^(200|302|401|403)$ ]] || fail "root not reachable or unexpected status: ${ROOT_STATUS}"
echo ""

echo "== api /api/system/users (reachable check) =="
USERS_STATUS="$(http_status "${BASE_URL}/api/system/users")"
echo "GET /api/system/users -> ${USERS_STATUS}"
[[ "${USERS_STATUS}" =~ ^(200|401|403)$ ]] || fail "users endpoint not reachable or unexpected status: ${USERS_STATUS}"
echo ""

echo "== log path hint =="
LOG_PATH="${EFFECTIVE_LOG_PATH:-${LOG_PATH_HINT}}"
echo "LOG_PATH=${LOG_PATH}"
if [[ -n "${LOG_PATH}" && -f "${LOG_PATH}" ]]; then
  ok "log file exists: ${LOG_PATH}"
  echo "-- tail(50) --"
  tail -n 50 "${LOG_PATH}" || true
else
  warn "log file not found at LOG_PATH (may be OK if logging disabled): ${LOG_PATH}"
fi
echo ""

ok "health_check completed."
