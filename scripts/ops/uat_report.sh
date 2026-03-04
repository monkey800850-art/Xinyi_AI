#!/usr/bin/env bash
set -euo pipefail

OUT="${OUT:-/tmp/evidence_uat_readiness.md}"

lg="$(ls -td /tmp/xinyi_gate_* 2>/dev/null | head -1 || true)"
ld="$(ls -td /tmp/xinyi_doctor_* 2>/dev/null | head -1 || true)"

{
  echo "# UAT Readiness Report"
  echo ""
  echo "- generated_at: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo ""
  echo "## Latest evidence packs"
  echo "- gate_pack: ${lg}"
  echo "- doctor_pack: ${ld}"
  echo ""

  echo "## P0 (must pass)"
  echo "- restart_app.sh: $( [[ -x scripts/ops/restart_app.sh ]] && echo OK || echo MISSING )"
  echo "- health_check.sh: $( [[ -x scripts/ops/health_check.sh ]] && echo OK || echo MISSING )"
  echo "- hooks installed (.githooks): $( [[ "$(git config core.hooksPath || true)" == ".githooks" ]] && echo OK || echo WARN )"
  echo "- CI required checks: MANUAL VERIFY in GitHub (gate-secrets / ci-smoke / ci-release-gate / ci-hygiene)"
  echo ""

  echo "## P1 (should pass)"
  if [[ -n "${lg}" && -f "${lg}/INDEX.md" ]]; then
    echo "- gate_all INDEX excerpt:"
    sed -n '1,120p' "${lg}/INDEX.md"
  else
    echo "- gate_all: MISSING pack"
  fi
  echo ""

  if [[ -n "${ld}" && -f "${ld}/INDEX.md" ]]; then
    echo "- doctor INDEX excerpt:"
    sed -n '1,160p' "${ld}/INDEX.md"
  else
    echo "- doctor: MISSING pack"
  fi
  echo ""

  echo "## P2 (nice to have)"
  echo "- ops.env present (local, ignored): $( [[ -f var/run/ops.env ]] && echo YES || echo NO )"
  echo "- web_audit_pack.sh: $( [[ -x scripts/ops/web_audit_pack.sh ]] && echo OK || echo MISSING )"
  echo "- ops freeze tags: $(git tag --list 'ops-freeze-*' | tail -n 3 | tr '\n' ' ' || true)"
  echo ""
  echo "## Notes"
  echo "- This report intentionally excludes secrets and credentials."
  echo "- For window switching: run 'bash scripts/ops/project_state.sh' and paste output."
} > "${OUT}"

echo "[OK] wrote ${OUT}"
