#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== OSK uninstall =="
date '+%Y-%m-%d %H:%M (%z)'
echo "repo=$ROOT"

git config --unset core.hooksPath || true

E="/tmp/evidence_osk_uninstall.txt"
: > "$E"
echo "==[OSK] uninstall evidence ==" >> "$E"
date '+%Y-%m-%d %H:%M (%z)' >> "$E"
echo "hooksPath=$(git config core.hooksPath 2>/dev/null || echo unset)" >> "$E"

echo "[OK] uninstalled. Evidence: $E"
