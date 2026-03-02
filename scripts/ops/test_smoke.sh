#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p _health
LOG_FILE="_health/test_smoke_last.txt"

python3 -m pytest -q --maxfail=1 \
  tests/test_arch02_db_router.py \
  tests/test_arch02_service_router_integration.py \
  tests/test_arch04_consolidation_model.py \
  tests/test_arch05_consolidation_reports.py \
  2>&1 | tee "$LOG_FILE"

exit "${PIPESTATUS[0]}"
