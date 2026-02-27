from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple

from sqlalchemy import text

from app.db import get_engine


class VoucherValidationError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]]):
        super().__init__(message)
        self.errors = errors


def _parse_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid_amount")


def _require(cond: bool, errors: List[Dict[str, object]], row: int, field: str, msg: str):
    if not cond:
        errors.append({"row": row, "field": field, "message": msg})


def _subject_requires_due_date(subject_name: str, subject_note: str, category: str) -> bool:
    text_blob = "".join([subject_name or "", subject_note or "", category or ""]) 
    keywords = ["应收", "应付", "往来", "到期"]
    return any(k in text_blob for k in keywords)


def _check_period_open(conn, book_id: int, voucher_date: date) -> Tuple[bool, str]:
    year = voucher_date.year
    month = voucher_date.month
    row = conn.execute(
        text(
            "SELECT status FROM accounting_periods WHERE book_id=:book_id AND year=:year AND month=:month"
        ),
        {"book_id": book_id, "year": year, "month": month},
    ).fetchone()
    if not row:
        return True, ""
    if row.status != "open":
        return False, "会计期间已结账"
    return True, ""


def save_voucher(payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id = payload.get("book_id")
    voucher_date = payload.get("voucher_date")
    voucher_word = payload.get("voucher_word")
    voucher_no = payload.get("voucher_no")
    attachments = payload.get("attachments", 0)
    maker = payload.get("maker")
    status = payload.get("status") or "draft"
    lines = payload.get("lines") or []

    _require(book_id is not None, errors, 0, "book_id", "book_id is required")
    _require(voucher_date, errors, 0, "voucher_date", "voucher_date is required")
    if errors:
        raise VoucherValidationError("validation_error", errors)

    if not isinstance(lines, list) or len(lines) == 0:
        errors.append({"row": 0, "field": "lines", "message": "lines is required"})
        raise VoucherValidationError("validation_error", errors)

    try:
        book_id = int(book_id)
    except Exception:
        errors.append({"row": 0, "field": "book_id", "message": "book_id must be integer"})
        raise VoucherValidationError("validation_error", errors)

    try:
        if isinstance(voucher_date, str):
            voucher_date = date.fromisoformat(voucher_date)
    except Exception:
        errors.append({"row": 0, "field": "voucher_date", "message": "voucher_date invalid"})
        raise VoucherValidationError("validation_error", errors)

    engine = get_engine()
    with engine.begin() as conn:
        ok, msg = _check_period_open(conn, book_id, voucher_date)
        if not ok:
            errors.append({"row": 0, "field": "voucher_date", "message": msg})
            raise VoucherValidationError("validation_error", errors)

        total_debit = Decimal("0")
        total_credit = Decimal("0")

        for idx, line in enumerate(lines):
            row_no = idx + 1
            subject_code = (line.get("subject_code") or "").strip()
            subject_name_input = (line.get("subject_name") or "").strip()
            summary = line.get("summary")
            aux_display = (line.get("aux_display") or "").strip()
            aux_type = (line.get("aux_type") or "").strip()
            aux_code = (line.get("aux_code") or "").strip()
            aux_name = (line.get("aux_name") or "").strip()
            due_date = line.get("due_date")
            note = line.get("note")

            _require(subject_code, errors, row_no, "subject_code", "科目必填")

            try:
                debit = _parse_decimal(line.get("debit"))
                credit = _parse_decimal(line.get("credit"))
            except ValueError:
                errors.append({"row": row_no, "field": "amount", "message": "金额格式非法"})
                continue

            if debit < 0 or credit < 0:
                errors.append({"row": row_no, "field": "amount", "message": "金额不能为负"})
                continue

            if debit == 0 and credit == 0:
                errors.append({"row": row_no, "field": "amount", "message": "借贷金额不能同时为0"})
                continue
            if debit > 0 and credit > 0:
                errors.append({"row": row_no, "field": "amount", "message": "借贷金额不能同时填写"})
                continue

            total_debit += debit
            total_credit += credit

            subject = conn.execute(
                text(
                    "SELECT id, name, is_enabled, requires_auxiliary, note, category "
                    "FROM subjects WHERE book_id=:book_id AND code=:code LIMIT 1"
                ),
                {"book_id": book_id, "code": subject_code},
            ).fetchone()

            if not subject:
                errors.append({"row": row_no, "field": "subject_code", "message": "科目不存在"})
                continue
            if subject.is_enabled != 1:
                errors.append({"row": row_no, "field": "subject_code", "message": "科目已停用"})
                continue

            if subject.requires_auxiliary == 1 and not aux_display:
                errors.append({"row": row_no, "field": "aux_display", "message": "该科目要求填写辅助核算"})

            requires_due = _subject_requires_due_date(subject.name, subject.note, subject.category)
            if requires_due:
                if not due_date:
                    errors.append({"row": row_no, "field": "due_date", "message": "往来类科目需填写到期日"})

        if total_debit != total_credit:
            diff = total_debit - total_credit
            errors.append({"row": 0, "field": "balance", "message": f"凭证借贷不平衡，差额：{diff:.2f}"})

        if errors:
            raise VoucherValidationError("validation_error", errors)

        result = conn.execute(
            text(
                """
                INSERT INTO vouchers (book_id, voucher_date, voucher_word, voucher_no, attachments, maker, status)
                VALUES (:book_id, :voucher_date, :voucher_word, :voucher_no, :attachments, :maker, :status)
                """
            ),
            {
                "book_id": book_id,
                "voucher_date": voucher_date,
                "voucher_word": voucher_word,
                "voucher_no": voucher_no,
                "attachments": attachments or 0,
                "maker": maker,
                "status": status,
            },
        )
        voucher_id = result.lastrowid

        for idx, line in enumerate(lines):
            subject_code = (line.get("subject_code") or "").strip()
            subject_name_input = (line.get("subject_name") or "").strip()
            summary = line.get("summary")
            aux_display = (line.get("aux_display") or "").strip()
            aux_type = (line.get("aux_type") or "").strip() or None
            aux_code = (line.get("aux_code") or "").strip() or None
            aux_name = (line.get("aux_name") or "").strip() or None
            aux_id = line.get("aux_id") or None
            due_date = line.get("due_date") or None
            note = line.get("note")

            subject = conn.execute(
                text(
                    "SELECT id, name FROM subjects WHERE book_id=:book_id AND code=:code LIMIT 1"
                ),
                {"book_id": book_id, "code": subject_code},
            ).fetchone()

            debit = _parse_decimal(line.get("debit"))
            credit = _parse_decimal(line.get("credit"))

            conn.execute(
                text(
                    """
                    INSERT INTO voucher_lines (
                        voucher_id, line_no, summary,
                        subject_id, subject_code, subject_name,
                        aux_display, aux_type, aux_id, aux_code, aux_name,
                        debit, credit, due_date, note
                    ) VALUES (
                        :voucher_id, :line_no, :summary,
                        :subject_id, :subject_code, :subject_name,
                        :aux_display, :aux_type, :aux_id, :aux_code, :aux_name,
                        :debit, :credit, :due_date, :note
                    )
                    """
                ),
                {
                    "voucher_id": voucher_id,
                    "line_no": idx + 1,
                    "summary": summary,
                    "subject_id": subject.id,
                    "subject_code": subject_code,
                    "subject_name": subject_name_input or subject.name,
                    "aux_display": aux_display,
                    "aux_type": aux_type,
                    "aux_id": aux_id,
                    "aux_code": aux_code,
                    "aux_name": aux_name,
                    "debit": debit,
                    "credit": credit,
                    "due_date": due_date,
                    "note": note,
                },
            )

    return {"voucher_id": voucher_id, "status": status}
