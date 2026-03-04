"""
REPORTS-QUERY-01: Multi-dimension query planner for Trial Balance and Ledger.

Design constraints:
- Do not hardcode aux dimension categories; allow configurable dimension registry.
- Support: one primary dimension + 0..N secondary dimensions (ordered).
- Secondary dimensions may be multi-select; subjects may be multi-select.
- Provide:
  - validate_query_spec()
  - build_grouping_plan()
  - build_sql_plan_best_effort(): returns {sql, params, columns, warnings}
This file is intentionally DB-agnostic; SQL generation is "best effort" and can be adapted.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Registry: logical dimension -> (table alias, column expression)
# NOTE: adapt to your actual schema. This planner only standardizes the interface.
DEFAULT_DIM_REGISTRY: Dict[str, Dict[str, str]] = {
    # accounting core
    "subject": {"expr": "subject_code", "label": "科目"},
    # aux dimensions (examples; do not assume all exist in DB)
    "person": {"expr": "aux_person_id", "label": "个人"},
    "project": {"expr": "aux_project_id", "label": "项目"},
    "department": {"expr": "aux_department_id", "label": "部门"},
    "bank_account": {"expr": "aux_bank_account_id", "label": "银行账户"},
}

@dataclass
class QuerySpec:
    report: str  # "trial_balance" | "ledger"
    primary_dim: str
    secondary_dims: List[str]
    # filter dict: dim -> list of allowed values (multi-select)
    filters: Dict[str, List[Any]]
    # generic period filters
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    # for ledger (optional)
    include_opening: bool = False

def validate_query_spec(spec: QuerySpec, dim_registry: Dict[str, Dict[str, str]] = DEFAULT_DIM_REGISTRY) -> Tuple[bool, List[str]]:
    warns: List[str] = []
    if spec.primary_dim not in dim_registry:
        warns.append(f"unknown primary_dim={spec.primary_dim}")
    for d in spec.secondary_dims:
        if d not in dim_registry:
            warns.append(f"unknown secondary_dim={d}")
    # primary cannot repeat in secondary
    if spec.primary_dim in spec.secondary_dims:
        warns.append("primary_dim must not appear in secondary_dims")
    # de-dup while preserving order
    seen=set()
    dedup=[]
    for d in spec.secondary_dims:
        if d not in seen:
            seen.add(d)
            dedup.append(d)
    if dedup != spec.secondary_dims:
        warns.append("secondary_dims deduplicated")
        spec.secondary_dims = dedup
    return (len([w for w in warns if w.startswith("unknown")]) == 0, warns)

def build_grouping_plan(spec: QuerySpec, dim_registry: Dict[str, Dict[str, str]] = DEFAULT_DIM_REGISTRY) -> Dict[str, Any]:
    ok, warns = validate_query_spec(spec, dim_registry)
    dims = [spec.primary_dim] + list(spec.secondary_dims)
    cols = []
    for d in dims:
        meta = dim_registry.get(d, {"expr": d, "label": d})
        cols.append({"dim": d, "expr": meta["expr"], "label": meta.get("label", d)})
    return {"ok": ok, "warnings": warns, "dims": dims, "columns": cols}

def build_sql_plan_best_effort(spec: QuerySpec, dim_registry: Dict[str, Dict[str, str]] = DEFAULT_DIM_REGISTRY) -> Dict[str, Any]:
    """
    Best-effort SQL plan. Caller should adapt base_table / joins to real schema.
    We only:
    - choose group-by columns per plan
    - generate WHERE filters for multi-select (IN (...))
    """
    plan = build_grouping_plan(spec, dim_registry)
    cols = plan["columns"]
    group_exprs = [c["expr"] for c in cols]
    params: List[Any] = []
    where = ["1=1"]
    # date filters (if schema supports)
    if spec.date_from:
        where.append("biz_date >= ?")
        params.append(spec.date_from)
    if spec.date_to:
        where.append("biz_date <= ?")
        params.append(spec.date_to)

    for dim, values in (spec.filters or {}).items():
        if not values:
            continue
        meta = dim_registry.get(dim)
        expr = (meta["expr"] if meta else dim)
        placeholders = ",".join(["?"] * len(values))
        where.append(f"{expr} IN ({placeholders})")
        params.extend(values)

    # base table differs by report type; keep generic
    base_table = "voucher_entries" if spec.report == "ledger" else "balances"

    sql = f"""
SELECT
  {", ".join(group_exprs)},
  
SUM(debit) AS period_debit,
SUM(credit) AS period_credit

FROM {base_table}
WHERE {" AND ".join(where)}
GROUP BY {", ".join(group_exprs)}
ORDER BY {", ".join(group_exprs)}
""".strip()

    return {
        "ok": plan["ok"],
        "warnings": plan["warnings"],
        "sql": sql,
        "params": params,
        "group_by": group_exprs,
        "columns": cols,
        "base_table": base_table,
    }
