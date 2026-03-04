#!/usr/bin/env bash
set -euo pipefail

echo "[gate] hygiene scan..."

PAT_FILE="scripts/ops/hygiene_patterns.txt"
if [[ ! -f "${PAT_FILE}" ]]; then
  echo "[FAIL] patterns file missing: ${PAT_FILE}"
  exit 1
fi
PAT_TMP="$(mktemp)"
trap 'rm -f "${PAT_TMP}"' EXIT
awk 'NF && $0 !~ /^[[:space:]]*#/' "${PAT_FILE}" > "${PAT_TMP}"

# staged file list
staged="$(git diff --cached --name-only || true)"

fail() { echo "[FAIL] $*"; exit 1; }

# Unified scan using patterns file (filenames only)
if echo "$staged" | rg -n -f "${PAT_TMP}" >/dev/null; then
  echo "$staged" | rg -n -f "${PAT_TMP}" || true
  fail "staged contains hygiene-blocked files (.env / Zone.Identifier / key/cert)"
fi

echo "[OK] hygiene scan passed."
