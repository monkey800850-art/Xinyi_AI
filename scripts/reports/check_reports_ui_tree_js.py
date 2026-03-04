import sys
from pathlib import Path

tb = Path("app/templates/reports_trial_balance.html").read_text(encoding="utf-8", errors="ignore")
ld = Path("app/templates/reports_ledger.html").read_text(encoding="utf-8", errors="ignore")

def must(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)

must("REPORTS-QUERY-06" in tb, "trial_balance html missing REPORTS-QUERY-06 marker")
must("REPORTS-QUERY-06" in ld, "ledger html missing REPORTS-QUERY-06 marker")
must("loadCollapsedSet" in tb and "saveCollapsedSet" in tb, "missing collapse persistence functions in TB")
must("data-kind='node'" in tb or "data-kind=\"node\"" in tb, "TB should render node rows clickable")
print("PASS ui tree js static checks")
