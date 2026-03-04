"""
REPORTS-QUERY-10: Flatten vector tree into lines with subtotal rows.
Each line carries amounts dict for rendering multiple columns.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

def tree_to_lines_vector(tree: Dict[str,Any], level: int = 0, path: Optional[List[str]] = None) -> List[Dict[str,Any]]:
    path = path or []
    lines: List[Dict[str,Any]] = []
    for k in sorted(tree.keys(), key=lambda x: str(x)):
        node = tree[k]
        npath = path + [str(k)]
        children = node.get("_children") or {}
        amounts = node.get("_amounts") or {}
        direction = node.get("_direction") or ""
        kind = "leaf" if not children else "node"

        lines.append({
            "level": level,
            "label": str(k),
            "kind": kind,
            "path": npath,
            "direction": direction,
            "amounts": amounts,
        })

        if children:
            lines.extend(tree_to_lines_vector(children, level+1, npath))
            lines.append({
                "level": level,
                "label": f"小计({k})",
                "kind": "subtotal",
                "path": npath,
                "direction": direction,
                "amounts": amounts,
            })
    return lines

def overall_total_vector(lines: List[Dict[str,Any]]) -> Dict[str,Any]:
    # Sum top-level node amounts without double-counting.
    total = {"opening_debit":0.0,"opening_credit":0.0,"period_debit":0.0,"period_credit":0.0,"closing_debit":0.0,"closing_credit":0.0}
    tops = [l for l in lines if l.get("level")==0 and l.get("kind") in ("node","leaf")]
    for l in tops:
        a = l.get("amounts") or {}
        for k in total.keys():
            total[k] += float(a.get(k,0.0) or 0.0)
    return total
