#!/usr/bin/env python3
from pathlib import Path
import sys

sidebar = Path("app/templates/_sidebar.html").read_text(encoding="utf-8", errors="ignore")
layout = Path("app/templates/layout.html").read_text(encoding="utf-8", errors="ignore")

errs=[]
if 'id="btnToggleSidebar"' not in sidebar:
    errs.append("missing btnToggleSidebar in _sidebar.html")
if 'id="sidebar"' not in layout:
    errs.append("missing #sidebar wrapper in layout.html")
if "UI-SIDEBAR-TOGGLE-01" not in layout:
    errs.append("missing UI-SIDEBAR-TOGGLE-01 JS marker in layout.html")

if errs:
    print("ERROR")
    for e in errs: print("-", e)
    sys.exit(1)

print("OK: sidebar toggle wiring present")
