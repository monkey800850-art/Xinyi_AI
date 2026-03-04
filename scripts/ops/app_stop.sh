#!/usr/bin/env bash
set -euo pipefail
pkill -f "python3 app.py" >/dev/null 2>&1 || true
echo "STOPPED"
