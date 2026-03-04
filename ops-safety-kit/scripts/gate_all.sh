#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# OSK profile:
#   local (default): secrets + hygiene only (portable)
#   ci: secrets + hygiene + optional enabled gates
#   prod: all enabled gates
OSK_PROFILE="${OSK_PROFILE:-local}"
OSK_ENABLE_DB_GATES="${OSK_ENABLE_DB_GATES:-0}"   # 1 to enable DB/service bound gates
OSK_ENABLE_RELEASE_GATES="${OSK_ENABLE_RELEASE_GATES:-0}" # 1 to enable release/consolidation chain

echo "== gate_all =="
date '+%Y-%m-%d %H:%M (%z)'
echo "repo=$ROOT"
echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo nogit)"
echo "head=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
echo "OSK_PROFILE=${OSK_PROFILE} OSK_ENABLE_DB_GATES=${OSK_ENABLE_DB_GATES} OSK_ENABLE_RELEASE_GATES=${OSK_ENABLE_RELEASE_GATES}"
echo

run_if_exists() {
  local f="$1"
  if [ -x "$f" ]; then
    bash "$f"
  else
    echo "[SKIP] not executable or missing: $f"
  fi
}

# Required
run_if_exists ops-safety-kit/scripts/gate_secrets.sh

# Portable hygiene (optional but recommended)
if [ -x ops-safety-kit/scripts/gate_hygiene.sh ]; then
  run_if_exists ops-safety-kit/scripts/gate_hygiene.sh
else
  echo "[SKIP] optional gate not present: gate_hygiene.sh"
fi

# Release / consolidation gates: ONLY when explicitly enabled
if [ "${OSK_ENABLE_RELEASE_GATES}" = "1" ] || [ "${OSK_PROFILE}" = "prod" ]; then
  run_if_exists ops-safety-kit/scripts/gate_consolidation.sh
  run_if_exists ops-safety-kit/scripts/gate_release.sh
else
  echo "[SKIP] release/consolidation gates disabled by profile"
fi

# DB/service bound smoke gates: ONLY when explicitly enabled
if [ "${OSK_ENABLE_DB_GATES}" = "1" ] || [ "${OSK_PROFILE}" = "prod" ]; then
  run_if_exists ops-safety-kit/scripts/smoke_auth.sh
  run_if_exists ops-safety-kit/scripts/smoke_dashboard.sh
else
  echo "[SKIP] DB/service bound smoke disabled by profile"
fi

echo "[OK] gate_all passed."
