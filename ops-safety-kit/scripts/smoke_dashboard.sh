#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

ADMIN_USER="${ADMIN_USER:-p1c01_admin}"
ADMIN_PASS="${ADMIN_PASS:-${ADMIN_PASSWORD:-}}"
DASH_API="${DASH_API:-/api/dashboard/task-status}"
TASK_CODE="${TASK_CODE:-reimbursement_review}"

fail(){ echo "[FAIL] $*"; exit 1; }
ok(){ echo "[OK] $*"; }
info(){ echo "== $* =="; }

http_req(){
  # usage: http_req METHOD URL [BODY] [COOKIE_IN] [COOKIE_OUT] [MODE]
  local method="$1"; shift
  local url="$1"; shift
  local body="${1:-}"; shift || true
  local cookie_in="${1:-}"; shift || true
  local cookie_out="${1:-}"; shift || true
  local mode="${1:-code}" # code|body

  if command -v curl >/dev/null 2>&1; then
    local args=( ${NO_PROXY_OPT} -sS --max-time 5 -X "$method" )
    [[ -n "$body" ]] && args+=( -H 'Content-Type: application/json' -d "$body" )
    [[ -n "$cookie_in" ]] && args+=( -b "$cookie_in" )
    [[ -n "$cookie_out" ]] && args+=( -c "$cookie_out" )
    if [[ "$mode" == "code" ]]; then
      curl "${args[@]}" -o /dev/null -w '%{http_code}' "$url" || echo "000"
    else
      curl "${args[@]}" "$url" || true
    fi
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$method" "$url" "$body" "$cookie_in" "$cookie_out" "$mode" <<'PY'
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import MozillaCookieJar

method, url, body, cookie_in, cookie_out, mode = sys.argv[1:7]
jar = MozillaCookieJar()

try:
    if cookie_in and os.path.exists(cookie_in):
        try:
            jar.load(cookie_in, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(jar),
    )
    payload = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=payload, method=method)
    if body:
        req.add_header("Content-Type", "application/json")

    status = "000"
    text = ""
    try:
        with opener.open(req, timeout=5) as resp:
            status = str(resp.getcode())
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status = str(e.code)
        try:
            text = e.read().decode("utf-8", "replace")
        except Exception:
            text = ""
    except Exception:
        status = "000"

    if cookie_out:
        try:
            jar.save(cookie_out, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    if mode == "body":
        print(text)
    else:
        print(status)
except Exception:
    print("" if mode == "body" else "000")
PY
    return
  fi

  [[ "$mode" == "body" ]] && echo "" || echo "000"
}

code_only(){
  http_req GET "$1" "" "" "" code
}

json_get(){
  local url="$1"
  local cookie="${2:-}"
  http_req GET "$url" "" "$cookie" "" body
}

echo "== smoke_dashboard =="
date '+%Y-%m-%d %H:%M (%z)'
echo "BASE_URL=${BASE_URL}"
echo "DASH_API=${DASH_API}"
echo "TASK_CODE=${TASK_CODE}"
echo ""

info "ROOT"
c="$(code_only "${BASE_URL}/")"
echo "$c"
[[ "$c" =~ ^(200|302|401|403)$ ]] || fail "ROOT unexpected status: $c"
echo ""

dash_url="${BASE_URL}${DASH_API}?task_code=${TASK_CODE}"

info "DASH API (anonymous first)"
c="$(code_only "${dash_url}")"
echo "$c"
[[ "$c" =~ ^(200|401|403)$ ]] || fail "DASH API unexpected status: $c"
echo ""

cookie=""
if [[ "$c" != "200" ]]; then
  info "LOGIN (needed for dashboard)"
  [[ -n "${ADMIN_PASS}" ]] || fail "ADMIN_PASSWORD not set; dashboard needs auth."
  cookie="$(mktemp)"
  body="$(printf '{"username":"%s","password":"%s"}' "${ADMIN_USER}" "${ADMIN_PASS}")"
  lc="$(http_req POST "${BASE_URL}/api/auth/login" "${body}" "" "$cookie" code)"
  echo "$lc"
  [[ "$lc" == "200" ]] || { rm -f "$cookie" || true; fail "login failed status: $lc"; }
  [[ -s "$cookie" ]] || { rm -f "$cookie" || true; fail "cookie jar empty; login failed."; }
  ok "session cookie captured"
  echo ""
fi

info "DASH API (validate json structure)"
resp="$(json_get "${dash_url}" "${cookie}")"
printf '%s\n' "$resp" | head -c 200; echo ""
printf '%s' "$resp" | rg -q '^\s*[\{\[]' || { [[ -n "$cookie" ]] && rm -f "$cookie" || true; fail "dashboard response not JSON-like"; }
printf '%s' "$resp" | rg -q '"status"\s*:|"items"\s*:|"data"\s*:' || { [[ -n "$cookie" ]] && rm -f "$cookie" || true; fail "dashboard JSON missing key fields (status/items/data)"; }

[[ -n "$cookie" ]] && rm -f "$cookie" || true
ok "smoke_dashboard completed."
