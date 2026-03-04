#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

OUT="${OUT:-/tmp/evidence_uat_run.txt}"
: > "${OUT}"

log(){ echo "$*" | tee -a "${OUT}"; }
ok(){ log "[OK] $*"; }
warn(){ log "[WARN] $*"; }
fail(){ log "[FAIL] $*"; exit 1; }

code(){
  curl ${NO_PROXY_OPT} -sS -o /dev/null -w '%{http_code}' --max-time 6 "$1" || echo "000"
}

json_get(){
  curl ${NO_PROXY_OPT} -sS --max-time 8 "$1" || true
}

log "== UAT RUN =="
log "$(date '+%Y-%m-%d %H:%M (%z)')"
log "BASE_URL=${BASE_URL}"
log ""

# 0) Basic reachability
log "== STEP 0: ROOT =="
c="$(code "${BASE_URL}/")"
log "GET / -> ${c}"
[[ "${c}" =~ ^(200|302|401|403)$ ]] || fail "root not reachable: ${c}"
ok "root reachable"
log ""

# 1) System API reachability (anonymous expected 401)
log "== STEP 1: /api/system/users (reachable) =="
c="$(code "${BASE_URL}/api/system/users")"
log "GET /api/system/users -> ${c}"
[[ "${c}" =~ ^(200|401|403)$ ]] || fail "unexpected status: ${c}"
ok "system api reachable (auth may be required)"
log ""

# 2) Dashboard API (anonymous allowed)
DASH_API="${DASH_API:-/api/dashboard/task-status}"
log "== STEP 2: ${DASH_API} =="
c="$(code "${BASE_URL}${DASH_API}")"
log "GET ${DASH_API} -> ${c}"
[[ "${c}" =~ ^(200|401|403)$ ]] || warn "dashboard api status unusual: ${c}"
if [[ "${c}" == "200" ]]; then
  body="$(json_get "${BASE_URL}${DASH_API}")"
  echo "$body" | head -c 240 | tee -a "${OUT}"; echo "" | tee -a "${OUT}"
  echo "$body" | rg -q '^\s*[\{\[]' && ok "dashboard returns JSON" || warn "dashboard 200 but not JSON-like"
fi
log ""

# 3) UI pages (best-effort)
paths=("/login" "/reports/trial_balance" "/tax/summary" "/dashboard")
log "== STEP 3: UI pages (best-effort) =="
for p in "${paths[@]}"; do
  c="$(code "${BASE_URL}${p}")"
  log "GET ${p} -> ${c}"
done
ok "ui page probe completed"
log ""

log "== RESULT =="
ok "UAT run skeleton completed. For authenticated flows, run smoke_auth/smoke_dashboard with ops.env."
