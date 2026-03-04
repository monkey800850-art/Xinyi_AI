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


try:

    subtotal = _rq13_recalc_subtotal_closing(subtotal)

except Exception:

    pass

# --- REPORTS-QUERY-13 HOTFIX BEGIN ---
def _rq13_recalc_subtotal_closing(subtotal: dict):
    """Best-effort: enforce closing = opening + period for grouped subtotal."""
    if not isinstance(subtotal, dict):
        return subtotal
    # locate opening
    opening = None
    for k in ("opening_amount", "opening", "opening_balance"):
        if k in subtotal and subtotal.get(k) is not None:
            opening = float(subtotal.get(k) or 0.0)
            break
    if opening is None:
        return subtotal

    # locate period (本期)
    period = None
    for k in ("period_amount", "period", "period_delta", "net_amount", "current_amount", "this_period_amount"):
        if k in subtotal and subtotal.get(k) is not None:
            period = float(subtotal.get(k) or 0.0)
            break

    # fallback: debit-credit if present
    if period is None and ("debit_amount" in subtotal or "credit_amount" in subtotal):
        debit = float(subtotal.get("debit_amount") or 0.0)
        credit = float(subtotal.get("credit_amount") or 0.0)
        # assume net = debit - credit (common convention; if opposite in your engine, adjust upstream)
        period = debit - credit

    if period is None:
        return subtotal

    subtotal["closing_amount"] = opening + period
    return subtotal
# --- REPORTS-QUERY-13 HOTFIX END ---
def _num(x) -> float:
    if x is None or x == "":
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def _key(row: Dict[str,Any], group_cols: List[str]) -> Tuple[Any,...]:
    return tuple(row.get(c) for c in group_cols)

def build_grouped_ledger(rows: List[Dict[str,Any]], group_cols: List[str], opening_by_group: dict | None = None) -> List[Dict[str,Any]]:
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
            if opening_by_group and k in opening_by_group:
                g["opening"] = {
                    "direction": opening_by_group[k].get("direction",""),
                    "amount": float(opening_by_group[k].get("amount") or 0.0)
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
