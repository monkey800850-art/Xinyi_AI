#!/usr/bin/env bash
set -euo pipefail
echo "[DEPRECATED] use ops-safety-kit/scripts/* (single source)" >&2
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
bash ops-safety-kit/scripts/gate_all.sh
