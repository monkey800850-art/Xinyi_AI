#!/usr/bin/env bash
set -euo pipefail

OUT="${OUT:-/tmp/evidence_uat_exit_report.md}"

lg="$(ls -td /tmp/xinyi_gate_* 2>/dev/null | head -1 || true)"
ld="$(ls -td /tmp/xinyi_doctor_* 2>/dev/null | head -1 || true)"
la="$(ls -td /tmp/xinyi_audit_* 2>/dev/null | head -1 || true)"

{
  echo "# UAT Exit Report (Engineering-UAT Preparation)"
  echo ""
  echo "- generated_at: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo ""
  echo "## Latest evidence packs"
  echo "- gate_pack: ${lg}"
  echo "- doctor_pack: ${ld}"
  echo "- audit_pack: ${la}"
  echo ""

  echo "## Local entrypoints"
  for f in scripts/ops/start_app.sh scripts/ops/stop_app.sh scripts/ops/restart_app.sh \
           scripts/ops/health_check.sh scripts/ops/gate_all.sh scripts/ops/doctor.sh \
           scripts/ops/project_state.sh scripts/ops/uat_run.sh scripts/ops/uat_auth_run.sh \
           scripts/ops/web_audit_pack.sh; do
    if [[ -x "$f" ]]; then
      echo "- ${f}: OK"
    else
      echo "- ${f}: MISSING/NOT-EXEC"
    fi
  done
  echo ""

  echo "## Hook status"
  hp="$(git config core.hooksPath || true)"
  echo "- core.hooksPath: ${hp}"
  echo ""

  if [[ -n "${lg}" && -f "${lg}/INDEX.md" ]]; then
    echo "## Gate INDEX excerpt"
    sed -n '1,220p' "${lg}/INDEX.md"
    echo ""
  else
    echo "## Gate INDEX excerpt"
    echo "- missing gate pack"
    echo ""
  fi

  if [[ -n "${ld}" && -f "${ld}/INDEX.md" ]]; then
    echo "## Doctor INDEX excerpt"
    sed -n '1,260p' "${ld}/INDEX.md"
    echo ""
  else
    echo "## Doctor INDEX excerpt"
    echo "- missing doctor pack"
    echo ""
  fi

  if [[ -n "${la}" && -f "${la}/INDEX.md" ]]; then
    echo "## Audit INDEX excerpt"
    sed -n '1,260p' "${la}/INDEX.md"
    echo ""
  else
    echo "## Audit INDEX excerpt"
    echo "- missing audit pack"
    echo ""
  fi

  echo "## CI / Branch Protection (manual confirm)"
  echo "- Verify in GitHub: required checks (gate-secrets, ci-hygiene, ci-smoke, ci-uat, ci-release-gate) PASS on main"
  echo "- Verify branch protection enabled (if desired)"
} > "${OUT}"

echo "[OK] wrote ${OUT}"
