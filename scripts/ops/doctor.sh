#!/usr/bin/env bash
set -euo pipefail

TS="$(date '+%Y%m%d_%H%M%S')"
OUT="/tmp/xinyi_doctor_${TS}"
mkdir -p "${OUT}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

OPS_ENV_FILE="${OPS_ENV_FILE:-var/run/ops.env}"
if [[ -f "${OPS_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${OPS_ENV_FILE}"
fi

idx="${OUT}/INDEX.md"
{
  echo "# Xinyi Doctor Run"
  echo ""
  echo "## Baseline"
  echo "- date: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "- BASE_URL: ${BASE_URL}"
  echo "- OPS_ENV_FILE: ${OPS_ENV_FILE} ($( [[ -f "${OPS_ENV_FILE}" ]] && echo present || echo missing ))"
  echo ""
  echo "## Evidence"
} > "${idx}"

run_step() {
  local name="$1"; shift
  local cmd="$*"
  local file="${OUT}/evidence_${name}.txt"
  echo "- ${name}: $(basename "${file}")" >> "${idx}"
  {
    echo "== ${name} =="
    echo "cmd: ${cmd}"
    echo "---"
  } > "${file}"

  set +e
  eval "${cmd}" 2>&1 | tee -a "${file}"
  rc="${PIPESTATUS[0]}"
  set -e

  {
    echo "---"
    echo "exit_code=${rc}"
  } >> "${file}"
  return "${rc}"
}

echo "" >> "${idx}"
echo "## Results" >> "${idx}"

# 0) restart app (hard requirement)
if [[ -x scripts/ops/restart_app.sh ]]; then
  run_step "restart_app" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/restart_app.sh"
  echo "- restart_app: DONE" >> "${idx}"
else
  echo "- restart_app: FAIL (missing restart_app.sh)" >> "${idx}"
  exit 1
fi

# 1) gates (soft, but should pass if staged clean)
if [[ -x scripts/ops/gate_secrets.sh ]]; then
  run_step "gate_secrets" "bash scripts/ops/gate_secrets.sh" || true
  echo "- gate_secrets: DONE" >> "${idx}"
fi
if [[ -x scripts/ops/gate_hygiene.sh ]]; then
  run_step "gate_hygiene" "bash scripts/ops/gate_hygiene.sh" || true
  echo "- gate_hygiene: DONE" >> "${idx}"
fi

# 2) health_check (hard requirement)
if [[ -x scripts/ops/health_check.sh ]]; then
  run_step "health_check" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/health_check.sh"
  echo "- health_check: DONE" >> "${idx}"
else
  echo "- health_check: FAIL (missing health_check.sh)" >> "${idx}"
  exit 1
fi

# 3) smokes (optional)
if [[ -x scripts/ops/smoke_auth.sh ]]; then
  if [[ -n "${ADMIN_PASSWORD:-}" || -n "${ADMIN_PASS:-}" ]]; then
    run_step "smoke_auth" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/smoke_auth.sh" || true
    echo "- smoke_auth: DONE" >> "${idx}"
  else
    echo "- smoke_auth: SKIP (no ADMIN_PASSWORD)" >> "${idx}"
  fi
fi

if [[ -x scripts/ops/smoke_dashboard.sh ]]; then
  run_step "smoke_dashboard" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/smoke_dashboard.sh" || true
  echo "- smoke_dashboard: DONE" >> "${idx}"
fi

# 4) audit pack (optional)
if [[ -x scripts/ops/web_audit_pack.sh ]]; then
  run_step "web_audit_pack" "bash scripts/ops/web_audit_pack.sh" || true
  echo "- web_audit_pack: DONE" >> "${idx}"
fi

echo ""
echo "[OK] doctor run completed: ${OUT}"
sed -n '1,220p' "${idx}"
