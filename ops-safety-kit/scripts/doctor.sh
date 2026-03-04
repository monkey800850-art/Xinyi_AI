#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

OUT_DIR="/tmp/osk_run_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT_DIR"

echo "== doctor ==" | tee "$OUT_DIR/INDEX.md"
{
  echo "- date: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $ROOT"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo nogit)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
} | tee -a "$OUT_DIR/INDEX.md"

echo "" | tee -a "$OUT_DIR/INDEX.md"
echo "## Evidence" | tee -a "$OUT_DIR/INDEX.md"

echo "" | tee -a "$OUT_DIR/INDEX.md"
echo "### gate_all" | tee -a "$OUT_DIR/INDEX.md"
if bash ops-safety-kit/scripts/gate_all.sh >"$OUT_DIR/evidence_gate_all.txt" 2>&1; then
  echo "- gate_all: PASS (evidence_gate_all.txt)" | tee -a "$OUT_DIR/INDEX.md"
else
  echo "- gate_all: FAIL (evidence_gate_all.txt)" | tee -a "$OUT_DIR/INDEX.md"
fi

echo "" | tee -a "$OUT_DIR/INDEX.md"
echo "### health_check" | tee -a "$OUT_DIR/INDEX.md"
if [ -x ops-safety-kit/scripts/health_check.sh ]; then
  if bash ops-safety-kit/scripts/health_check.sh >"$OUT_DIR/evidence_health_check.txt" 2>&1; then
    echo "- health_check: PASS (evidence_health_check.txt)" | tee -a "$OUT_DIR/INDEX.md"
  else
    echo "- health_check: FAIL (evidence_health_check.txt)" | tee -a "$OUT_DIR/INDEX.md"
  fi
else
  echo "- health_check: SKIP (not packaged)" | tee -a "$OUT_DIR/INDEX.md"
fi

echo "" | tee -a "$OUT_DIR/INDEX.md"
echo "### project_state" | tee -a "$OUT_DIR/INDEX.md"
if [ -x ops-safety-kit/scripts/project_state.sh ]; then
  bash ops-safety-kit/scripts/project_state.sh >"$OUT_DIR/evidence_project_state.txt" 2>&1 || true
  echo "- project_state: DONE (evidence_project_state.txt)" | tee -a "$OUT_DIR/INDEX.md"
else
  echo "- project_state: SKIP (not packaged)" | tee -a "$OUT_DIR/INDEX.md"
fi

echo ""
echo "[OK] doctor run packaged at: $OUT_DIR"
