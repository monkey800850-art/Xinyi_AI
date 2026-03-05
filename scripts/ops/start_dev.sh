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

# 1) Ensure venv runtime
if [ ! -x "venv/bin/python3" ]; then
  echo "[1/6] Creating venv..."
  python3 -m venv venv
fi

echo "[2/6] Activating venv..."
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
else
  export VIRTUAL_ENV="$ROOT_DIR/venv"
  export PATH="$ROOT_DIR/venv/bin:$PATH"
fi

if [ ! -x "venv/bin/python" ] && [ -x "venv/bin/python3" ]; then
  ln -sf python3 venv/bin/python
fi

# 2) Load local dotenv (development only)
set -a
[ -f "$ROOT_DIR/.env" ] && . "$ROOT_DIR/.env"
set +a

echo "DB_HOST=${DB_HOST:-<missing>}"
echo "DB_PORT=${DB_PORT:-<missing>}"
echo "DB_USER=${DB_USER:-<missing>}"
echo "DB_NAME=${DB_NAME:-<missing>}"
if [ -n "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL=<set>"
else
  echo "DATABASE_URL=<missing>"
fi

missing_db_vars=()
for key in DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME; do
  if [ -z "${!key:-}" ]; then
    missing_db_vars+=("$key")
  fi
done
if [ ${#missing_db_vars[@]} -gt 0 ]; then
  echo "FATAL: missing DB env: ${missing_db_vars[*]}"
  echo "Please copy .env.example to .env and fill DB credentials."
  exit 2
fi

# 2) Ensure deps (quick check)
if ! python -c "import flask" >/dev/null 2>&1; then
  echo "[3/6] Installing dependencies..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "[3/6] Dependencies OK"
fi

# 3) DB connectivity precheck
python - <<'PY'
import os, sys
host = os.getenv("DB_HOST")
port = os.getenv("DB_PORT", "3306")
user = os.getenv("DB_USER")
pwd = os.getenv("DB_PASSWORD", "")
name = os.getenv("DB_NAME")
if not all([host, user, name]):
    print("FATAL: missing DB_* env; see .env.example")
    sys.exit(2)
try:
    import pymysql
except Exception as e:
    print("FATAL: pymysql missing:", e)
    sys.exit(2)
try:
    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=user,
        password=pwd,
        database=name,
        connect_timeout=3,
    )
    conn.close()
    print("DB_CONNECT_OK")
except Exception as e:
    print("FATAL: mysql connect failed:", repr(e))
    sys.exit(2)
PY

# 3) Migrate
echo "[4/6] Running migration..."
PYTHONPATH=. python -m alembic upgrade head

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
