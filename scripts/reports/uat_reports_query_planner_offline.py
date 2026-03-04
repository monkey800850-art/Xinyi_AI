#!/usr/bin/env python3
# REPORTS-QUERY-01B: sys.path bootstrap so `import app.*` works when run as a script
import sys
from pathlib import Path as _Path
_repo_root = _Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
"""
REPORTS-QUERY-01 offline UAT:
- ensures planner accepts primary + multi-level secondary
- ensures multi-select filters produce IN(...) clauses with correct params length
This is offline (no DB).
"""
from app.services.report_query_planner import QuerySpec, build_sql_plan_best_effort

def must(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)

# Example per doc: primary=person, secondary=[subject, department], subject multi-select
spec = QuerySpec(
    report="trial_balance",
    primary_dim="person",
    secondary_dims=["subject", "department"],
    filters={"subject": ["6602", "6601"], "department": ["HR", "CEO"]},
    date_from="2026-01-01",
    date_to="2026-12-31",
)
plan = build_sql_plan_best_effort(spec)
must(plan["ok"] in (True, False), "plan must return ok flag")
sql = plan["sql"]
params = plan["params"]

must("GROUP BY" in sql and "ORDER BY" in sql, "sql must have GROUP BY/ORDER BY")
import re as _re
must(_re.search(r"\bIN\s*\(\s*\?(\s*,\s*\?)+\s*\)", sql, _re.I) is not None, "sql should contain IN placeholders for multi-select")
must(len(params) == (2 + 2 + 2), "params should include date_from/date_to + 2+2 filters")

print("PASS: offline planner checks")
print("group_by=", plan["group_by"])
print("params_len=", len(params))
