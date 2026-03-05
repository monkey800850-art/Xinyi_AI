#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import runpy
import sys
from pathlib import Path

# ensure repo root is on sys.path (when executed as a file script)
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
APP_PY = REPO_ROOT / "app.py"
from pathlib import Path

def load_flask_app():
    ns = runpy.run_path(str(APP_PY))
    # preferred: create_app factory
    if "create_app" in ns and callable(ns["create_app"]):
        return ns["create_app"](), "runpy(app.py):create_app()"
    # fallback: global app (some projects keep it)
    if "app" in ns:
        return ns["app"], "runpy(app.py):app"
    raise RuntimeError("cannot find create_app() or app in app.py namespace")

def main():
    app, ref = load_flask_app()
    out_routes = Path("docs/evidence/testclient_routes_all.txt")
    out_tax = Path("docs/evidence/testclient_routes_tax.txt")
    out_pages = Path("docs/evidence/testclient_tax_pages.txt")

    # routes
    routes = []
    for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        methods = ",".join(sorted(mm for mm in r.methods if mm not in ("HEAD","OPTIONS")))
        routes.append(f"{methods:10s} {r.rule:45s} -> {r.endpoint}")
    out_routes.write_text("flask_app_ref=" + ref + "\n" + "\n".join(routes) + "\n", encoding="utf-8")

    tax_lines = [ln for ln in routes if ("/tax" in ln or "tax_" in ln or "/m/" in ln or "/hub" in ln)]
    out_tax.write_text("flask_app_ref=" + ref + "\n" + "\n".join(tax_lines) + "\n", encoding="utf-8")

    # pages to probe
    candidates = [
        "/", "/hub",
        "/tax", "/tax/summary",
        "/m/tax", "/m/tax_summary", "/m/tax-summary", "/m/tax-summary.html",
        "/m/modules/tax", "/m/tax.html", "/m/tax_summary.html",
        "/api/tax/forms/latest",
    ]

    c = app.test_client()
    lines = [f"flask_app_ref={ref}"]
    for p in candidates:
        try:
            resp = c.get(p)
            status = resp.status_code
            ct = resp.headers.get("Content-Type", "")
            body = resp.get_data(as_text=True, errors="ignore")
            snippet = body[:200].replace("\n", "\\n")
            lines.append(f"GET {p:28s} -> {status} ct={ct} body[0:200]={snippet}")
        except Exception as e:
            lines.append(f"GET {p:28s} -> EXC {e}")
    out_pages.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[OK] wrote:", out_routes)
    print("[OK] wrote:", out_tax)
    print("[OK] wrote:", out_pages)

if __name__ == "__main__":
    main()
