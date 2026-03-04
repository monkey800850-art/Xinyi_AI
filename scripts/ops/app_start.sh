#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="${LOG_FILE:-/tmp/xinyi/xinyi_app_500.log}"

# 1) stop existing
pkill -f "python3 app.py" >/dev/null 2>&1 || true

# 2) start
cd "$APP_DIR"
nohup python3 app.py > "$LOG_FILE" 2>&1 &

sleep 1
echo "STARTED pid=$!"
echo "LOG=$LOG_FILE"
ss -lntp | grep ':5000' || (echo "NO_LISTEN_5000" && tail -n 120 "$LOG_FILE" && exit 1)

# 3) quick health
curl -sS --noproxy '*' -m 3 -o /dev/null -w "ROOT_HTTP=%{http_code}\n" http://127.0.0.1:5000/ || true
