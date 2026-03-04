#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PYFILES = [
    p for p in ROOT.rglob("*.py")
    if "/.git/" not in p.as_posix()
    and "/.venv" not in p.as_posix()
    and "/.venv_nopip" not in p.as_posix()
    and "/site-packages" not in p.as_posix()
    and "/node_modules" not in p.as_posix()
]

ROUTE_RE = re.compile(r'@(?P<obj>[a-zA-Z0-9_\.]+)\.route\(\s*(?P<q>["\'])(?P<path>/[^"\']*|)\2', re.M)
RENDER_RE = re.compile(r'render_template\(\s*(?P<q>["\'])(?P<tpl>[^"\']+\.html)\1', re.M)
REDIR_RE  = re.compile(r'redirect\(\s*(?P<q>["\'])(?P<to>/[^"\']+)\1', re.M)

def scan_file(fp: Path):
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    hits=[]
    for m in ROUTE_RE.finditer(txt):
        path = m.group("path")
        # root candidates: "/" or "" (blueprint mount) or explicit methods
        if path not in ("/", ""):
            continue
        win = txt[m.start(): m.start()+3000]
        rt = RENDER_RE.search(win)
        rd = REDIR_RE.search(win)
        tpl = rt.group("tpl") if rt else None
        to  = rd.group("to") if rd else None
        line = txt[:m.start()].count("\n") + 1
        hits.append({
            "path": path,
            "decorator_obj": m.group("obj"),
            "file": fp.as_posix().replace(str(ROOT)+"/",""),
            "line": line,
            "template": tpl,
            "redirect_to": to,
        })
    return hits

def main():
    all_hits=[]
    for fp in PYFILES:
        all_hits.extend(scan_file(fp))

    # Also grep-like: find redirect("/hub") etc in any file
    print("home_route_candidates=", len(all_hits))
    for h in all_hits:
        print(f'{h["path"] or "(empty)"} -> tpl={h["template"]} redir={h["redirect_to"]} @ {h["file"]}:{h["line"]} ({h["decorator_obj"]})')

    out = Path("evidence/UI-ROUTE-MAP-02/home_candidates.txt")
    out.write_text("\n".join(
        [f'{h["path"] or "(empty)"} -> tpl={h["template"]} redir={h["redirect_to"]} @ {h["file"]}:{h["line"]} ({h["decorator_obj"]})'
         for h in all_hits]
    ) + ("\n" if all_hits else ""), encoding="utf-8")

    # naive pick: first hit with template, else first hit with redirect
    pick_tpl = next((h["template"] for h in all_hits if h["template"]), None)
    pick_redir = next((h["redirect_to"] for h in all_hits if h["redirect_to"]), None)

    plan = []
    plan.append("# Home route patch plan (auto-generated)")
    plan.append("")
    plan.append(f"- candidates: {len(all_hits)}")
    plan.append(f"- chosen_template: {pick_tpl}")
    plan.append(f"- chosen_redirect_to: {pick_redir}")
    plan.append("")
    if pick_tpl:
        plan.append("## Proposed action")
        plan.append(f"- Migrate template `{pick_tpl}` to extend `layout.html`.")
    elif pick_redir:
        plan.append("## Proposed action")
        plan.append(f"- Home route already redirects to `{pick_redir}`. Consider serving new home UI via that page, or add a dedicated home template that extends layout.")
    else:
        plan.append("## Proposed action")
        plan.append("- Could not detect template/redirect statically. Need runtime introspection (Flask url_map) or search for index template usage.")
    Path("docs/ui/home_patch_plan.md").write_text("\n".join(plan)+"\n", encoding="utf-8")

    # Output chosen template for bash consumption
    print("CHOSEN_TEMPLATE=", pick_tpl or "")
    print("CHOSEN_REDIRECT=", pick_redir or "")

if __name__ == "__main__":
    main()
