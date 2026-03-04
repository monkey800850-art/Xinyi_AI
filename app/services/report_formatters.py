"""
REPORTS-QUERY-06: numeric formatting helpers.
Keep minimal + deterministic (no locale dependency).
"""
from __future__ import annotations

def fmt_amount(v, decimals: int = 2) -> str:
    if v is None:
        return ""
    try:
        x = float(v)
    except Exception:
        return str(v)
    # format with thousands separator
    s = f"{x:,.{decimals}f}"
    return s
