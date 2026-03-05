#!/usr/bin/env bash
set -euo pipefail

TASK="REPORTS-QUERY-14A_SMOKE_FAST"
EVDIR="evidence/${TASK}"
mkdir -p "$EVDIR"

ts(){ date '+%F %T'; }

# 1) 基线
{
  echo "[$(ts)] start"
  date
  pwd
  git rev-parse --abbrev-ref HEAD || true
  git rev-parse HEAD || true
} > "$EVDIR/00_runlog.txt" 2>&1

# 2) 端口快照（可选，缺 ss 也不失败）
( ss -ltnp 2>/dev/null | grep -E '(:5000)\b' || true ) > "$EVDIR/02_port_5000.txt" 2>&1

# 3) 生成并运行 HTTP 探测（标准库，不需要额外依赖）
cat > "$EVDIR/http_probe.py" <<'PY'
import json, sys, time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

URL = "http://127.0.0.1:5000/api/reports/health"

def once():
    req = Request(URL, headers={"Accept":"application/json"})
    with urlopen(req, timeout=2) as r:
        body = r.read().decode("utf-8", errors="replace")
        return r.status, body

last=None
for i in range(1,6):
    try:
        status, body = once()
        print(f"TRY {i}: status={status}")
        print("BODY:", body)
        if status == 200:
            data = json.loads(body)
            if data.get("ok") is True and data.get("module") == "reports":
                print("SMOKE_OK")
                sys.exit(0)
        last=f"bad_response: status={status}"
    except HTTPError as e:
        last=f"HTTPError {e.code}: {e}"
    except (URLError, TimeoutError) as e:
        last=f"{type(e).__name__}: {e}"
    time.sleep(1)

print("SMOKE_FAIL", last)
sys.exit(1)
PY

# 4) 运行并落盘输出（不走管道）
python3 "$EVDIR/http_probe.py" > "$EVDIR/03_http_probe.txt" 2>&1 || true

# 5) 判定
if grep -q "SMOKE_OK" "$EVDIR/03_http_probe.txt"; then
  echo "PASS" >> "$EVDIR/00_runlog.txt"
  exit 0
fi

echo "FAIL" >> "$EVDIR/00_runlog.txt"
exit 1
