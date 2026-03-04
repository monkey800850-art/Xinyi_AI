#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="${LOG_FILE:-/tmp/xinyi/xinyi_app_500.log}"
echo "== LISTEN :5000 =="
ss -lntp | grep ':5000' || echo "NO_LISTEN_5000"
echo "== PROCESS =="
ps -ef | egrep "python3 app.py" | grep -v egrep || echo "NO_PROCESS"
echo "== LOG TAIL =="
tail -n 80 "$LOG_FILE" 2>/dev/null || echo "NO_LOG ($LOG_FILE)"
