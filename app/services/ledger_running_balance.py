"""
REPORTS-QUERY-11: compute running balance for ledger entries.

Input: entries list (each has debit/credit/biz_date/subject_code and optional dims)
Output: entries enriched with:
- dc_direction: "debit"|"credit"
- debit_amount, credit_amount (normalized)
- running_debit, running_credit, running_direction
"""
from __future__ import annotations
from typing import Any, Dict, List

def _num(x) -> float:
    if x is None or x == "":
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def enrich_running_balance(entries: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    run_debit = 0.0
    run_credit = 0.0

    out=[]
    for e in (entries or []):
        d=_num(e.get("debit"))
        c=_num(e.get("credit"))
        dc_dir = "debit" if d>0 else ("credit" if c>0 else "")
        e2=dict(e)
        e2["dc_direction"]=dc_dir
        e2["debit_amount"]=d
        e2["credit_amount"]=c

        run_debit += d
        run_credit += c

        # net direction
        if run_debit >= run_credit:
            e2["running_debit"]=run_debit-run_credit
            e2["running_credit"]=0.0
            e2["running_direction"]="debit"
        else:
            e2["running_debit"]=0.0
            e2["running_credit"]=run_credit-run_debit
            e2["running_direction"]="credit"

        out.append(e2)
    return out
