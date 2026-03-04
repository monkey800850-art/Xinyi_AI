#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== OSK install =="
date '+%Y-%m-%d %H:%M (%z)'
echo "repo=$ROOT"

chmod +x ops-safety-kit/scripts/*.sh 2>/dev/null || true
chmod +x ops-safety-kit/.githooks/pre-commit

git config core.hooksPath ops-safety-kit/.githooks

E="/tmp/evidence_osk_install.txt"
: > "$E"
echo "==[OSK] install evidence ==" >> "$E"
date '+%Y-%m-%d %H:%M (%z)' >> "$E"
echo "hooksPath=$(git config core.hooksPath)" >> "$E"
ls -l ops-safety-kit/.githooks/pre-commit >> "$E"

echo "[OK] installed. Evidence: $E"
