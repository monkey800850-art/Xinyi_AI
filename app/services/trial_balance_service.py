from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine
from app.services.subject_category_service import resolve_subject_category


class TrialBalanceError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise TrialBalanceError("invalid_date") from err


def _sum_children(nodes_by_code: Dict[str, Dict[str, object]], order: List[str]):
    # Post-order aggregation by level descending
    for code in sorted(order, key=lambda c: nodes_by_code[c]["level"], reverse=True):
        node = nodes_by_code[code]
        parent_code = node.get("parent_code")
        if parent_code and parent_code in nodes_by_code:
            parent = nodes_by_code[parent_code]
            parent["period_debit"] += node["period_debit"]
            parent["period_credit"] += node["period_credit"]
            parent["opening_balance"] += node["opening_balance"]
            parent["ending_balance"] += node["ending_balance"]


def _find_parent_by_prefix(code: str, existing_codes: set) -> str:
    c = (code or "").strip()
    if len(c) <= 4:
        return ""
    for cut in range(len(c) - 2, 3, -2):
        p = c[:cut]
        if p in existing_codes:
            return p
    return ""


def get_trial_balance(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()

    if not book_id_raw or not start_raw or not end_raw:
        raise TrialBalanceError("book_id/start_date/end_date required")

    try:
        book_id = int(book_id_raw)
    except Exception as err:
        raise TrialBalanceError("book_id must be integer") from err

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    engine = get_engine()
    with engine.connect() as conn:
        subjects = conn.execute(
            text(
                """
                SELECT id, code, name, category, level, parent_code, balance_direction
                FROM subjects
                WHERE book_id=:book_id
                ORDER BY code ASC
                """
            ),
            {"book_id": book_id},
        ).fetchall()

        sums = conn.execute(
            text(
                """
                SELECT vl.subject_code AS code,
                       SUM(vl.debit) AS debit_sum,
                       SUM(vl.credit) AS credit_sum
                FROM voucher_lines vl
                JOIN vouchers v ON v.id = vl.voucher_id
                WHERE v.book_id = :book_id
                  AND v.voucher_date BETWEEN :start_date AND :end_date
                  AND v.status = 'posted'
                GROUP BY vl.subject_code
                """
            ),
            {"book_id": book_id, "start_date": start_date, "end_date": end_date},
        ).fetchall()

    sum_map = {
        row.code: {
            "debit": Decimal(str(row.debit_sum or 0)),
            "credit": Decimal(str(row.credit_sum or 0)),
        }
        for row in sums
    }

    nodes_by_code: Dict[str, Dict[str, object]] = {}
    order: List[str] = []
    existing_codes = {s.code for s in subjects}

    for s in subjects:
        parent_code = (s.parent_code or "").strip()
        if not parent_code:
            parent_code = _find_parent_by_prefix(s.code, existing_codes)
        sums_for = sum_map.get(s.code, {"debit": Decimal("0"), "credit": Decimal("0")})
        opening = Decimal("0")
        if (s.balance_direction or "").upper() == "CREDIT":
            ending = opening + sums_for["credit"] - sums_for["debit"]
        else:
            ending = opening + sums_for["debit"] - sums_for["credit"]

        node = {
            "code": s.code,
            "name": s.name,
            "category": s.category or "",
            "level": s.level,
            "parent_code": parent_code or None,
            "opening_balance": opening,
            "raw_period_debit": sums_for["debit"],
            "raw_period_credit": sums_for["credit"],
            "raw_ending_balance": ending,
            "period_debit": sums_for["debit"],
            "period_credit": sums_for["credit"],
            "ending_balance": ending,
        }
        category_resolved = resolve_subject_category(s.code, s.category or "")
        node["category_code"] = category_resolved["category_code"]
        node["category_name"] = category_resolved["category_name"]
        node["category_source"] = category_resolved["category_source"]
        nodes_by_code[s.code] = node
        order.append(s.code)

    _sum_children(nodes_by_code, order)

    items = []
    category_summary: Dict[str, Dict[str, Decimal]] = {}
    for code in order:
        node = nodes_by_code[code]
        cat_code = node.get("category_code") or "UNKNOWN"
        cat_name = node.get("category_name") or "未分类"
        cat_key = f"{cat_code}|{cat_name}"
        if cat_key not in category_summary:
            category_summary[cat_key] = {
                "category_code": cat_code,
                "category_name": cat_name,
                "period_debit": Decimal("0"),
                "period_credit": Decimal("0"),
                "ending_balance": Decimal("0"),
            }
        category_summary[cat_key]["period_debit"] += node["raw_period_debit"]
        category_summary[cat_key]["period_credit"] += node["raw_period_credit"]
        category_summary[cat_key]["ending_balance"] += node["raw_ending_balance"]
        items.append(
            {
                "code": node["code"],
                "name": node["name"],
                "category": node["category_name"],
                "category_code": node["category_code"],
                "category_name": node["category_name"],
                "category_source": node["category_source"],
                "level": node["level"],
                "parent_code": node["parent_code"],
                "opening_balance": float(node["opening_balance"]),
                "period_debit": float(node["period_debit"]),
                "period_credit": float(node["period_credit"]),
                "ending_balance": float(node["ending_balance"]),
            }
        )

    return {
        "book_id": book_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
        "category_summary": [
            {
                "category": v["category_name"],
                "category_code": v["category_code"],
                "category_name": v["category_name"],
                "period_debit": float(v["period_debit"]),
                "period_credit": float(v["period_credit"]),
                "ending_balance": float(v["ending_balance"]),
            }
            for k, v in sorted(category_summary.items(), key=lambda x: x[0])
        ],
    }
