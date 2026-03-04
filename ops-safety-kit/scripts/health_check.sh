#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
PORT="${PORT:-5000}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"
LOG_PATH_HINT="${LOG_PATH_HINT:-/tmp/xinyi_app_500.log}"
OSK_HC_STRICT="${OSK_HC_STRICT:-1}"  # 1=strict FAIL; 0=degrade on restricted network


echo "== health_check =="
date '+%Y-%m-%d %H:%M (%z)'
echo "pwd=$PWD"
echo "git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo nogit)"
echo "git_head=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
echo "BASE_URL=${BASE_URL}"
echo "PORT=${PORT}"
echo

echo "== listen check (:${PORT}) =="
if command -v ss >/dev/null 2>&1; then
  set +e
  out="$(ss -ltnp 2>&1)"
  rc=$?
  set -e
  if echo "$out" | grep -qi "Cannot open netlink socket"; then
    echo "[WARN] ss netlink permission limited; showing best-effort listener line"
    echo "$out" | grep -E ":${PORT}\b" || true
  else
    echo "$out" | grep -E ":${PORT}\b" || echo "[WARN] no listener line found for :${PORT}"
  fi
else
  echo "[WARN] ss not found; skipping listen check"
fi
echo

http_get_status() {
  local url="$1"

  if command -v curl >/dev/null 2>&1; then
    # shellcheck disable=SC2086
    curl -sS -o /dev/null -w "%{http_code}" ${NO_PROXY_OPT} --max-time 5 "$url" || echo "000"
    return 0
  fi

  python3 - <<PY
import urllib.request, urllib.error, socket, sys
url="${url}"
try:
    # Force-disable proxies regardless of env vars
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, method="GET")
    with opener.open(req, timeout=5) as r:
        print(getattr(r, "status", 200))
except urllib.error.HTTPError as e:
    print(e.code)
except Exception as e:
    # Return 000 but also print diagnostic for evidence
    print("000")
    print(f"[urllib_diag] {type(e).__name__}: {e}", file=sys.stderr)
PY
}

echo "== http root =="
# capture stderr from http_get_status by running it in a subshell
diag_file="$(mktemp)"
set +e
code="$( { http_get_status "${BASE_URL}/" 2> "$diag_file"; } )"
rc=$?
set -e
diag="$(cat "$diag_file" 2>/dev/null || true)"
rm -f "$diag_file" || true

# Print diag first if any
if [ -n "$diag" ]; then
  echo "$diag"
fi
echo "GET / -> ${code}"

if [ "$code" != "200" ] && [ "$code" != "302" ]; then
  if echo "$diag" | grep -qi "Operation not permitted"; then
    echo "[WARN] NETWORK_RESTRICTED: outbound connect blocked by environment policy (Errno 1)."
    if [ "${OSK_HC_STRICT}" = "1" ]; then
      echo "[FAIL] strict mode enabled; failing health_check due to unreachable root."
      exit 1
    else
      echo "[OK] degrade mode: skipping http root failure (listen check still valid)."
    fi
  else
    echo "[FAIL] root not reachable or unexpected status: ${code}"
    exit 1
  fi
fi
echo

echo "== api /api/system/users (reachability only) =="
diag_file="$(mktemp)"
set +e
code="$( { http_get_status "${BASE_URL}/api/system/users" 2> "$diag_file"; } )"
set -e
diag="$(cat "$diag_file" 2>/dev/null || true)"
rm -f "$diag_file" || true
if [ -n "$diag" ]; then
  echo "$diag"
fi
echo "GET /api/system/users -> ${code}"

# Accept 200/401/403/404 as reachability; 000 means network failure
if [ "$code" = "000" ]; then
  if echo "$diag" | grep -qi "Operation not permitted"; then
    echo "[WARN] NETWORK_RESTRICTED: outbound connect blocked by environment policy (Errno 1)."
    if [ "${OSK_HC_STRICT}" = "1" ]; then
      echo "[FAIL] strict mode enabled; failing due to unreachable api."
      exit 1
    else
      echo "[OK] degrade mode: skipping api reachability failure (listen check still valid)."
    fi
  else
    echo "[FAIL] /api/system/users unreachable (000)"
    exit 1
  fi
fi
echo "== log path hint =="
echo "LOG_PATH_HINT=${LOG_PATH_HINT}"
if [ -f "${LOG_PATH_HINT}" ]; then
  echo "[OK] log file exists at hint path"
else
  echo "[WARN] log file not found at hint path (may be OK): ${LOG_PATH_HINT}"
fi
echo

echo "[OK] health_check completed."
