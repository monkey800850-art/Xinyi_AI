from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class AuxReportError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise AuxReportError("invalid_date") from err


def _require(val, message: str):
    if not val:
        raise AuxReportError(message)


def _validate_common(params: Dict[str, str]):
    book_id_raw = (params.get("book_id") or "").strip()
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()
    aux_type = (params.get("aux_type") or "").strip()

    _require(book_id_raw, "book_id required")
    _require(start_raw, "start_date required")
    _require(end_raw, "end_date required")
    _require(aux_type, "aux_type required")

    if aux_type not in ("entity", "person", "project", "department"):
        raise AuxReportError("aux_type unsupported")

    try:
        book_id = int(book_id_raw)
    except Exception as err:
        raise AuxReportError("book_id must be integer") from err

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    subject_code = (params.get("subject_code") or "").strip()
    aux_code = (params.get("aux_code") or "").strip()
    primary = (params.get("primary") or "aux").strip().lower()
    if primary not in ("aux", "subject"):
        raise AuxReportError("primary must be aux or subject")

    return {
        "book_id": book_id,
        "start_date": start_date,
        "end_date": end_date,
        "aux_type": aux_type,
        "subject_code": subject_code,
        "aux_code": aux_code,
        "primary": primary,
    }


def get_aux_balance(params: Dict[str, str]) -> Dict[str, object]:
    cfg = _validate_common(params)

    group_by_aux = cfg["primary"] == "aux"

    if group_by_aux:
        select_cols = "vl.aux_code, vl.aux_name"
        group_cols = "vl.aux_code, vl.aux_name"
    else:
        select_cols = "vl.subject_code, vl.subject_name"
        group_cols = "vl.subject_code, vl.subject_name"

    sql = f"""
        SELECT {select_cols},
               SUM(vl.debit) AS debit_sum,
               SUM(vl.credit) AS credit_sum
        FROM voucher_lines vl
        JOIN vouchers v ON v.id = vl.voucher_id
        WHERE v.book_id = :book_id
          AND v.status = 'posted'
          AND v.voucher_date BETWEEN :start_date AND :end_date
          AND vl.aux_type = :aux_type
    """

    params_sql = {
        "book_id": cfg["book_id"],
        "start_date": cfg["start_date"],
        "end_date": cfg["end_date"],
        "aux_type": cfg["aux_type"],
    }

    if cfg["subject_code"]:
        sql += " AND vl.subject_code = :subject_code"
        params_sql["subject_code"] = cfg["subject_code"]
    if cfg["aux_code"]:
        sql += " AND vl.aux_code = :aux_code"
        params_sql["aux_code"] = cfg["aux_code"]

    sql += f" GROUP BY {group_cols} ORDER BY {group_cols}"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        debit = Decimal(str(r.debit_sum or 0))
        credit = Decimal(str(r.credit_sum or 0))
        items.append(
            {
                "primary": cfg["primary"],
                "primary_code": r[0],
                "primary_name": r[1],
                "period_debit": float(debit),
                "period_credit": float(credit),
                "ending_balance": float(debit - credit),
            }
        )

    return {
        "book_id": cfg["book_id"],
        "start_date": cfg["start_date"].isoformat(),
        "end_date": cfg["end_date"].isoformat(),
        "aux_type": cfg["aux_type"],
        "primary": cfg["primary"],
        "items": items,
    }


def get_aux_ledger(params: Dict[str, str]) -> Dict[str, object]:
    cfg = _validate_common(params)

    if not cfg["subject_code"] or not cfg["aux_code"]:
        raise AuxReportError("subject_code and aux_code required")

    sql = """
        SELECT v.id AS voucher_id,
               v.voucher_date,
               v.voucher_word,
               v.voucher_no,
               vl.line_no,
               vl.summary,
               vl.subject_code,
               vl.subject_name,
               vl.aux_code,
               vl.aux_name,
               vl.debit,
               vl.credit,
               vl.note
        FROM voucher_lines vl
        JOIN vouchers v ON v.id = vl.voucher_id
        WHERE v.book_id = :book_id
          AND v.status = 'posted'
          AND v.voucher_date BETWEEN :start_date AND :end_date
          AND vl.subject_code = :subject_code
          AND vl.aux_type = :aux_type
          AND vl.aux_code = :aux_code
        ORDER BY v.voucher_date ASC, v.id ASC, vl.line_no ASC
    """

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            {
                "book_id": cfg["book_id"],
                "start_date": cfg["start_date"],
                "end_date": cfg["end_date"],
                "subject_code": cfg["subject_code"],
                "aux_type": cfg["aux_type"],
                "aux_code": cfg["aux_code"],
            },
        ).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        items.append(
            {
                "voucher_id": r.voucher_id,
                "voucher_date": r.voucher_date.isoformat(),
                "voucher_word": r.voucher_word or "",
                "voucher_no": r.voucher_no or "",
                "line_no": r.line_no,
                "summary": r.summary or "",
                "subject_code": r.subject_code,
                "subject_name": r.subject_name,
                "aux_code": r.aux_code,
                "aux_name": r.aux_name,
                "debit": float(r.debit),
                "credit": float(r.credit),
                "note": r.note or "",
            }
        )

    return {
        "book_id": cfg["book_id"],
        "start_date": cfg["start_date"].isoformat(),
        "end_date": cfg["end_date"].isoformat(),
        "aux_type": cfg["aux_type"],
        "subject_code": cfg["subject_code"],
        "aux_code": cfg["aux_code"],
        "items": items,
    }
