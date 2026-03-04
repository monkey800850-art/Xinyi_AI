#!/usr/bin/env bash
set -euo pipefail

# Always anchor to repo root (portable; avoids '~' issues)
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# OSK profile:
#   local (default): secrets + hygiene only
#   ci: secrets + hygiene + optional enabled gates
#   prod: all enabled gates
OSK_PROFILE="${OSK_PROFILE:-local}"
OSK_ENABLE_DB_GATES="${OSK_ENABLE_DB_GATES:-0}"          # 1 enables DB/service smoke
OSK_ENABLE_RELEASE_GATES="${OSK_ENABLE_RELEASE_GATES:-0}" # 1 enables release/consolidation chain

echo "== gate_all =="
date '+%Y-%m-%d %H:%M (%z)'
echo "repo=$ROOT"
echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo nogit)"
echo "head=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
echo "OSK_PROFILE=${OSK_PROFILE} OSK_ENABLE_DB_GATES=${OSK_ENABLE_DB_GATES} OSK_ENABLE_RELEASE_GATES=${OSK_ENABLE_RELEASE_GATES}"
echo

run_if_exec() {
  local f="$1"
  if [ -x "$f" ]; then
    bash "$f"
  else
    echo "[SKIP] not executable or missing: $f"
  fi
}

# Required
run_if_exec ops-safety-kit/scripts/gate_secrets.sh

# Portable hygiene
if [ -x ops-safety-kit/scripts/gate_hygiene.sh ]; then
  run_if_exec ops-safety-kit/scripts/gate_hygiene.sh
else
  echo "[SKIP] optional gate not present: gate_hygiene.sh"
fi

# Release / consolidation (explicit)
if [ "${OSK_ENABLE_RELEASE_GATES}" = "1" ] || [ "${OSK_PROFILE}" = "prod" ]; then
  run_if_exec ops-safety-kit/scripts/gate_consolidation.sh
  run_if_exec ops-safety-kit/scripts/gate_release.sh
else
  echo "[SKIP] release/consolidation gates disabled by profile"
fi

# DB/service smoke (explicit)
if [ "${OSK_ENABLE_DB_GATES}" = "1" ] || [ "${OSK_PROFILE}" = "prod" ]; then
  run_if_exec ops-safety-kit/scripts/smoke_auth.sh
  run_if_exec ops-safety-kit/scripts/smoke_dashboard.sh
else
  echo "[SKIP] DB/service bound smoke disabled by profile"
fi

scripts/ops/check_no_tee_mask.sh

echo "[OK] gate_all passed."

# [UI-WIRE] catalog schema gate
python3 scripts/ui/check_modules_catalog.py
# --- HOOK: REPORTS-QUERY-13 invariants (no Flask dependency) ---
if [ -f "tests/scripts/reports_query_13_invariants.py" ]; then
  echo "[gate] running REPORTS-QUERY-13 invariants..."
  python3 tests/scripts/reports_query_13_invariants.py
fi
# --- END HOOK ---
