#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_SCRIPT="${ROOT_DIR}/scripts/ops/test_smoke.sh"
TMP_LOG="$(mktemp /tmp/smoke_runner.XXXXXX.log)"

cleanup() {
  rm -f "$TMP_LOG"
}
trap cleanup EXIT

run_smoke() {
  local mode="$1"

  : > "$TMP_LOG"
  set +e
  if [ "$mode" = "sudo" ]; then
    sudo bash "$TEST_SCRIPT" 2>&1 | tee "$TMP_LOG"
  else
    bash "$TEST_SCRIPT" 2>&1 | tee "$TMP_LOG"
  fi
  local rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

is_permission_probe_error() {
  grep -Eqi 'Operation not permitted|Errno[[:space:]]*1|errno[[:space:]]*=[[:space:]]*1|Errno[[:space:]]*2003|errno[[:space:]]*=[[:space:]]*2003' "$TMP_LOG"
}

set +e
run_smoke "non-root"
rc=$?
set -e
if [ "$rc" -eq 0 ]; then
  echo "[smoke] PASS (non-root)"
  exit 0
fi

if [ "$rc" -eq 2 ] && is_permission_probe_error; then
  set +e
  run_smoke "sudo"
  rc_sudo=$?
  set -e
  if [ "$rc_sudo" -eq 0 ]; then
    echo "[smoke] PASS (sudo fallback)"
    exit 0
  fi
fi

echo "[smoke] FAIL"
exit "${rc_sudo:-$rc}"
