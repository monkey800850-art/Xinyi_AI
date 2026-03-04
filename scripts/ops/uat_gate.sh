#!/usr/bin/env bash
set -euo pipefail

OUT="/tmp/evidence_uat_gate.txt"
: > "${OUT}"

log(){ echo "$*" | tee -a "${OUT}"; }
fail(){ log "[FAIL] $*"; exit 1; }
ok(){ log "[OK] $*"; }

log "== UAT gate =="
log "$(date '+%Y-%m-%d %H:%M (%z)')"
log "repo=$(pwd)"
log "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
log "head=$(git rev-parse --short HEAD 2>/dev/null || true)"
log ""

# P0 checks (local)
log "== P0 local checks =="
[[ -x scripts/ops/restart_app.sh ]] || fail "missing scripts/ops/restart_app.sh"
[[ -x scripts/ops/health_check.sh ]] || fail "missing scripts/ops/health_check.sh"
[[ -x scripts/ops/install_githooks.sh ]] || fail "missing scripts/ops/install_githooks.sh"

hooksPath="$(git config core.hooksPath || true)"
if [[ "${hooksPath}" != ".githooks" ]]; then
  log "[WARN] core.hooksPath is not .githooks (current: ${hooksPath})"
else
  ok "pre-commit hooks installed (.githooks)"
fi

# Restart + health_check (hard)
log ""
log "== restart_app ==" 
bash scripts/ops/restart_app.sh 2>&1 | tee -a "${OUT}"

log ""
log "== health_check ==" 
bash scripts/ops/health_check.sh 2>&1 | tee -a "${OUT}"
ok "health_check executed"

# P1 checks
log ""
log "== P1 checks =="
if [[ -x scripts/ops/gate_all.sh ]]; then
  bash scripts/ops/gate_all.sh 2>&1 | tee -a "${OUT}" || true
  ok "gate_all executed"
else
  log "[WARN] gate_all missing"
fi

if [[ -x scripts/ops/doctor.sh ]]; then
  bash scripts/ops/doctor.sh 2>&1 | tee -a "${OUT}" || true
  ok "doctor executed"
else
  log "[WARN] doctor missing"
fi

# Summarize latest packs
lg="$(ls -td /tmp/xinyi_gate_* 2>/dev/null | head -1 || true)"
ld="$(ls -td /tmp/xinyi_doctor_* 2>/dev/null | head -1 || true)"
log ""
log "latest_gate=${lg}"
log "latest_doctor=${ld}"

ok "UAT gate completed (CI checks must be verified in GitHub UI)."
