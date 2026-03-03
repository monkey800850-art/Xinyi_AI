#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "== Xinyi AI Dev Startup =="

# 1. Check python
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

# 2. Create venv if missing
if [ ! -f "venv/bin/activate" ]; then
  echo "[1/6] Creating venv..."
  python3 -m venv venv
fi

echo "[2/6] Activate venv..."
source venv/bin/activate

# 3. Install dependencies if needed
if ! python -m flask --version >/dev/null 2>&1; then
  echo "[3/6] Installing dependencies..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "[3/6] Dependencies OK"
fi

# 4. Run migration
echo "[4/6] Running migration..."
PYTHONPATH=. alembic upgrade head

# 5. Start server
echo "[5/6] Starting server..."
python3 run_dev.py &

sleep 2

# 6. Verify port
if ss -lntp | grep -q ':5000'; then
  echo "[6/6] Server running on http://localhost:5000"
else
  echo "ERROR: server did not start"
  exit 1
fi

echo "== Startup Complete =="
