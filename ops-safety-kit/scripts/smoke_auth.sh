#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

ADMIN_USER="${ADMIN_USER:-p1c01_admin}"
ADMIN_PASS="${ADMIN_PASS:-${ADMIN_PASSWORD:-}}"

fail(){ echo "[FAIL] $*"; exit 1; }
ok(){ echo "[OK] $*"; }
info(){ echo "== $* =="; }

http_code(){
  # usage: http_code METHOD URL [DATA] [COOKIE_IN] [COOKIE_OUT]
  local method="$1"; shift
  local url="$1"; shift
  local data="${1:-}"; shift || true
  local cookie_in="${1:-}"; shift || true
  local cookie_out="${1:-}"

  if command -v curl >/dev/null 2>&1; then
    local args=( ${NO_PROXY_OPT} -sS -o /dev/null -w '%{http_code}' --max-time 5 -X "$method" )
    [[ -n "$data" ]] && args+=( -H 'Content-Type: application/json' -d "$data" )
    [[ -n "$cookie_in" ]] && args+=( -b "$cookie_in" )
    [[ -n "$cookie_out" ]] && args+=( -c "$cookie_out" )
    curl "${args[@]}" "$url" || echo "000"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$method" "$url" "$data" "$cookie_in" "$cookie_out" <<'PY'
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import MozillaCookieJar

method, url, data, cookie_in, cookie_out = sys.argv[1:6]
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
    payload = data.encode("utf-8") if data else None
    req = urllib.request.Request(url, data=payload, method=method)
    if data:
        req.add_header("Content-Type", "application/json")

    code = "000"
    try:
        with opener.open(req, timeout=5) as resp:
            code = str(resp.getcode())
    except urllib.error.HTTPError as e:
        code = str(e.code)
    except Exception:
        code = "000"

    if cookie_out:
        try:
            jar.save(cookie_out, ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    print(code)
except Exception:
    print("000")
PY
    return
  fi

  echo "000"
}

echo "== smoke_auth =="
date '+%Y-%m-%d %H:%M (%z)'
echo "BASE_URL=${BASE_URL}"
echo ""

info "ROOT"
code="$(http_code GET "${BASE_URL}/")"
echo "${code}"
[[ "$code" =~ ^(200|302|401|403)$ ]] || fail "ROOT unexpected status: ${code}"
echo ""

info "USERS (anonymous expected 401/403 or 200 if public)"
code="$(http_code GET "${BASE_URL}/api/system/users")"
echo "${code}"
[[ "$code" =~ ^(200|401|403)$ ]] || fail "USERS(anon) unexpected status: ${code}"
echo ""

info "LOGIN"
[[ -n "${ADMIN_PASS}" ]] || fail "ADMIN_PASS/ADMIN_PASSWORD not set in env (refuse to run login)."
login_body="$(printf '{"username":"%s","password":"%s"}' "${ADMIN_USER}" "${ADMIN_PASS}")"
code="$(http_code POST "${BASE_URL}/api/auth/login" "${login_body}")"
echo "${code}"
[[ "$code" == "200" ]] || fail "LOGIN failed status: ${code}"
echo ""

info "LOGIN (capture session)"
tmp_cookie="$(mktemp)"
code="$(http_code POST "${BASE_URL}/api/auth/login" "${login_body}" "" "${tmp_cookie}")"
[[ "$code" == "200" ]] || { rm -f "${tmp_cookie}" || true; fail "LOGIN(session) failed status: ${code}"; }
[[ -s "${tmp_cookie}" ]] || { rm -f "${tmp_cookie}" || true; fail "cookie jar empty; session not established."; }
ok "session cookie captured"
echo ""

info "USERS (after login must be 200)"
code="$(http_code GET "${BASE_URL}/api/system/users" "" "${tmp_cookie}")"
echo "${code}"
rm -f "${tmp_cookie}" || true
[[ "$code" == "200" ]] || fail "USERS(auth) expected 200, got: ${code}"
echo ""

ok "smoke_auth completed."
