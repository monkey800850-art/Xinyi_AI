#!/usr/bin/env python3
# REPORTS-QUERY-03: offline runner UAT (no DB required)
import sys
from pathlib import Path as _Path
_repo_root = _Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.services.report_query_planner import QuerySpec, build_sql_plan_best_effort
from app.services.report_query_runner import run_plan

def must(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)

spec = QuerySpec(
    report="trial_balance",
    primary_dim="person",
    secondary_dims=["subject","department"],
    filters={"subject":["6601","6602"],"department":["HR"]},
)
plan = build_sql_plan_best_effort(spec)
res = run_plan(plan)

# In current restricted env, we accept non-ok, but must be safe (no exception) and structured.
must(hasattr(res, "warnings"), "result must have warnings")
must(isinstance(res.rows, list), "rows must be a list")
print("PASS: runner offline safety")
print("engine=", res.engine)
print("ok=", res.ok)
print("rows_len=", len(res.rows))
print("warnings_head=", (res.warnings or [])[:3])
