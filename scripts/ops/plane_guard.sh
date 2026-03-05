#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import sys
print("python:", sys.executable)
try:
    import flask
    print("DEV_PLANE_OK flask_version=", getattr(flask, "__version__", "unknown"))
    raise SystemExit(0)
except Exception as e:
    print("RESTRICTED_PLANE flask_import_failed:", type(e).__name__, e)
    raise SystemExit(2)
PY
