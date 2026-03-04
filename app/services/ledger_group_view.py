"""
REPORTS-QUERY-12: Build grouped ledger view with per-group subtotal.

Input rows: enriched ledger rows (from enrich_running_balance), each row includes:
- biz_date, subject_code, note (optional)
- dc_direction, debit_amount, credit_amount
- running_direction, running_debit, running_credit
- aux_* dims optional

We group by a composite key: ["subject_code"] + selected dims (if present).
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple

def _num(x) -> float:
    if x is None or x == "":
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def _key(row: Dict[str,Any], group_cols: List[str]) -> Tuple[Any,...]:
    return tuple(row.get(c) for c in group_cols)

def build_grouped_ledger(rows: List[Dict[str,Any]], group_cols: List[str]) -> List[Dict[str,Any]]:
    if not group_cols:
        group_cols = ["subject_code"]

    groups: Dict[Tuple[Any,...], Dict[str,Any]] = {}

    for r in (rows or []):
        k = _key(r, group_cols)
        g = groups.get(k)
        if g is None:
            g = {
                "key": {group_cols[i]: k[i] for i in range(len(group_cols))},
                "opening": {"direction":"", "amount": 0.0},  # scaffold for future carry-forward
                "lines": [],
                "subtotal": {
                    "period_debit": 0.0,
                    "period_credit": 0.0,
                    "closing_direction": "",
                    "closing_amount": 0.0,
                }
            }
            groups[k] = g

        g["lines"].append(r)
        g["subtotal"]["period_debit"] += _num(r.get("debit_amount"))
        g["subtotal"]["period_credit"] += _num(r.get("credit_amount"))

    # finalize closing from last line in each group (running_* fields)
    out=[]
    for k, g in groups.items():
        if g["lines"]:
            last = g["lines"][-1]
            g["subtotal"]["closing_direction"] = last.get("running_direction") or ""
            if (last.get("running_direction") == "debit"):
                g["subtotal"]["closing_amount"] = _num(last.get("running_debit"))
            elif (last.get("running_direction") == "credit"):
                g["subtotal"]["closing_amount"] = _num(last.get("running_credit"))
            else:
                g["subtotal"]["closing_amount"] = 0.0
        out.append(g)

    # stable sort by composite key stringified
    def sk(g):
        return tuple("" if g["key"].get(c) is None else str(g["key"].get(c)) for c in group_cols)
    out.sort(key=sk)
    return out
