#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import json

TPL_DIR = Path("app/templates")

# Heuristics for legacy sidebar/toggle
LEGACY_PATTERNS = [
    re.compile(r'\b(toggle|collapse|sidebar|offcanvas)\b', re.I),
    re.compile(r'>\s*</button>'),         # lone '>' button
    re.compile(r'&gt;\s*</button>', re.I),
    re.compile(r'data-(toggle|target)=', re.I),
]

HREF_RE = re.compile(r'href\s*=\s*["\'](/[^"\']+)["\']', re.I)

def scan_file(fp: Path):
    lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
    txt = "\n".join(lines)

    extends_layout = '{% extends "layout.html" %}' in txt

    legacy_hits=[]
    for i,ln in enumerate(lines, start=1):
        if any(p.search(ln) for p in LEGACY_PATTERNS):
            legacy_hits.append((i, ln.strip()[:200]))

    hrefs=[]
    for m in HREF_RE.finditer(txt):
        hrefs.append(m.group(1))

    return {
        "file": fp.as_posix(),
        "extends_layout": extends_layout,
        "legacy_hits": legacy_hits,
        "hrefs": hrefs[:200],  # cap
    }

def main():
    files = sorted(TPL_DIR.rglob("*.html"))
    results=[scan_file(fp) for fp in files]

    old_layout = [r for r in results if not r["extends_layout"]]
    legacy = [r for r in results if r["legacy_hits"]]

    # collect entry links from legacy templates first, then old_layout
    entry_links=[]
    for r in legacy + old_layout:
        for h in r["hrefs"]:
            if h not in entry_links:
                entry_links.append(h)
    entry_links = entry_links[:50]

    out = {
        "templates_total": len(results),
        "old_layout_count": len(old_layout),
        "legacy_toggle_count": len(legacy),
        "old_layout_templates": [r["file"] for r in old_layout],
        "legacy_toggle_templates": [{"file": r["file"], "hits": r["legacy_hits"][:20]} for r in legacy],
        "entry_links_top50": entry_links,
    }

    Path("evidence/UI-STATIC-TRACE-01/trace.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    md=[]
    md.append("# UI static trace report (old UI sources)")
    md.append("")
    md.append(f"- templates_total: {out['templates_total']}")
    md.append(f"- old_layout_count (not extends layout.html): {out['old_layout_count']}")
    md.append(f"- legacy_toggle_count (has legacy toggle patterns): {out['legacy_toggle_count']}")
    md.append("")
    md.append("## OLD_LAYOUT_TEMPLATES")
    for f in out["old_layout_templates"]:
        md.append(f"- {f}")
    md.append("")
    md.append("## LEGACY_TOGGLE_TEMPLATES (with line samples)")
    for item in out["legacy_toggle_templates"]:
        md.append(f"- {item['file']}")
        for (ln, sample) in item["hits"]:
            md.append(f"  - L{ln}: {sample}")
    md.append("")
    md.append("## ENTRY_LINKS (top 50 unique hrefs from legacy/old templates)")
    for h in out["entry_links_top50"]:
        md.append(f"- {h}")
    md.append("")

    Path("docs/ui/static_trace_old_ui.md").write_text("\n".join(md), encoding="utf-8")

    print("old_layout_count=", out["old_layout_count"])
    print("legacy_toggle_count=", out["legacy_toggle_count"])
    print("wrote docs/ui/static_trace_old_ui.md")

if __name__ == "__main__":
    main()
