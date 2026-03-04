import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000/hub"

req = urllib.request.Request(url, headers={"User-Agent": "XinyiAI-Probe/1.0"})
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        code = resp.status
        body = resp.read(20000).decode("utf-8", errors="replace")
except Exception as e:
    print("ERROR:", repr(e))
    sys.exit(1)

print("STATUS", code)
print(body)
