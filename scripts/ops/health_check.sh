#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
BOOK_ID="${BOOK_ID:-9}"
DEP_YEAR="${DEP_YEAR:-2025}"
DEP_MONTH="${DEP_MONTH:-2}"
TIMEOUT_SEC="${TIMEOUT_SEC:-8}"

ok=0
fail=0

check_http() {
  local name="$1"
  local path="$2"
  local expected="$3"
  local code
  code=$(curl -m "$TIMEOUT_SEC" -s -o /tmp/step28_health_body.txt -w "%{http_code}" "${BASE_URL}${path}" || echo "000")
  if [[ "$code" == "$expected" ]]; then
    echo "[PASS] ${name} ${path} -> ${code}"
    ok=$((ok + 1))
  else
    echo "[FAIL] ${name} ${path} -> ${code} (expect ${expected})"
    echo "       body: $(head -c 160 /tmp/step28_health_body.txt 2>/dev/null || true)"
    fail=$((fail + 1))
  fi
}

check_json_contains() {
  local name="$1"
  local path="$2"
  local pattern="$3"
  local body
  body=$(curl -m "$TIMEOUT_SEC" -s "${BASE_URL}${path}" || true)
  if echo "$body" | rg -q "$pattern"; then
    echo "[PASS] ${name} ${path} contains /${pattern}/"
    ok=$((ok + 1))
  else
    echo "[FAIL] ${name} ${path} missing /${pattern}/"
    echo "       body: $(echo "$body" | head -c 160)"
    fail=$((fail + 1))
  fi
}

echo "STEP28 health check"
echo "BASE_URL=${BASE_URL} BOOK_ID=${BOOK_ID} DEP=${DEP_YEAR}-${DEP_MONTH}"

check_http "health" "/" "200"
check_json_contains "health-body" "/" '"status"\s*:\s*"ok"'
check_http "dashboard" "/dashboard" "200"
check_http "roles-api" "/api/system/roles" "200"
check_http "asset-changes-api" "/api/assets/changes?book_id=${BOOK_ID}" "200"
check_http "asset-ledger-api" "/api/assets/ledger?book_id=${BOOK_ID}&dep_year=${DEP_YEAR}&dep_month=${DEP_MONTH}" "200"

echo "summary: pass=${ok} fail=${fail}"
if (( fail > 0 )); then
  exit 1
fi
