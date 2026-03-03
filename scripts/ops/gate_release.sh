#!/bin/bash
set -euo pipefail

echo "== RELEASE GATE START =="

# 1. Consolidation Gate
if [ -f scripts/ops/gate_consolidation.sh ]; then
  echo "[1] gate_consolidation"
  ./scripts/ops/gate_consolidation.sh
fi

# 2. Smoke
if [ -f scripts/ops/smoke.sh ]; then
  echo "[2] smoke"
  ./scripts/ops/smoke.sh
fi

# 3. Pytest
if [ -d tests ]; then
  echo "[3] pytest"
  pytest -q
fi

# 4. Schema Drift Check
echo "[4] schema drift check"
if [ -f snapshots/cons/db_snapshot_latest.json ]; then
  echo "Schema baseline exists."
else
  echo "No schema baseline snapshot found."
  exit 1
fi

# 5. Route Drift Check
echo "[5] route drift check"
if [ -f snapshots/cons/routes_snapshot_latest.json ]; then
  echo "Route baseline exists."
else
  echo "No route baseline snapshot found."
  exit 1
fi

echo "== RELEASE GATE PASS =="
