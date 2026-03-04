#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
USER_NAME="${USER_NAME:-p1c01_admin}"
USER_PASS="${USER_PASS:-88888888}"

echo "== ROOT ==" && curl -sS --noproxy '*' -m 3 -o /dev/null -w "%{http_code}\n" "$BASE_URL/"

echo "== LOGIN ==" && curl -sS --noproxy '*' -m 5 -c /tmp/xinyi_cookies.txt \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USER_NAME\",\"password\":\"$USER_PASS\"}" \
  -o /tmp/xinyi_login.json -w "%{http_code}\n" "$BASE_URL/api/auth/login"
cat /tmp/xinyi_login.json && echo

echo "== USERS ==" && curl -sS --noproxy '*' -m 5 -b /tmp/xinyi_cookies.txt \
  -o /tmp/xinyi_users.json -w "%{http_code}\n" "$BASE_URL/api/system/users"
cat /tmp/xinyi_users.json && echo

echo "== OK =="
