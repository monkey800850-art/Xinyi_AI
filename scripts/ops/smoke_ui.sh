#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

OUT="${OUT:-/tmp/evidence_ui_smoke.txt}"
: > "${OUT}"

log(){ echo "$*" | tee -a "${OUT}"; }
fail(){ log "[FAIL] $*"; exit 1; }
ok(){ log "[OK] $*"; }

fetch(){
  local path="$1"
  curl ${NO_PROXY_OPT} -sS --max-time 5 -D - "${BASE_URL}${path}" -o /tmp/ui_body.html || return 1
  return 0
}

status_of(){
  # reads headers in stdout from fetch()
  rg -m1 -n '^HTTP/' | awk '{print $2}' || true
}

log "== smoke_ui =="
log "$(date '+%Y-%m-%d %H:%M (%z)')"
log "BASE_URL=${BASE_URL}"
log ""

# 1) ROOT
log "== GET / =="
hdr="$(fetch "/" && cat /tmp/ui_body.html >/dev/null; cat -)"
# we can't easily capture both; do it simpler:
set +e
curl ${NO_PROXY_OPT} -sS --max-time 5 -D /tmp/ui_hdr.txt -o /tmp/ui_root.html "${BASE_URL}/"
rc=$?
set -e
[[ $rc -eq 0 ]] || fail "curl / failed"
code="$(rg -m1 '^HTTP/' /tmp/ui_hdr.txt | awk '{print $2}')"
log "status=${code}"
[[ "${code}" =~ ^(200|302|401|403)$ ]] || fail "unexpected status for /: ${code}"
# HTML heuristic
if [[ "${code}" == "200" ]]; then
  rg -n '<html|<!doctype html' /tmp/ui_root.html >/dev/null && ok "root returns HTML" || log "[WARN] root 200 but not obvious HTML"
fi
log ""

# Candidate paths (best-effort)
paths=("/login" "/reports/trial_balance" "/tax/summary" "/dashboard")
for p in "${paths[@]}"; do
  log "== GET ${p} (best-effort) =="
  set +e
  curl ${NO_PROXY_OPT} -sS --max-time 5 -D /tmp/ui_hdr.txt -o /tmp/ui_page.html "${BASE_URL}${p}"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    log "[SKIP] curl failed (path may not exist): ${p}"
    log ""
    continue
  fi
  code="$(rg -m1 '^HTTP/' /tmp/ui_hdr.txt | awk '{print $2}')"
  log "status=${code}"
  # allow 200/302/401/403/404 (404 means route absent; not a failure here)
  if [[ ! "${code}" =~ ^(200|302|401|403|404)$ ]]; then
    fail "unexpected status for ${p}: ${code}"
  fi
  if [[ "${code}" == "200" ]]; then
    rg -n '<html|<!doctype html' /tmp/ui_page.html >/dev/null && ok "${p} returns HTML" || log "[WARN] ${p} 200 but not obvious HTML"
  fi
  log ""
done

# Static sample (best-effort): find one static reference in root html, then request it
log "== static sample (best-effort) =="
static_path="$(rg -o '/static/[^"'"'"' )]+' /tmp/ui_root.html 2>/dev/null | head -n 1 || true)"
if [[ -n "${static_path}" ]]; then
  log "static_ref=${static_path}"
  code="$(curl ${NO_PROXY_OPT} -sS --max-time 5 -o /dev/null -w '%{http_code}' "${BASE_URL}${static_path}" || echo 000)"
  log "GET ${static_path} -> ${code}"
  [[ "${code}" =~ ^(200|304)$ ]] || log "[WARN] static resource not reachable: ${code}"
else
  log "[SKIP] no /static reference found in root html"
fi

ok "smoke_ui completed."
