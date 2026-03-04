#!/usr/bin/env bash
set -euo pipefail

TS="$(date '+%Y%m%d_%H%M%S')"
OUT="/tmp/xinyi_audit_${TS}"
mkdir -p "${OUT}"

echo "OUT=${OUT}"

# Baseline
{
  echo "## Baseline"
  echo "- date: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- pwd: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo ""
} > "${OUT}/INDEX.md"

# Commit snapshot (latest)
{
  echo "## Latest commit"
  git log -1 --pretty=fuller
  echo ""
  echo "## Latest commit diff (stat)"
  git show --stat --oneline HEAD
} > "${OUT}/commit_latest.txt" || true

# Optional: snapshot a specific commit if provided
COMMIT_ID="${1:-}"
if [[ -n "${COMMIT_ID}" ]]; then
  git show --stat --oneline "${COMMIT_ID}" > "${OUT}/commit_${COMMIT_ID}_stat.txt" || true
  git show "${COMMIT_ID}" > "${OUT}/commit_${COMMIT_ID}.diff" || true
  echo "- commit_snapshot: commit_${COMMIT_ID}.diff" >> "${OUT}/INDEX.md"
fi

# Collect existing evidence files if present
collect() {
  local f="$1"
  if [[ -f "$f" ]]; then
    cp -f "$f" "${OUT}/" || true
    echo "- $(basename "$f"): $(basename "$f")" >> "${OUT}/INDEX.md"
  else
    echo "- $(basename "$f"): (missing)" >> "${OUT}/INDEX.md"
  fi
}

collect_glob() {
  local pattern="$1"
  local matched=0
  shopt -s nullglob
  for f in ${pattern}; do
    matched=1
    cp -f "$f" "${OUT}/" || true
    echo "- $(basename "$f"): $(basename "$f")" >> "${OUT}/INDEX.md"
  done
  shopt -u nullglob
  if [[ "${matched}" -eq 0 ]]; then
    echo "- ${pattern}: (missing)" >> "${OUT}/INDEX.md"
  fi
}

echo "" >> "${OUT}/INDEX.md"
echo "## Evidence files" >> "${OUT}/INDEX.md"
collect /tmp/evidence_smoke_auth.txt
collect /tmp/evidence_health_check.txt
collect /tmp/evidence_smoke_dashboard.txt
collect /tmp/evidence_secret_history_scan.txt
collect /tmp/evidence_secret_history_hits.txt
collect_glob "/tmp/evidence_uat_run*.txt"
collect_glob "/tmp/evidence_uat_auth_run*.txt"
collect_glob "/tmp/evidence_ui_smoke*.txt"

# Local keyword scan (working tree) - filenames only
{
  echo "## Working tree keyword scan (filenames only)"
  rg -n --hidden -g '!.git' \
    -S 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|Authorization:\s*Bearer|SECRET_KEY\s*=|TOKEN\s*=' \
    . 2>/dev/null | cut -d: -f1 | sort -u || true
} > "${OUT}/working_tree_scan_files.txt"

echo "- working_tree_scan_files: working_tree_scan_files.txt" >> "${OUT}/INDEX.md"

# ---- AUDIT INDEX ----
lg="$(ls -td /tmp/xinyi_gate_* 2>/dev/null | head -1 || true)"
ld="$(ls -td /tmp/xinyi_doctor_* 2>/dev/null | head -1 || true)"

{
  echo "# Xinyi Web Audit Pack"
  echo ""
  echo "## Baseline"
  echo "- date: $(date '+%Y-%m-%d %H:%M (%z)')"
  echo "- repo: $(pwd)"
  echo "- branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  echo "- head: $(git rev-parse --short HEAD 2>/dev/null || true)"
  echo ""
  echo "## Latest Packs"
  echo "- latest_gate: ${lg}"
  echo "- latest_doctor: ${ld}"
  echo "- this_audit: ${OUT}"
  echo ""
  echo "## Collected Evidence Files"
  (cd "${OUT}" && ls -1 | sed 's/^/- /')
  echo ""
  if [[ -n "${lg}" && -f "${lg}/INDEX.md" ]]; then
    echo "## Gate INDEX excerpt"
    sed -n '1,160p' "${lg}/INDEX.md"
    echo ""
  fi
  if [[ -n "${ld}" && -f "${ld}/INDEX.md" ]]; then
    echo "## Doctor INDEX excerpt"
    sed -n '1,200p' "${ld}/INDEX.md"
    echo ""
  fi
  echo "## Window Recovery Hint"
  echo "Run: bash scripts/ops/project_state.sh"
} > "${OUT}/INDEX.md"

echo ""
echo "Audit pack created:"
echo "${OUT}"
echo ""
echo "Show index:"
sed -n '1,120p' "${OUT}/INDEX.md"
