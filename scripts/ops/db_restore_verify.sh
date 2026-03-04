#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"
DUMP_FILE="${DUMP_FILE:-}"
RESTORE_DB="${RESTORE_DB:-xinyi_ai_restore_verify_$(date +%Y%m%d_%H%M%S)}"
DROP_AFTER_VERIFY="${DROP_AFTER_VERIFY:-1}"

usage() {
  cat <<EOF
Usage: scripts/ops/db_restore_verify.sh --dump-file <path> [options]

Options:
  --dump-file <path>       Required SQL dump file path
  --restore-db <name>      Restore target database name
  --keep-db                Keep restore DB after verify
  --host <host>            DB host (default: 127.0.0.1)
  --port <port>            DB port (default: 3306)
  --user <user>            DB user (default: root)
  --password <pwd>         DB password (default: from env)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dump-file) DUMP_FILE="$2"; shift 2 ;;
    --restore-db) RESTORE_DB="$2"; shift 2 ;;
    --keep-db) DROP_AFTER_VERIFY=0; shift 1 ;;
    --host) DB_HOST="$2"; shift 2 ;;
    --port) DB_PORT="$2"; shift 2 ;;
    --user) DB_USER="$2"; shift 2 ;;
    --password) DB_PASSWORD="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "${DUMP_FILE}" ]]; then
  echo "[ERROR] --dump-file is required"
  usage
  exit 2
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "[ERROR] dump file not found: ${DUMP_FILE}"
  exit 2
fi

MYSQL_PWD="${DB_PASSWORD}" mysql -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" \
  -e "CREATE DATABASE IF NOT EXISTS \`${RESTORE_DB}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

MYSQL_PWD="${DB_PASSWORD}" mysql -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" "${RESTORE_DB}" < "${DUMP_FILE}"

table_count=$(MYSQL_PWD="${DB_PASSWORD}" mysql -N -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" "${RESTORE_DB}" \
  -e "SELECT COUNT(1) FROM information_schema.tables WHERE table_schema='${RESTORE_DB}';")
books_count=$(MYSQL_PWD="${DB_PASSWORD}" mysql -N -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" "${RESTORE_DB}" \
  -e "SELECT COUNT(1) FROM books;")
subjects_count=$(MYSQL_PWD="${DB_PASSWORD}" mysql -N -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" "${RESTORE_DB}" \
  -e "SELECT COUNT(1) FROM subjects;")

echo "[OK] restore_verify_passed"
echo "restore_db=${RESTORE_DB}"
echo "table_count=${table_count}"
echo "books_count=${books_count}"
echo "subjects_count=${subjects_count}"

if [[ "${DROP_AFTER_VERIFY}" == "1" ]]; then
  MYSQL_PWD="${DB_PASSWORD}" mysql -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" \
    -e "DROP DATABASE IF EXISTS \`${RESTORE_DB}\`;"
  echo "cleanup=dropped"
else
  echo "cleanup=kept"
fi
