"""
REPORTS-QUERY-05
Flatten tree into render-ready lines with subtotals.

Tree format (from report_result_tree.rows_to_tree):
node = {
  key1: {"_children": {...}, "_value": 123},
  key2: {"_children": {...}, "_value": 456},
}

Output lines:
[
  {"level":0,"label":"A","value":150,"kind":"node","path":["A"]},
  {"level":1,"label":"6601","value":100,"kind":"node","path":["A","6601"]},
  {"level":2,"label":"HR","value":100,"kind":"leaf","path":["A","6601","HR"]},
  {"level":1,"label":"小计(6601)","value":100,"kind":"subtotal","path":["A","6601"]},
  {"level":0,"label":"小计(A)","value":150,"kind":"subtotal","path":["A"]},
]
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

def tree_to_lines(tree: Dict[str, Any], level: int = 0, path: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    path = path or []
    lines: List[Dict[str, Any]] = []

    # Stable order: stringified key
    for k in sorted(tree.keys(), key=lambda x: str(x)):
        node = tree[k]
        npath = path + [str(k)]
        children = node.get("_children") or {}
        value = node.get("_value", 0)

        kind = "leaf" if not children else "node"
        lines.append({"level": level, "label": str(k), "value": value, "kind": kind, "path": npath})

        if children:
            lines.extend(tree_to_lines(children, level + 1, npath))
            # subtotal for this node after children
            lines.append({"level": level, "label": f"小计({k})", "value": value, "kind": "subtotal", "path": npath})

    return lines

def overall_total(lines: List[Dict[str, Any]]) -> float:
    # top-level subtotals sum (avoid double-counting by taking max level==0 node values)
    tops = [l["value"] for l in lines if l.get("level")==0 and l.get("kind") in ("node","leaf")]
    return sum(tops) if tops else 0
