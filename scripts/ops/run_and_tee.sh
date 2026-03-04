#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/ops/run_and_tee.sh "<cmd...>" "<logfile>"
#
# Example:
#   scripts/ops/run_and_tee.sh "python3 scripts/payroll/uat_payroll_mvp_offline.py" "evidence/x.txt"

if [[ $# -lt 2 ]]; then
  echo "usage: $0 \"<command>\" <logfile>" >&2
  exit 2
fi

CMD="$1"
LOG="$2"

mkdir -p "$(dirname "$LOG")"

# Print command header for traceability
{
  echo "== run_and_tee =="
  echo "cmd=$CMD"
  echo "pwd=$(pwd)"
  echo "ts=$(date -Iseconds)"
  echo
} | tee "$LOG" >/dev/null

# Execute command and tee output; pipefail makes failures propagate
bash -lc "$CMD" 2>&1 | tee -a "$LOG" >/dev/null
