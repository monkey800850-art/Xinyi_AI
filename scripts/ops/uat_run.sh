#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

OUT="${OUT:-/tmp/evidence_uat_run2.txt}"
: > "${OUT}"

log(){ echo "$*" | tee -a "${OUT}"; }
ok(){ log "[OK] $*"; }
warn(){ log "[WARN] $*"; }
fail(){ log "[FAIL] $*"; }

code(){
  curl ${NO_PROXY_OPT} -sS -o /dev/null -w '%{http_code}' --max-time 6 "$1" || echo "000"
}
get_body(){
  curl ${NO_PROXY_OPT} -sS --max-time 8 "$1" || true
}

# Config lines:
# PATH|ALLOWED_CODES(comma)|JSON_KEYS(optional, comma; only checked when 200)
CHECKS=(
  "/|200,302,401,403|"
  "/api/system/users|200,401,403|items,username"
  "/api/dashboard/task-status|200,401,403|status,items,data"
  "/login|200,302,401,403,404|"
  "/reports/trial_balance|200,302,401,403,404|"
  "/tax/summary|200,302,401,403,404|"
  "/dashboard|200,302,401,403,404|"
)

log "== UAT RUN (configurable) =="
log "$(date '+%Y-%m-%d %H:%M (%z)')"
log "BASE_URL=${BASE_URL}"
log ""

fails=0
fail_list=()

check_one(){
  local path="$1" allowed="$2" keys="$3"
  local url="${BASE_URL}${path}"
  local c
  c="$(code "${url}")"
  log "GET ${path} -> ${c} (allow: ${allowed})"

  if ! echo ",${allowed}," | rg -q ",${c},"; then
    fails=$((fails+1))
    fail_list+=("${path}=${c} not_in(${allowed})")
    fail "unexpected status for ${path}: ${c}"
    log ""
    return 0
  fi

  # Optional JSON key assertions (only when 200)
  if [[ "${c}" == "200" && -n "${keys}" ]]; then
    body="$(get_body "${url}")"
    # keep evidence light: show first 240 chars only
    echo "${body}" | head -c 240 | tee -a "${OUT}"; echo "" | tee -a "${OUT}"
    # JSON-like check
    if ! echo "${body}" | rg -q '^\s*[\{\[]'; then
      fails=$((fails+1))
      fail_list+=("${path}=200 but not JSON-like")
      fail "body not JSON-like"
      log ""
      return 0
    fi
    IFS=',' read -r -a arr <<< "${keys}"
    for k in "${arr[@]}"; do
      k="$(echo "$k" | xargs)"
      [[ -n "$k" ]] || continue
      if ! echo "${body}" | rg -q "\"${k}\"\\s*:"; then
        fails=$((fails+1))
        fail_list+=("${path} missing_key(${k})")
        fail "missing json key: ${k}"
      fi
    done
  fi

  ok "${path} ok"
  log ""
}

log "== checks =="
for line in "${CHECKS[@]}"; do
  IFS='|' read -r p allowed keys <<< "${line}"
  check_one "${p}" "${allowed}" "${keys}"
done

log "== SUMMARY =="
if [[ "${fails}" -eq 0 ]]; then
  ok "UAT RUN PASS (all checks satisfied)"
  exit 0
fi

fail "UAT RUN FAIL: ${fails} issue(s)"
for item in "${fail_list[@]}"; do
  log " - ${item}"
done
exit 1
