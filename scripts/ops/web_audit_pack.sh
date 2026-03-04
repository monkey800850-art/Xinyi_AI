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

echo "" >> "${OUT}/INDEX.md"
echo "## Evidence files" >> "${OUT}/INDEX.md"
collect /tmp/evidence_smoke_auth.txt
collect /tmp/evidence_health_check.txt
collect /tmp/evidence_smoke_dashboard.txt
collect /tmp/evidence_secret_history_scan.txt
collect /tmp/evidence_secret_history_hits.txt

# Local keyword scan (working tree) - filenames only
{
  echo "## Working tree keyword scan (filenames only)"
  rg -n --hidden -g '!.git' \
    -S 'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|xox[baprs]-|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|Authorization:\s*Bearer|SECRET_KEY\s*=|TOKEN\s*=' \
    . 2>/dev/null | cut -d: -f1 | sort -u || true
} > "${OUT}/working_tree_scan_files.txt"

echo "- working_tree_scan_files: working_tree_scan_files.txt" >> "${OUT}/INDEX.md"

echo ""
echo "Audit pack created:"
echo "${OUT}"
echo ""
echo "Show index:"
sed -n '1,120p' "${OUT}/INDEX.md"
