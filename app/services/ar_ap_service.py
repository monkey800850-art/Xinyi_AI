from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class ArApError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise ArApError("invalid_date") from err


def _get_as_of(params: Dict[str, str]) -> date:
    raw = (params.get("as_of_date") or "").strip()
    if not raw:
        return date.today()
    return _parse_date(raw)


def _is_receivable_payable_filter() -> str:
    # use subject name/category/note keywords
    return (
        "(s.name LIKE '%应收%' OR s.name LIKE '%应付%' OR s.name LIKE '%往来%' "
        "OR s.category LIKE '%应收%' OR s.category LIKE '%应付%' OR s.category LIKE '%往来%' "
        "OR s.note LIKE '%应收%' OR s.note LIKE '%应付%' OR s.note LIKE '%往来%')"
    )


def get_due_warnings(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise ArApError("book_id required")

    try:
        book_id = int(book_id_raw)
    except Exception as err:
        raise ArApError("book_id must be integer") from err

    as_of = _get_as_of(params)
    days_before_raw = (params.get("days_before") or "").strip() or "10"
    try:
        days_before = int(days_before_raw)
    except Exception as err:
        raise ArApError("days_before must be integer") from err

    warning_date = as_of + timedelta(days=days_before)

    sql = f"""
        SELECT
            vl.subject_code,
            vl.subject_name,
            vl.aux_type,
            vl.aux_code,
            vl.aux_name,
            vl.aux_display,
            v.id AS voucher_id,
            v.voucher_date,
            vl.due_date,
            s.balance_direction,
            vl.debit,
            vl.credit
        FROM voucher_lines vl
        JOIN vouchers v ON v.id = vl.voucher_id
        JOIN subjects s ON s.book_id = v.book_id AND s.code = vl.subject_code
        WHERE v.book_id = :book_id
          AND v.status = 'posted'
          AND vl.due_date IS NOT NULL
          AND { _is_receivable_payable_filter() }
    """

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"book_id": book_id}).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        balance = Decimal("0")
        if (r.balance_direction or "").upper() == "CREDIT":
            balance = Decimal(str(r.credit)) - Decimal(str(r.debit))
        else:
            balance = Decimal(str(r.debit)) - Decimal(str(r.credit))

        if balance == 0:
            continue

        status = None
        if r.due_date < as_of:
            status = "overdue"
        elif r.due_date <= warning_date:
            status = "warning"
        else:
            continue

        counterparty = r.aux_name or r.aux_display or r.aux_code or ""

        items.append(
            {
                "voucher_id": r.voucher_id,
                "voucher_date": r.voucher_date.isoformat(),
                "subject_code": r.subject_code,
                "subject_name": r.subject_name,
                "counterparty": counterparty,
                "aux_type": r.aux_type or "",
                "aux_code": r.aux_code or "",
                "due_date": r.due_date.isoformat(),
                "amount": float(balance),
                "status": status,
                "days_overdue": (as_of - r.due_date).days if r.due_date < as_of else 0,
            }
        )

    return {
        "book_id": book_id,
        "as_of_date": as_of.isoformat(),
        "days_before": days_before,
        "items": items,
    }


def get_warning_summary(params: Dict[str, str]) -> Dict[str, object]:
    data = get_due_warnings(params)
    due_soon_amount = Decimal("0")
    overdue_amount = Decimal("0")
    due_soon_count = 0
    overdue_count = 0

    for item in data["items"]:
        amount = Decimal(str(item["amount"]))
        if item["status"] == "warning":
            due_soon_amount += amount
            due_soon_count += 1
        if item["status"] == "overdue":
            overdue_amount += amount
            overdue_count += 1

    return {
        "book_id": data["book_id"],
        "as_of_date": data["as_of_date"],
        "due_soon_count": due_soon_count,
        "overdue_count": overdue_count,
        "due_soon_amount": float(due_soon_amount),
        "overdue_amount": float(overdue_amount),
    }


def get_aging_report(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()
    if not book_id_raw or not start_raw or not end_raw:
        raise ArApError("book_id/start_date/end_date required")

    try:
        book_id = int(book_id_raw)
    except Exception as err:
        raise ArApError("book_id must be integer") from err

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)
    as_of = _get_as_of(params)

    sql = f"""
        SELECT
            vl.aux_type,
            COALESCE(vl.aux_code, '') AS aux_code,
            COALESCE(vl.aux_name, vl.aux_display, '') AS aux_name,
            SUM(CASE
                  WHEN s.balance_direction = 'CREDIT'
                    THEN (vl.credit - vl.debit)
                  ELSE (vl.debit - vl.credit)
                END) AS balance_sum,
            SUM(CASE
                  WHEN v.voucher_date BETWEEN :start_date AND :end_date THEN
                    CASE WHEN s.balance_direction = 'CREDIT'
                      THEN (vl.credit - vl.debit)
                    ELSE (vl.debit - vl.credit)
                    END
                  ELSE 0 END) AS period_sum,
            SUM(CASE
                  WHEN vl.due_date < :as_of_date THEN
                    CASE WHEN s.balance_direction = 'CREDIT'
                      THEN (vl.credit - vl.debit)
                    ELSE (vl.debit - vl.credit)
                    END
                  ELSE 0 END) AS overdue_sum,
            MAX(CASE
                  WHEN vl.due_date < :as_of_date THEN DATEDIFF(:as_of_date, vl.due_date)
                  ELSE 0 END) AS max_overdue_days
        FROM voucher_lines vl
        JOIN vouchers v ON v.id = vl.voucher_id
        JOIN subjects s ON s.book_id = v.book_id AND s.code = vl.subject_code
        WHERE v.book_id = :book_id
          AND v.status = 'posted'
          AND vl.due_date IS NOT NULL
          AND { _is_receivable_payable_filter() }
        GROUP BY vl.aux_type, aux_code, aux_name
        ORDER BY aux_code ASC
    """

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            {
                "book_id": book_id,
                "start_date": start_date,
                "end_date": end_date,
                "as_of_date": as_of,
            },
        ).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        items.append(
            {
                "aux_type": r.aux_type or "",
                "counterparty_code": r.aux_code or "",
                "counterparty_name": r.aux_name or "",
                "balance": float(Decimal(str(r.balance_sum or 0))),
                "period_amount": float(Decimal(str(r.period_sum or 0))),
                "overdue_amount": float(Decimal(str(r.overdue_sum or 0))),
                "overdue_days": int(r.max_overdue_days or 0),
            }
        )

    return {
        "book_id": book_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "as_of_date": as_of.isoformat(),
        "items": items,
    }
