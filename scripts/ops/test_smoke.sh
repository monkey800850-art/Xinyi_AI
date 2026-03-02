#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Fixed smoke DB env; intentionally isolated from caller/.env.
DB_HOST="127.0.0.1"
DB_PORT="3306"
DB_NAME="xinyi_ai"
DB_USER="root"
DB_PASSWORD="88888888"

mkdir -p _health
LOG_FILE="_health/test_smoke_last.txt"
START_TS="$(date +%s)"

run_isolated() {
  env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    DB_HOST="$DB_HOST" \
    DB_PORT="$DB_PORT" \
    DB_NAME="$DB_NAME" \
    DB_USER="$DB_USER" \
    DB_PASSWORD="$DB_PASSWORD" \
    "$@"
}

echo "[smoke] start"
echo "[smoke] db=${DB_HOST}:${DB_PORT}/${DB_NAME} user=${DB_USER}"

# DB probe step 1: TCP reachability is a hard gate.
tcp_probe_err=""
if ! tcp_probe_err="$(run_isolated python3 - <<'PY' 2>&1
import os
import socket
import sys

host = os.getenv("DB_HOST", "127.0.0.1")
port = int(os.getenv("DB_PORT", "3306"))

try:
    with socket.create_connection((host, port), timeout=2):
        pass
except Exception as exc:
    print(f"tcp_connect_failed: {exc}", file=sys.stderr)
    sys.exit(2)
PY
)"; then
  elapsed="$(( $(date +%s) - START_TS ))"
  reason="$(echo "$tcp_probe_err" | tail -n 1)"
  echo "[smoke] db probe failed: ${reason}"
  echo "[smoke] summary: FAIL (db_probe) elapsed=${elapsed}s"
  exit 2
fi

# DB probe step 2: retry pymysql probe to reduce flaky startup failures.
set +e
db_probe_err="$(run_isolated python3 - <<'PY' 2>&1
import os
import sys
import time
import pymysql

host = os.getenv("DB_HOST", "127.0.0.1")
port = int(os.getenv("DB_PORT", "3306"))
db = os.getenv("DB_NAME", "xinyi_ai")
user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "88888888")

def should_fallback(exc):
    text = str(exc).lower()
    if "operation not permitted" in text:
        return True
    if "errno 1" in text:
        return True
    if "2003" in text:
        return True
    if getattr(exc, "args", None):
        first = exc.args[0]
        if first in (1, 2003):
            return True
    return False

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

if last_err is None:
    print("DB probe failed after 5 attempts: unknown error", file=sys.stderr)
    sys.exit(2)

if should_fallback(last_err):
    print(f"DB probe failed after 5 attempts: {last_err}", file=sys.stderr)
    sys.exit(10)

print(f"DB probe failed after 5 attempts: {last_err}", file=sys.stderr)
sys.exit(2)
PY
)"; db_probe_rc=$?
set -e

if [ "$db_probe_rc" -eq 0 ]; then
  echo "[smoke] db probe ok: pymysql"
elif [ "$db_probe_rc" -eq 10 ]; then
  set +e
  mysql_probe_err="$(run_isolated mysql \
    --protocol=TCP \
    --connect-timeout=2 \
    -h"$DB_HOST" \
    -P"$DB_PORT" \
    -u"$DB_USER" \
    -p"$DB_PASSWORD" \
    "$DB_NAME" \
    -e "SELECT 1;" 2>&1)"
  mysql_probe_rc=$?
  set -e

  if [ "$mysql_probe_rc" -eq 0 ]; then
    echo "[smoke] db probe ok: mysql_cli_fallback"
  else
    elapsed="$(( $(date +%s) - START_TS ))"
    reason="$(echo "${mysql_probe_err:-$db_probe_err}" | tail -n 1)"
    echo "[smoke] db probe failed: ${reason}"
    echo "[smoke] summary: FAIL (db_probe) elapsed=${elapsed}s"
    exit 2
  fi
else
  elapsed="$(( $(date +%s) - START_TS ))"
  reason="$(echo "$db_probe_err" | tail -n 1)"
  echo "[smoke] db probe failed: ${reason}"
  echo "[smoke] summary: FAIL (db_probe) elapsed=${elapsed}s"
  exit 2
fi

set +e
run_isolated python3 -m pytest -q --maxfail=1 \
  tests/test_arch02_db_router.py \
  tests/test_arch02_service_router_integration.py \
  tests/test_arch04_consolidation_model.py \
  tests/test_arch05_consolidation_reports.py \
  > >(tee "$LOG_FILE") 2>&1
pytest_rc=$?
set -e

tail -n 20 "$LOG_FILE"
elapsed="$(( $(date +%s) - START_TS ))"
if [ "$pytest_rc" -eq 0 ]; then
  echo "[smoke] summary: PASS elapsed=${elapsed}s log=${LOG_FILE}"
else
  echo "[smoke] summary: FAIL (pytest_rc=${pytest_rc}) elapsed=${elapsed}s log=${LOG_FILE}"
fi
exit "$pytest_rc"
