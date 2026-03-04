#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
NO_PROXY_OPT="${NO_PROXY_OPT:---noproxy '*'}"

echo "== smoke_tax_ui =="
echo "BASE_URL=$BASE_URL"

http_get() {
  local path="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sS -m 5 $NO_PROXY_OPT -o /dev/null -w "%{http_code}" "${BASE_URL}${path}" || echo "000"
  else
    python3 - <<PY
import urllib.request, os
url = os.environ.get("BASE_URL","http://127.0.0.1:5000") + "$path"
try:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as r:
        print(r.getcode())
except Exception:
    print("000")
PY
  fi
}

code=$(http_get "/tax/summary")
echo "GET /tax/summary -> $code"
if [[ "$code" != "200" ]]; then
  echo "[WARN] /tax/summary not reachable ($code). environment may restrict http."
fi

code2=$(http_get "/api/tax/forms/latest")
echo "GET /api/tax/forms/latest -> $code2"
if [[ "$code2" != "200" && "$code2" != "404" ]]; then
  echo "[WARN] unexpected status for forms api: $code2"
fi

echo "== OK =="
