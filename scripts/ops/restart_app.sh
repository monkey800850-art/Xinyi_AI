#!/usr/bin/env bash
set -euo pipefail

echo "== restart_app =="
date '+%Y-%m-%d %H:%M (%z)'
echo ""

bash scripts/ops/stop_app.sh
bash scripts/ops/start_app.sh
echo "[OK] restart_app completed."
