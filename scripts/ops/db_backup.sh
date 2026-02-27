#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

# Load .env values only for missing vars
if [[ -f "${ENV_FILE}" ]]; then
  while IFS='=' read -r key value; do
    key="$(echo "${key}" | xargs)"
    [[ -z "${key}" || "${key}" =~ ^# ]] && continue
    value="$(echo "${value}" | sed -e 's/^\s*//' -e 's/\s*$//')"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    case "${key}" in
      DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD)
        if [[ -z "${!key:-}" ]]; then
          export "${key}=${value}"
        fi
        ;;
    esac
  done < "${ENV_FILE}"
fi

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-}"
DB_USER="${DB_USER:-}"
DB_PASSWORD="${DB_PASSWORD:-}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
USE_GZIP=0

usage() {
  cat <<USAGE
Usage: scripts/ops/db_backup.sh [options]

Options:
  --host <host>          DB host (default: env DB_HOST or 127.0.0.1)
  --port <port>          DB port (default: env DB_PORT or 3306)
  --db <name>            DB name (default: env DB_NAME)
  --user <user>          DB user (default: env DB_USER)
  --password <password>  DB password (default: env DB_PASSWORD)
  --backup-dir <dir>     Backup output dir (default: ./backups)
  --gzip                 Output .sql.gz file
  -h, --help             Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) DB_HOST="$2"; shift 2 ;;
    --port) DB_PORT="$2"; shift 2 ;;
    --db) DB_NAME="$2"; shift 2 ;;
    --user) DB_USER="$2"; shift 2 ;;
    --password) DB_PASSWORD="$2"; shift 2 ;;
    --backup-dir) BACKUP_DIR="$2"; shift 2 ;;
    --gzip) USE_GZIP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown option: $1"; usage; exit 1 ;;
  esac
done

if ! command -v mysqldump >/dev/null 2>&1; then
  echo "[ERROR] mysqldump not found. Install MySQL client tools first."
  exit 1
fi

if [[ "${USE_GZIP}" == "1" ]] && ! command -v gzip >/dev/null 2>&1; then
  echo "[ERROR] gzip not found, but --gzip was requested."
  exit 1
fi

for required in DB_NAME DB_USER DB_PASSWORD; do
  if [[ -z "${!required:-}" ]]; then
    echo "[ERROR] Missing required config: ${required}"
    exit 1
  fi
done

if ! mkdir -p "${BACKUP_DIR}"; then
  echo "[ERROR] Cannot create backup dir: ${BACKUP_DIR}"
  exit 1
fi

if [[ ! -w "${BACKUP_DIR}" ]]; then
  echo "[ERROR] Backup dir is not writable: ${BACKUP_DIR}"
  exit 1
fi

ts="$(date +%Y%m%d_%H%M%S)"
base_name="${DB_NAME}_${ts}.sql"
out_file="${BACKUP_DIR}/${base_name}"

set +e
if [[ "${USE_GZIP}" == "1" ]]; then
  out_file="${out_file}.gz"
  MYSQL_PWD="${DB_PASSWORD}" mysqldump -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" --single-transaction --routines --triggers --no-tablespaces "${DB_NAME}" | gzip > "${out_file}"
  dump_rc=${PIPESTATUS[0]}
  gzip_rc=${PIPESTATUS[1]:-0}
  rc=$(( dump_rc != 0 ? dump_rc : gzip_rc ))
else
  MYSQL_PWD="${DB_PASSWORD}" mysqldump -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" --single-transaction --routines --triggers --no-tablespaces "${DB_NAME}" > "${out_file}"
  rc=$?
fi
set -e

if [[ ${rc} -ne 0 ]]; then
  echo "[ERROR] Backup failed (exit=${rc}). host=${DB_HOST} port=${DB_PORT} db=${DB_NAME} user=${DB_USER}"
  rm -f "${out_file}" || true
  exit 1
fi

if [[ ! -s "${out_file}" ]]; then
  echo "[ERROR] Backup file was created but empty: ${out_file}"
  rm -f "${out_file}" || true
  exit 1
fi

size_bytes="$(wc -c < "${out_file}" | tr -d ' ')"
echo "[OK] backup completed"
echo "file=${out_file}"
echo "size_bytes=${size_bytes}"
echo "db=${DB_NAME} host=${DB_HOST} port=${DB_PORT}"
