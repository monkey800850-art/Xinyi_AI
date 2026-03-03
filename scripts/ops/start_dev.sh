#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "== Xinyi AI Dev Startup =="

# 0) Preflight
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

# 1) Ensure venv
if [ ! -f "venv/bin/activate" ]; then
  echo "[1/6] Creating venv..."
  python3 -m venv venv
fi

echo "[2/6] Activating venv..."
source venv/bin/activate

# 2) Ensure deps (quick check)
if ! python -c "import flask" >/dev/null 2>&1; then
  echo "[3/6] Installing dependencies..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "[3/6] Dependencies OK"
fi

# 3) Migrate
echo "[4/6] Running migration..."
PYTHONPATH=. alembic upgrade head

# 4) Start server if not running
echo "[5/6] Starting server..."
if ss -lntp 2>/dev/null | grep -q ':5000'; then
  echo "Port 5000 already in use - assume server running."
else
  nohup python3 run_dev.py > logs/dev.log 2>&1 &
  sleep 1
fi

# 5) Verify
echo "[6/6] Verify..."
if ss -lntp 2>/dev/null | grep -q ':5000'; then
  echo "Server OK: http://localhost:5000/dashboard"
else
  echo "ERROR: server did not start. See logs/dev.log"
  exit 1
fi
