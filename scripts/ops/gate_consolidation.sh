#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p _health
APP_LOG="_health/app_last_run.log"
APP_PID_FILE="_health/app_pid_gate_conso.txt"

cleanup() {
  if [ -f "$APP_PID_FILE" ]; then
    pid="$(cat "$APP_PID_FILE" 2>/dev/null || true)"
    if [[ "${pid:-}" =~ ^[0-9]+$ ]]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT INT TERM

fail_gate() {
  local reason="$1"
  local show_log="${2:-0}"
  echo "[gate] FAIL: ${reason}"
  if [ "$show_log" -eq 1 ]; then
    echo "===== _health/app_last_run.log (tail 60) ====="
    tail -n 60 "$APP_LOG" 2>/dev/null || true
  fi
  echo "summary: FAIL"
  exit 1
}

echo "[gate] 1/3 smoke"
bash scripts/ops/smoke.sh || fail_gate "smoke"

echo "[gate] 2/3 unit test"
python3 -m pytest -q tests/test_cons_auth_gate_unit.py || fail_gate "unit_test"

echo "[gate] 3/3 app endpoints"
FLASK_ENV=production FLASK_DEBUG=0 \
python3 app.py >"$APP_LOG" 2>&1 &
app_pid=$!
echo "$app_pid" > "$APP_PID_FILE"

port_ready="$(
python3 - <<'PY'
import socket
import time

host = "127.0.0.1"
port = 5000
deadline = time.time() + 5
ok = False
while time.time() < deadline:
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        ok = True
        break
    except Exception:
        time.sleep(0.2)
    finally:
        try:
            s.close()
        except Exception:
            pass
print("OK" if ok else "NOT_READY")
PY
)"

if [ "$port_ready" != "OK" ]; then
  fail_gate "gate3_port_not_ready" 1
fi

probe_http_code() {
  local url="$1"
  local code
  set +e
  code="$(curl --max-time 5 -s -o /dev/null -w "%{http_code}" "$url")"
  local rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    echo "000"
  else
    echo "$code"
  fi
}

ui_code="$(probe_http_code "http://127.0.0.1:5000/system/consolidation")"
api_code="$(probe_http_code "http://127.0.0.1:5000/api/consolidation/parameters")"
echo "[gate] /system/consolidation -> ${ui_code}"
echo "[gate] /api/consolidation/parameters -> ${api_code}"

if [ "$ui_code" = "000" ] || [ "$api_code" = "000" ]; then
  fail_gate "gate3_http_probe_000" 1
fi

echo "summary: PASS"
