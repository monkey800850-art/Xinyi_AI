#!/usr/bin/env bash
set -euo pipefail


# PORT_OWNERSHIP_CHECK
port_owner() {
  local port="$1"
  # Prefer ss, fallback to lsof
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | rg -n ":${port}\\b" || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  else
    echo "[WARN] neither ss nor lsof available to detect port owner"
    return 0
  fi
}

port_owned_by_this_app() {
  local port="$1"
  # Heuristic: python process and repo path name appears
  local o
  o="$(port_owner "${port}")"
  echo "${o}" | rg -q "python" && echo "${o}" | rg -q "app\.py|Xinyi_AI|xinyi" && return 0
  return 1
}

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

PID_FILE="${PID_FILE:-var/run/xinyi_app.pid}"
LOG_PATH="${LOG_PATH:-var/log/xinyi_app.log}"

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_PATH")"

http_code() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl ${NO_PROXY_OPT} -sS -o /dev/null -w '%{http_code}' --max-time 3 "$url" || echo "000"
    return
  fi

  python3 - "$url" <<'PY'
import sys
import urllib.request
import urllib.error
url = sys.argv[1]
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=3) as r:
        print(r.getcode())
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print("000")
PY
}

is_listening() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | rg -q ":${p}\\b"
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltn 2>/dev/null | rg -q ":${p}\\b"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP -sTCP:LISTEN -P 2>/dev/null | rg -q ":${p}\\b"
  else
    python3 - "$p" <<'PY'
import socket, sys
p = int(sys.argv[1])
s = socket.socket()
s.settimeout(1)
try:
    s.connect(("127.0.0.1", p))
    print("ok")
except Exception:
    sys.exit(1)
finally:
    s.close()
PY
  fi
}

echo "== start_app =="
date '+%Y-%m-%d %H:%M (%z)'
echo "HOST=${HOST}"
echo "PORT=${PORT}"
echo "BASE_URL=${BASE_URL}"
echo "PID_FILE=${PID_FILE}"
echo "LOG_PATH=${LOG_PATH}"
echo ""

if [[ -f "$PID_FILE" ]]; then
  oldpid="$(cat "$PID_FILE" || true)"
  if [[ -n "${oldpid}" ]] && ps -p "${oldpid}" >/dev/null 2>&1 && is_listening "${PORT}" >/dev/null 2>&1; then
    echo "[OK] already running (pid=${oldpid}) and listening :${PORT}"
    exit 0
  fi
  echo "[WARN] stale pid file or process not healthy; removing PID_FILE"
  rm -f "$PID_FILE" || true
fi

if is_listening "${PORT}" >/dev/null 2>&1; then
  echo "[WARN] port :${PORT} already listening; checking ownership
if port_owned_by_this_app "${PORT}"; then
  echo "[OK] port ${PORT} seems owned by this app; will not restart"
else
  echo "[FAIL] port ${PORT} is occupied by another process; stop it first." >&2
  port_owner "${PORT}" >&2 || true
  exit 1
fi

fi

export FLASK_RUN_HOST="${HOST}"
export FLASK_RUN_PORT="${PORT}"
export LOG_PATH="${LOG_PATH}"

echo "[INFO] starting: python3 app.py"
nohup python3 app.py >>"$LOG_PATH" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"
echo "[OK] started pid=${pid}"
echo ""

for i in $(seq 1 20); do
  if is_listening "${PORT}" >/dev/null 2>&1; then
    echo "[OK] listening on :${PORT} (t=${i}s)"
    break
  fi
  sleep 1
done

if ! is_listening "${PORT}" >/dev/null 2>&1; then
  echo "[FAIL] not listening on :${PORT} after 20s"
  echo "---- tail log ----"
  tail -n 80 "$LOG_PATH" || true
  exit 1
fi

code="$(http_code "${BASE_URL}/")"
echo "GET / -> ${code}"
[[ "$code" =~ ^(200|302|401|403)$ ]] || { echo "[FAIL] unexpected root status ${code}"; exit 1; }

echo "[OK] start_app completed."
