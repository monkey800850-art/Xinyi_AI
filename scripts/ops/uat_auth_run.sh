#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"
OPS_ENV_FILE="${OPS_ENV_FILE:-var/run/ops.env}"

OUT="${OUT:-/tmp/evidence_uat_auth_run.txt}"
: > "${OUT}"

log(){ echo "$*" | tee -a "${OUT}"; }
ok(){ log "[OK] $*"; }
warn(){ log "[WARN] $*"; }
fail(){ log "[FAIL] $*"; exit 1; }

# Load ops env (must exist)
if [[ ! -f "${OPS_ENV_FILE}" ]]; then
  fail "missing OPS_ENV_FILE=${OPS_ENV_FILE}. Create it from docs/ops/OPS_ENV.example (DO NOT COMMIT)."
fi
# shellcheck disable=SC1090
source "${OPS_ENV_FILE}"

ADMIN_USER="${ADMIN_USER:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-${ADMIN_PASS:-}}"
[[ -n "${ADMIN_USER}" ]] || fail "ADMIN_USER missing in ops.env"
[[ -n "${ADMIN_PASSWORD}" ]] || fail "ADMIN_PASSWORD missing in ops.env"

JAR="/tmp/xinyi_cookie_jar.txt"
rm -f "${JAR}"

code(){
  curl ${NO_PROXY_OPT} -sS -o /dev/null -w '%{http_code}' --max-time 8 "$1" || echo "000"
}

log "== UAT AUTH RUN =="
log "$(date '+%Y-%m-%d %H:%M (%z)')"
log "BASE_URL=${BASE_URL}"
log "OPS_ENV_FILE=${OPS_ENV_FILE} (present)"
log ""

# 0) Precheck: protected endpoint should be 401/403 when anonymous
pre="$(code "${BASE_URL}/api/system/users")"
log "anon GET /api/system/users -> ${pre}"
if [[ "${pre}" == "200" ]]; then
  warn "endpoint already 200 without auth (check if intended)"
else
  [[ "${pre}" =~ ^(401|403)$ ]] || warn "unexpected anon status: ${pre}"
fi
log ""

# 1) Login (POST /api/auth/login) - store cookie jar
log "== login =="
# Do not echo password; send via curl -d
set +e
curl ${NO_PROXY_OPT} -sS --max-time 10 \
  -c "${JAR}" \
  -H 'Content-Type: application/json' \
  -X POST "${BASE_URL}/api/auth/login" \
  -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
  -D /tmp/login_hdr.txt \
  -o /tmp/login_body.json
rc=$?
set -e
[[ $rc -eq 0 ]] || fail "login curl failed"
login_code="$(rg -m1 '^HTTP/' /tmp/login_hdr.txt | awk '{print $2}')"
log "login status=${login_code}"
[[ "${login_code}" == "200" ]] || fail "login not 200"

# minimal body check
if rg -n '"status"\s*:\s*"ok"' /tmp/login_body.json >/dev/null; then
  ok "login response status ok"
else
  warn "login body missing status:ok (check /tmp/login_body.json locally)"
fi

# cookie jar existence
[[ -s "${JAR}" ]] || warn "cookie jar empty (session may use other mechanism)"
ok "cookie jar created at ${JAR}"
log ""

# 2) Authenticated checks (must become 200)
CHECKS=(
  "/api/system/users|200|items,username"
  "/api/dashboard/task-status|200|status"
)

log "== authenticated checks =="
fails=0

for line in "${CHECKS[@]}"; do
  IFS='|' read -r path allowed keys <<< "${line}"
  url="${BASE_URL}${path}"

  # request with cookie jar
  set +e
  curl ${NO_PROXY_OPT} -sS --max-time 10 -b "${JAR}" -D /tmp/hdr.txt -o /tmp/body.json "${url}"
  rc=$?
  set -e
  [[ $rc -eq 0 ]] || { log "[FAIL] curl failed: ${path}"; fails=$((fails+1)); continue; }

  c="$(rg -m1 '^HTTP/' /tmp/hdr.txt | awk '{print $2}')"
  log "auth GET ${path} -> ${c}"
  if [[ "${c}" != "${allowed}" ]]; then
    log "[FAIL] ${path} expected ${allowed}, got ${c}"
    fails=$((fails+1))
    continue
  fi

  # keys assert
  if [[ -n "${keys}" ]]; then
    body="$(cat /tmp/body.json)"
    echo "$body" | head -c 240 | tee -a "${OUT}"; echo "" | tee -a "${OUT}"
    echo "$body" | rg -q '^\s*[\{\[]' || { log "[FAIL] ${path} not JSON-like"; fails=$((fails+1)); continue; }
    IFS=',' read -r -a arr <<< "${keys}"
    for k in "${arr[@]}"; do
      k="$(echo "$k" | xargs)"
      [[ -n "$k" ]] || continue
      echo "$body" | rg -q "\"${k}\"\\s*:" || { log "[FAIL] ${path} missing key ${k}"; fails=$((fails+1)); }
    done
  fi

  ok "${path} auth ok"
  log ""
done

log "== SUMMARY =="
if [[ "${fails}" -eq 0 ]]; then
  ok "UAT AUTH RUN PASS"
  exit 0
fi
fail "UAT AUTH RUN FAIL (${fails} issue(s))"
