#!/usr/bin/env bash
set -euo pipefail

# load optional ops env (local, not committed)
OPS_ENV_FILE="${OPS_ENV_FILE:-var/run/ops.env}"
if [[ -f "${OPS_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${OPS_ENV_FILE}"
fi

TS="$(date '+%Y%m%d_%H%M%S')"
OUT="/tmp/xinyi_gate_${TS}"
mkdir -p "${OUT}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

printf 'OUT=%s\n' "${OUT}"

idx="${OUT}/INDEX.md"
{
  echo "# Xinyi Gate Run"
  echo ""
  echo "## Baseline"
  echo "- date: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo "- BASE_URL: ${BASE_URL}"
  echo "- NO_PROXY_OPT: ${NO_PROXY_OPT}"
  echo ""
  echo "## Evidence"
} > "${idx}"

declare -A STEP_RC
declare -A STEP_NOTE

run_step() {
  local name="$1"
  shift
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
  local rc="${PIPESTATUS[0]}"
  set -e

  {
    echo "---"
    echo "exit_code=${rc}"
  } >> "${file}"

  STEP_RC["${name}"]="${rc}"
}

mark_skip() {
  local name="$1"
  local reason="$2"
  STEP_RC["${name}"]=""
  STEP_NOTE["${name}"]="SKIP (${reason})"
}

# 1) gate_secrets
if [[ -f scripts/ops/gate_secrets.sh ]]; then
  run_step "gate_secrets" "bash scripts/ops/gate_secrets.sh"
else
  mark_skip "gate_secrets" "missing"
fi

# 1.5) hygiene gate (staged names like .env / Zone.Identifier / cert files)
if [[ -f scripts/ops/gate_hygiene.sh ]]; then
  run_step "gate_hygiene" "bash scripts/ops/gate_hygiene.sh"
  echo "- gate_hygiene: DONE" >> "${idx}"
else
  echo "- gate_hygiene: SKIP (missing)" >> "${idx}"
fi


# 2) start_app (best-effort bootstrap before checks)
if [[ -x scripts/ops/start_app.sh ]]; then
  run_step "start_app" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/start_app.sh"
else
  mark_skip "start_app" "missing or not executable"
fi

# 3) health_check
if [[ -x scripts/ops/health_check.sh ]]; then
  run_step "health_check" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/health_check.sh"
else
  mark_skip "health_check" "missing or not executable"
fi

# 3.5) smoke_ui (curl-based UI reachability)
if [[ -x scripts/ops/smoke_ui.sh ]]; then
  run_step "smoke_ui" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" bash scripts/ops/smoke_ui.sh"
else
  mark_skip "smoke_ui" "missing or not executable"
fi

# 4) smoke_auth (requires admin password)
if [[ -x scripts/ops/smoke_auth.sh ]]; then
  if [[ -n "${ADMIN_PASSWORD:-}" || -n "${ADMIN_PASS:-}" ]]; then
    run_step "smoke_auth" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" ADMIN_PASSWORD=\"${ADMIN_PASSWORD:-}\" ADMIN_PASS=\"${ADMIN_PASS:-}\" bash scripts/ops/smoke_auth.sh"
  else
    mark_skip "smoke_auth" "ADMIN_PASSWORD not set"
  fi
else
  mark_skip "smoke_auth" "missing or not executable"
fi

# 5) smoke_dashboard (auth usually required)
if [[ -x scripts/ops/smoke_dashboard.sh ]]; then
  if [[ -n "${ADMIN_PASSWORD:-}" || -n "${ADMIN_PASS:-}" ]]; then
    run_step "smoke_dashboard" "HOST=${HOST} PORT=${PORT} BASE_URL=${BASE_URL} NO_PROXY_OPT=\"${NO_PROXY_OPT}\" ADMIN_PASSWORD=\"${ADMIN_PASSWORD:-}\" ADMIN_PASS=\"${ADMIN_PASS:-}\" bash scripts/ops/smoke_dashboard.sh"
  else
    mark_skip "smoke_dashboard" "ADMIN_PASSWORD not set"
  fi
else
  mark_skip "smoke_dashboard" "missing or not executable"
fi

# Summarize
{
  echo ""
  echo "## Results"
} >> "${idx}"

overall_fail=0
for name in gate_secrets start_app health_check smoke_ui smoke_auth smoke_dashboard; do
  rc="${STEP_RC[$name]:-}"
  if [[ -z "${rc}" ]]; then
    note="${STEP_NOTE[$name]:-SKIP}"
    echo "- ${name}: ${note}" >> "${idx}"
  elif [[ "${rc}" == "0" ]]; then
    echo "- ${name}: PASS" >> "${idx}"
  else
    echo "- ${name}: FAIL (exit=${rc})" >> "${idx}"
    overall_fail=1
  fi
done

echo ""
echo "[OK] gate run completed: ${OUT}"
echo "Show index:"
sed -n '1,200p' "${idx}"

exit "${overall_fail}"
