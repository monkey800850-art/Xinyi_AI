#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-xinyi_ai}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-88888888}"

mkdir -p _health
LOG_FILE="_health/test_smoke_last.txt"

# DB probe: retry 5 times to reduce flaky startup failures.
if python3 - <<'PY'
import os
import sys
import time
import pymysql

host = os.getenv("DB_HOST", "127.0.0.1")
port = int(os.getenv("DB_PORT", "3306"))
db = os.getenv("DB_NAME", "xinyi_ai")
user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "88888888")

last_err = None
for i in range(5):
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db,
            connect_timeout=2,
            read_timeout=2,
            write_timeout=2,
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        sys.exit(0)
    except Exception as exc:
        last_err = exc
        if i < 4:
            time.sleep(0.4)

print(f"DB probe failed after 5 attempts: {last_err}", file=sys.stderr)
sys.exit(2)
PY
then :; else
  exit $?
fi

echo "DB probe ok"

env -i \
  PATH="$PATH" \
  HOME="$HOME" \
  DB_HOST="$DB_HOST" \
  DB_PORT="$DB_PORT" \
  DB_NAME="$DB_NAME" \
  DB_USER="$DB_USER" \
  DB_PASSWORD="$DB_PASSWORD" \
  python3 -m pytest -q --maxfail=1 \
    tests/test_arch02_db_router.py \
    tests/test_arch02_service_router_integration.py \
    tests/test_arch04_consolidation_model.py \
    tests/test_arch05_consolidation_reports.py \
    > >(tee "$LOG_FILE") 2>&1 || pytest_rc=$?

pytest_rc=${pytest_rc:-0}
tail -n 20 "$LOG_FILE"
exit "$pytest_rc"
