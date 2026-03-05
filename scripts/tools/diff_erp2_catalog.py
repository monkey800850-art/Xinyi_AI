#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ERP2 catalog diff tool.

- base: latest snapshot in docs/evidence_erp2/snapshots (erp2_catalog_*.json)
- current: app/erp2/catalog/erp2_catalog.json (or --current)
- output: docs/evidence_erp2/diff/catalog_diff_<ts>.json (or --out)

Key: (method, path)
Changed: same key but metadata changed (group/title/ui)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

TZ_UTC8 = timezone(timedelta(hours=8))

def read_json(p: str) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def list_snapshots(snapdir: str) -> List[str]:
    if not os.path.isdir(snapdir):
        return []
    files = []
    for name in os.listdir(snapdir):
        if name.startswith("erp2_catalog_") and name.endswith(".json"):
            files.append(os.path.join(snapdir, name))
    files.sort()
    return files

def extract_items(catalog: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Return mapping: (method, path) -> info
    info includes group_id, group_title, item_title, ui_type
    """
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    groups = catalog.get("groups") or []
    for g in groups:
        gid = g.get("id")
        gtitle = g.get("title")
        items = g.get("items") or []
        for it in items:
            api = it.get("api") or {}
            method = api.get("method")
            path = api.get("path")
            if not method or not path:
                continue
            k = (str(method).upper(), str(path))
            ui = it.get("ui") or {}
            out[k] = {
                "group_id": gid,
                "group_title": gtitle,
                "item_title": it.get("title"),
                "ui_type": ui.get("type"),
            }
    return out

def diff_maps(base: Dict[Tuple[str,str], Dict[str,Any]], cur: Dict[Tuple[str,str], Dict[str,Any]]):
    base_keys = set(base.keys())
    cur_keys = set(cur.keys())
    added = sorted(cur_keys - base_keys)
    removed = sorted(base_keys - cur_keys)
    common = sorted(base_keys & cur_keys)

    changed = []
    for k in common:
        if base[k] != cur[k]:
            changed.append(k)
    return added, removed, changed

def main():
    ap = argparse.ArgumentParser(description="Diff ERP2 catalog snapshots against current catalog.")
    ap.add_argument("--snapshots", default="docs/evidence_erp2/snapshots", help="Snapshots directory")
    ap.add_argument("--current", default="app/erp2/catalog/erp2_catalog.json", help="Current catalog path")
    ap.add_argument("--out", default=None, help="Output diff json path")
    args = ap.parse_args()

    snaps = list_snapshots(args.snapshots)
    base_path: Optional[str] = snaps[-1] if snaps else None
    cur_path = args.current

    cur_catalog = read_json(cur_path)
    cur_map = extract_items(cur_catalog)

    base_map: Dict[Tuple[str,str], Dict[str,Any]] = {}
    base_catalog = None
    if base_path:
        base_catalog = read_json(base_path)
        base_map = extract_items(base_catalog)

    added, removed, changed = diff_maps(base_map, cur_map)

    def pack(keys: List[Tuple[str,str]], m: Dict[Tuple[str,str], Dict[str,Any]]):
        arr = []
        for method, path in keys:
            info = m.get((method, path)) or {}
            arr.append({"method": method, "path": path, **info})
        return arr

    now = datetime.now(TZ_UTC8).strftime("%Y%m%d_%H%M%S")
    out_path = args.out or os.path.join("docs/evidence_erp2/diff", f"catalog_diff_{now}.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    payload = {
        "schema_version": "erp2-catalog-diff-0.1",
        "generated_at": datetime.now(TZ_UTC8).isoformat(),
        "base_snapshot": base_path,
        "current": cur_path,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "base_items": len(base_map),
            "current_items": len(cur_map),
        },
        "items": {
            "added": pack(added, cur_map),
            "removed": pack(removed, base_map),
            "changed": [
                {
                    "method": k[0],
                    "path": k[1],
                    "from": base_map.get(k),
                    "to": cur_map.get(k),
                }
                for k in changed
            ],
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("OK diff written:", out_path)
    print("summary:", payload["summary"])

if __name__ == "__main__":
    main()
