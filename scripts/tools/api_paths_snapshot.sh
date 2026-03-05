#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."  # repo root

OUT="docs/evidence/api_paths.txt"
TMP="/tmp/xinyi_ui_api_refs.txt"

grep -RInE "fetch\(|/api/|unauthor|login|auth|session|token|csrf|logout|system_users|users|accounts|subjects|voucher|trial_balance|reports" \
  app/templates app/static app \
  > "$TMP" || true

grep -oE "/api/[A-Za-z0-9_/\-]+" "$TMP" \
  | sort -u > "$OUT" || true

echo "[OK] wrote $OUT"
echo "[INFO] count=$(wc -l < "$OUT" | tr -d ' ')"
