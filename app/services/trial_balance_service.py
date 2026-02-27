from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


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
                SELECT id, code, name, level, parent_code, balance_direction
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

    for s in subjects:
        sums_for = sum_map.get(s.code, {"debit": Decimal("0"), "credit": Decimal("0")})
        opening = Decimal("0")
        if (s.balance_direction or "").upper() == "CREDIT":
            ending = opening + sums_for["credit"] - sums_for["debit"]
        else:
            ending = opening + sums_for["debit"] - sums_for["credit"]

        node = {
            "code": s.code,
            "name": s.name,
            "level": s.level,
            "parent_code": s.parent_code,
            "opening_balance": opening,
            "period_debit": sums_for["debit"],
            "period_credit": sums_for["credit"],
            "ending_balance": ending,
        }
        nodes_by_code[s.code] = node
        order.append(s.code)

    _sum_children(nodes_by_code, order)

    items = []
    for code in order:
        node = nodes_by_code[code]
        items.append(
            {
                "code": node["code"],
                "name": node["name"],
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
    }
