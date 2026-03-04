#!/usr/bin/env bash
set -euo pipefail

# Fail if any script under scripts/ uses a masked python->tee pipeline.
# Limit scope to .sh/.md under scripts/ to avoid unrelated noise.

hits=$(grep -RIn \
  --exclude="check_no_tee_mask.sh" \
  --include="*.sh" \
  --include="*.md" \
  -E 'python3[[:space:]].*\|[[:space:]]*tee' scripts/ || true)

if [[ -n "$hits" ]]; then
  echo "[FAIL] Found masked python3 pipeline with tee under scripts/:"
  echo "$hits"
  echo
  echo "Use scripts/ops/run_and_tee.sh or source scripts/ops/taskcard.sh and run() instead."
  exit 1
fi

echo "[OK] no masked python3|tee patterns under scripts/"
