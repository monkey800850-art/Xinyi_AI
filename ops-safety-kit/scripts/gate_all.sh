#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "== gate_all =="
date '+%Y-%m-%d %H:%M (%z)'
echo "repo=$ROOT"
echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo nogit)"
echo "head=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
echo

if [ -x ops-safety-kit/scripts/gate_secrets.sh ]; then
  bash ops-safety-kit/scripts/gate_secrets.sh
else
  echo "[FAIL] missing ops-safety-kit/scripts/gate_secrets.sh"
  exit 1
fi

for g in gate_hygiene.sh gate_release.sh gate_consolidation.sh; do
  if [ -x "ops-safety-kit/scripts/${g}" ]; then
    bash "ops-safety-kit/scripts/${g}"
  else
    echo "[SKIP] optional gate not present: ${g}"
  fi
done

echo "[OK] gate_all passed."
