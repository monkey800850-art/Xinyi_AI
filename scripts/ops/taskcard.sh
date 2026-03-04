#!/usr/bin/env bash
set -euo pipefail

# Taskcard helper
# Usage:
#   source scripts/ops/taskcard.sh
#   run "<command>" "evidence/XXX/log.txt"
#
# This ensures command failures propagate even when tee'ing output.
run() {
  if [[ $# -lt 2 ]]; then
    echo "usage: run \"<command>\" <logfile>" >&2
    return 2
  fi
  scripts/ops/run_and_tee.sh "$1" "$2"
}
