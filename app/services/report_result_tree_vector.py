"""
REPORTS-QUERY-10: Vector tree builder for accounting columns.
Accumulates amounts dict at each node.
"""
from __future__ import annotations
from typing import Any, Dict, List
from app.services.report_accounting_amounts import calc_closing

AMT_KEYS = ["opening_debit","opening_credit","period_debit","period_credit","closing_debit","closing_credit"]

def _num(x):
    if x is None or x == "":
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def _empty_amounts():
    return {k: 0.0 for k in AMT_KEYS}

def _add_amounts(dst: Dict[str,float], src: Dict[str,Any]):
    for k in AMT_KEYS:
        dst[k] = dst.get(k,0.0) + _num(src.get(k))

def _recalc_closing(amounts: Dict[str,float]):
    c = calc_closing(
        amounts.get("opening_debit",0),
        amounts.get("opening_credit",0),
        amounts.get("period_debit",0),
        amounts.get("period_credit",0),
    )
    amounts["closing_debit"] = float(c["closing_debit"])
    amounts["closing_credit"] = float(c["closing_credit"])
    return c["direction"]

def rows_to_tree_vector(rows: List[Dict[str,Any]], group_by: List[str]) -> Dict[str,Any]:
    root: Dict[str,Any] = {}
    for r in (rows or []):
        node = root
        for g in group_by:
            key = r.get(g)
            if key not in node:
                node[key] = {"_children": {}, "_amounts": _empty_amounts(), "_direction": ""}
            _add_amounts(node[key]["_amounts"], r)
            node[key]["_direction"] = _recalc_closing(node[key]["_amounts"])
            node = node[key]["_children"]
    return root
