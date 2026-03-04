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


# --- REPORTS-QUERY-13 HOTFIX BEGIN ---
def _rq13_group_key(row: dict):
    """Best-effort group key extractor for grouping rows."""
    for k in ("group_key", "group_id", "group", "groupBy", "groupby", "gk"):
        if k in row and row.get(k) not in (None, ""):
            return row.get(k)
    # some pipelines may embed grouping info
    for k in ("_group_key", "__group_key__", "__gkey__"):
        if k in row and row.get(k) not in (None, ""):
            return row.get(k)
    return None

def _rq13_is_group_first_row(row: dict, prev_group_key):
    """Return True iff this row should receive opening injection (group-first only)."""
    # Prefer explicit markers if present
    if row.get("is_group_first") is True:
        return True
    if row.get("is_group_header") is True:
        return True
    rt = row.get("row_type") or row.get("type")
    if isinstance(rt, str) and rt.lower() in ("group_header", "group_first", "group-start", "groupstart", "header"):
        return True

    # Otherwise: use group key transition
    gk = _rq13_group_key(row)
    if gk is None:
        return None  # unknown
    return (prev_group_key is None) or (gk != prev_group_key)
# --- REPORTS-QUERY-13 HOTFIX END ---
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


def enrich_running_balance_grouped(entries: List[Dict[str,Any]], group_cols: List[str], opening_by_group: dict | None = None) -> List[Dict[str,Any]]:
    """
    Compute running balance per group (composite key by group_cols).
    Keeps original order of entries within each group as they appear in input.
    """
    if not group_cols:
        group_cols = ["subject_code"]

    # Maintain per-group accumulators
    acc = {}  # key -> (run_debit, run_credit)

    out=[]
    for e in (entries or []):
        k = tuple(e.get(c) for c in group_cols)
        run = acc.get(k, (0.0, 0.0))

        # apply opening (infer) if provided
        if opening_by_group and k in opening_by_group:
            od = float(opening_by_group[k].get('debit', 0.0) or 0.0)
            oc = float(opening_by_group[k].get('credit', 0.0) or 0.0)
            run_debit, run_credit = od, oc
        
        run_debit, run_credit = run

        d=_num(e.get("debit"))
        c=_num(e.get("credit"))

        dc_dir = "debit" if d>0 else ("credit" if c>0 else "")
        e2=dict(e)
        e2["dc_direction"]=dc_dir
        e2["debit_amount"]=d
        e2["credit_amount"]=c

        run_debit += d
        run_credit += c

        if run_debit >= run_credit:
            e2["running_debit"]=run_debit-run_credit
            e2["running_credit"]=0.0
            e2["running_direction"]="debit"
        else:
            e2["running_debit"]=0.0
            e2["running_credit"]=run_credit-run_debit
            e2["running_direction"]="credit"

        acc[k] = (run_debit, run_credit)
        out.append(e2)

    return out
