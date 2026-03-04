#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import importlib
from pathlib import Path

def try_import(modname: str):
    try:
        return importlib.import_module(modname), None
    except Exception as e:
        return None, e

def find_flask_app(mod):
    from flask import Flask

    # common names first
    for name in ("app", "application", "flask_app"):
        obj = getattr(mod, name, None)
        if isinstance(obj, Flask):
            return obj, f"{mod.__name__}.{name}"

    # scan all globals
    for name, obj in vars(mod).items():
        if isinstance(obj, Flask):
            return obj, f"{mod.__name__}.{name}"

    # factory pattern
    create = getattr(mod, "create_app", None)
    if callable(create):
        a = create()
        if isinstance(a, Flask):
            return a, f"{mod.__name__}.create_app()"

    raise RuntimeError("no Flask() instance or create_app() found")

def main():
    # candidates: prefer explicit files that usually exist in repos
    candidates = [
        "app", "main", "run", "server", "wsgi",
        "app.main", "app.server", "app.wsgi",
    ]

    report_lines = []
    picked = None

    for m in candidates:
        mod, err = try_import(m)
        if err is not None:
            report_lines.append(f"[MISS] import {m}: {err}")
            continue
        try:
            flask_app, ref = find_flask_app(mod)
            routes = []
            for r in sorted(flask_app.url_map.iter_rules(), key=lambda x: str(x)):
                methods = ",".join(sorted(mm for mm in r.methods if mm not in ("HEAD","OPTIONS")))
                routes.append(f"{methods:10s} {r.rule:45s} -> {r.endpoint}")
            picked = (ref, routes)
            report_lines.append(f"[HIT] {m} -> flask_app_ref={ref} routes={len(routes)}")
            break
        except Exception as e:
            report_lines.append(f"[MISS] {m}: imported but cannot detect flask app: {e}")
            continue

    out = Path("docs/evidence/routes_snapshot.txt")
    if picked is None:
        out.write_text("[FAIL] cannot import/detect flask app\n" + "\n".join(report_lines) + "\n", encoding="utf-8")
        print("[FAIL] wrote", out)
        return

    ref, routes = picked
    out.write_text("flask_app_ref=" + ref + "\n" + "\n".join(routes) + "\n\n" + "\n".join(report_lines) + "\n", encoding="utf-8")
    print("[OK] wrote", out)

if __name__ == "__main__":
    main()
