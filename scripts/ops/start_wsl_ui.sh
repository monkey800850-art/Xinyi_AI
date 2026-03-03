#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

OPEN_BROWSER=0
SKIP_INSTALL=0

for arg in "$@"; do
  case "$arg" in
    --open)
      OPEN_BROWSER=1
      ;;
    --skip-install)
      SKIP_INSTALL=1
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: $0 [--open] [--skip-install]"
      exit 1
      ;;
  esac
done

echo "== WSL UI Quick Start =="
echo "Project: ${ROOT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

if [ ! -d "venv" ]; then
  echo "[1/5] Creating venv"
  python3 -m venv venv
fi

echo "[2/5] Activating venv"
source venv/bin/activate

if [ "${SKIP_INSTALL}" -eq 0 ]; then
  echo "[3/5] Installing dependencies"
  pip install -r requirements.txt
else
  echo "[3/5] Skip dependency install (--skip-install)"
fi

if [ ! -f ".env" ]; then
  echo "WARN: .env not found, creating from .env.example"
  cp .env.example .env
  echo "WARN: please update DB_* values in .env before rerun if needed"
fi

echo "[4/5] Applying migrations"
PYTHONPATH=. alembic upgrade head

echo "[5/5] Starting app on http://localhost:5000"
if [ "${OPEN_BROWSER}" -eq 1 ] && command -v explorer.exe >/dev/null 2>&1; then
  (sleep 2; explorer.exe "http://localhost:5000/dashboard" >/dev/null 2>&1 || true) &
fi

python3 app.py
