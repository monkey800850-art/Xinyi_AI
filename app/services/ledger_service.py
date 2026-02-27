from datetime import date
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class LedgerError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise LedgerError("invalid_date") from err


def get_subject_ledger(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    subject_code = (params.get("subject_code") or "").strip()
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()
    summary_kw = (params.get("summary") or "").strip()
    direction = (params.get("direction") or "").strip().upper()

    if not book_id_raw or not subject_code or not start_raw or not end_raw:
        raise LedgerError("book_id/subject_code/start_date/end_date required")

    try:
        book_id = int(book_id_raw)
    except Exception as err:
        raise LedgerError("book_id must be integer") from err

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    if direction and direction not in ("DEBIT", "CREDIT"):
        raise LedgerError("direction must be DEBIT or CREDIT")

    engine = get_engine()
    with engine.connect() as conn:
        subject = conn.execute(
            text(
                """
                SELECT id, code, name
                FROM subjects
                WHERE book_id=:book_id AND code=:code
                LIMIT 1
                """
            ),
            {"book_id": book_id, "code": subject_code},
        ).fetchone()
        if not subject:
            raise LedgerError("subject_not_found")

        sql = """
            SELECT v.id AS voucher_id,
                   v.voucher_date,
                   v.voucher_word,
                   v.voucher_no,
                   vl.line_no,
                   vl.summary,
                   vl.debit,
                   vl.credit,
                   vl.note
            FROM voucher_lines vl
            JOIN vouchers v ON v.id = vl.voucher_id
            WHERE v.book_id = :book_id
              AND v.status = 'posted'
              AND vl.subject_code = :subject_code
              AND v.voucher_date BETWEEN :start_date AND :end_date
        """
        params = {
            "book_id": book_id,
            "subject_code": subject_code,
            "start_date": start_date,
            "end_date": end_date,
        }
        if summary_kw:
            sql += " AND vl.summary LIKE :summary"
            params["summary"] = f"%{summary_kw}%"
        if direction == "DEBIT":
            sql += " AND vl.debit > 0"
        if direction == "CREDIT":
            sql += " AND vl.credit > 0"
        sql += " ORDER BY v.voucher_date ASC, v.id ASC, vl.line_no ASC"

        rows = conn.execute(text(sql), params).fetchall()

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
                "debit": float(r.debit),
                "credit": float(r.credit),
                "note": r.note or "",
            }
        )

    return {
        "book_id": book_id,
        "subject_code": subject.code,
        "subject_name": subject.name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": items,
    }


def get_voucher_detail(voucher_id: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        header = conn.execute(
            text(
                """
                SELECT id, book_id, voucher_date, voucher_word, voucher_no, attachments, maker, status
                FROM vouchers
                WHERE id=:id
                """
            ),
            {"id": voucher_id},
        ).fetchone()
        if not header:
            raise LedgerError("voucher_not_found")

        lines = conn.execute(
            text(
                """
                SELECT line_no, summary, subject_code, subject_name, debit, credit, due_date, note
                FROM voucher_lines
                WHERE voucher_id=:id
                ORDER BY line_no ASC
                """
            ),
            {"id": voucher_id},
        ).fetchall()

    return {
        "id": header.id,
        "book_id": header.book_id,
        "voucher_date": header.voucher_date.isoformat(),
        "voucher_word": header.voucher_word or "",
        "voucher_no": header.voucher_no or "",
        "attachments": header.attachments,
        "maker": header.maker or "",
        "status": header.status,
        "lines": [
            {
                "line_no": r.line_no,
                "summary": r.summary or "",
                "subject_code": r.subject_code,
                "subject_name": r.subject_name,
                "debit": float(r.debit),
                "credit": float(r.credit),
                "due_date": r.due_date.isoformat() if r.due_date else "",
                "note": r.note or "",
            }
            for r in lines
        ],
    }
