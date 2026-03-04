"""
REPORTS-QUERY-08: Ledger Engine (DB-agnostic)

Compute trial-balance accounting structure from voucher-entry-like rows.

Entry fields (best-effort):
- biz_date: "YYYY-MM-DD" (optional)
- subject_code: str
- debit: number
- credit: number
- aux_* fields optional

Output per group:
- opening_debit/opening_credit
- period_debit/period_credit
- closing_debit/closing_credit
- direction ("debit"|"credit")
- group_by columns preserved
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from app.services.report_accounting_amounts import calc_closing

def _num(x) -> float:
    if x is None or x == "":
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def _key_for(entry: Dict[str, Any], group_by: List[str]) -> Tuple[Any, ...]:
    return tuple(entry.get(k) for k in group_by)

def _row_from_key(key: Tuple[Any, ...], group_by: List[str]) -> Dict[str, Any]:
    d = {}
    for i, k in enumerate(group_by):
        d[k] = key[i]
    d.update({
        "opening_debit": 0.0,
        "opening_credit": 0.0,
        "period_debit": 0.0,
        "period_credit": 0.0,
        "closing_debit": 0.0,
        "closing_credit": 0.0,
        "direction": "",
    })
    return d

def compute_trial_balance_from_entries(
    entries: List[Dict[str, Any]],
    group_by: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    opening_mode: str = "none",  # "none" | "infer"
) -> List[Dict[str, Any]]:
    if not group_by:
        group_by = ["subject_code"]

    acc: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

    for e in (entries or []):
        biz_date = e.get("biz_date")
        k = _key_for(e, group_by)
        row = acc.get(k)
        if row is None:
            row = _row_from_key(k, group_by)
            acc[k] = row

        debit = _num(e.get("debit"))
        credit = _num(e.get("credit"))

        in_period = True
        if date_from and biz_date and biz_date < date_from:
            in_period = False
        if date_to and biz_date and biz_date > date_to:
            in_period = False

        if in_period:
            row["period_debit"] += debit
            row["period_credit"] += credit
        else:
            if opening_mode == "infer" and date_from and biz_date and biz_date < date_from:
                row["opening_debit"] += debit
                row["opening_credit"] += credit

    out = []
    for _, row in acc.items():
        closing = calc_closing(
            row["opening_debit"],
            row["opening_credit"],
            row["period_debit"],
            row["period_credit"],
        )
        row["closing_debit"] = closing["closing_debit"]
        row["closing_credit"] = closing["closing_credit"]
        row["direction"] = closing["direction"]
        out.append(row)

    def sk(r):
        return tuple("" if r.get(c) is None else str(r.get(c)) for c in group_by)
    out.sort(key=sk)
    return out
