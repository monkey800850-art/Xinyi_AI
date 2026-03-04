#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
COOKIE="${COOKIE:-cookies.txt}"
LOG="${LOG:-/tmp/xinyi_app_500.log}"

echo "== TIME =="
date -Is

echo "== ENV (safe fields) =="
( grep -E '^(FLASK_ENV|DB_HOST|DB_PORT|DB_NAME|DB_USER|SECRET_KEY)=' .env 2>/dev/null || true ) | sed 's/SECRET_KEY=.*/SECRET_KEY=***REDACTED***/'

echo "== LISTEN :5000 =="
ss -lntp | grep ':5000' || echo "NOT_LISTENING"

echo "== CURL / (no proxy) =="
curl -i --noproxy '*' --max-time 5 "$BASE_URL/" | head -n 20 || true

echo "== CURL login (no proxy) =="
printf '{"username":"p1c01_admin","password":"88888888"}' | \
curl -i --noproxy '*' --max-time 8 -c "$COOKIE" \
  -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" --data-binary @- | head -n 30 || true

echo "== CURL /api/system/users (no proxy) =="
curl -i --noproxy '*' --max-time 8 -b "$COOKIE" \
  "$BASE_URL/api/system/users" | head -n 40 || true

echo "== LOG tail =="
if [ -f "$LOG" ]; then
  tail -n 80 "$LOG"
else
  echo "LOG_NOT_FOUND: $LOG"
fi
