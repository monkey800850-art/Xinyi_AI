from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple

from sqlalchemy import text

from app.db import get_engine


class ReimbursementError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


def _parse_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid_amount")


def _parse_date(value) -> date:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def _sum_items(items: List[Dict[str, object]]) -> Decimal:
    total = Decimal("0")
    for item in items:
        try:
            amt = _parse_decimal(item.get("amount"))
        except ValueError:
            raise ReimbursementError("validation_error", [{"field": "amount", "message": "金额格式非法"}])
        if amt < 0:
            raise ReimbursementError("validation_error", [{"field": "amount", "message": "金额不能为负"}])
        total += amt
    return total


def _log_action(conn, reimbursement_id: int, action: str, from_status: str, to_status: str, operator: str, role: str, comment: str = None):
    conn.execute(
        text(
            """
            INSERT INTO reimbursement_logs (
                reimbursement_id, action, from_status, to_status, operator, operator_role, comment
            ) VALUES (
                :rid, :action, :from_status, :to_status, :operator, :role, :comment
            )
            """
        ),
        {
            "rid": reimbursement_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "operator": operator,
            "role": role,
            "comment": comment,
        },
    )


def create_or_update_reimbursement(payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id = payload.get("book_id")
    title = (payload.get("title") or "").strip()
    applicant = (payload.get("applicant") or "").strip()
    department = (payload.get("department") or "").strip()
    status = (payload.get("status") or "draft").strip()
    attachment_count = payload.get("attachment_count", 0)
    attachments = payload.get("attachments")
    items = payload.get("items") or []
    rid = payload.get("id")

    _require(book_id is not None, errors, "book_id", "book_id is required")
    if not isinstance(items, list):
        errors.append({"field": "items", "message": "items must be list"})
    if errors:
        raise ReimbursementError("validation_error", errors)

    try:
        book_id = int(book_id)
    except Exception:
        raise ReimbursementError("validation_error", [{"field": "book_id", "message": "book_id must be integer"}])

    total_amount = _sum_items(items)

    engine = get_engine()
    with engine.begin() as conn:
        if rid:
            current = conn.execute(
                text("SELECT status FROM reimbursements WHERE id=:id AND book_id=:book_id"),
                {"id": rid, "book_id": book_id},
            ).fetchone()
            if not current:
                raise ReimbursementError("not_found")
            conn.execute(
                text(
                    """
                    UPDATE reimbursements
                    SET title=:title, applicant=:applicant, department=:department,
                        total_amount=:total_amount, attachment_count=:attachment_count,
                        attachments=:attachments, updated_at=NOW()
                    WHERE id=:id AND book_id=:book_id
                    """
                ),
                {
                    "id": rid,
                    "book_id": book_id,
                    "title": title,
                    "applicant": applicant,
                    "department": department,
                    "total_amount": total_amount,
                    "attachment_count": attachment_count or 0,
                    "attachments": attachments,
                },
            )
            conn.execute(
                text("DELETE FROM reimbursement_items WHERE reimbursement_id=:id"),
                {"id": rid},
            )
            reimbursement_id = rid
            status = current.status
        else:
            if status not in ("draft", "pending"):
                raise ReimbursementError("validation_error", [{"field": "status", "message": "invalid_status"}])
            result = conn.execute(
                text(
                    """
                    INSERT INTO reimbursements (book_id, title, applicant, department, total_amount, status, attachment_count, attachments)
                    VALUES (:book_id, :title, :applicant, :department, :total_amount, :status, :attachment_count, :attachments)
                    """
                ),
                {
                    "book_id": book_id,
                    "title": title,
                    "applicant": applicant,
                    "department": department,
                    "total_amount": total_amount,
                    "status": status,
                    "attachment_count": attachment_count or 0,
                    "attachments": attachments,
                },
            )
            reimbursement_id = result.lastrowid

        for idx, item in enumerate(items):
            conn.execute(
                text(
                    """
                    INSERT INTO reimbursement_items (
                        reimbursement_id, line_no, expense_date, category, description, amount
                    ) VALUES (
                        :rid, :line_no, :expense_date, :category, :description, :amount
                    )
                    """
                ),
                {
                    "rid": reimbursement_id,
                    "line_no": idx + 1,
                    "expense_date": _parse_date(item.get("expense_date")),
                    "category": item.get("category"),
                    "description": item.get("description"),
                    "amount": _parse_decimal(item.get("amount")),
                },
            )

    return {"id": reimbursement_id, "status": status, "total_amount": float(total_amount)}


def submit_reimbursement(reimbursement_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise ReimbursementError("operator_required")
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status not in ("draft", "pending"):
            raise ReimbursementError("invalid_status_transition")

        conn.execute(
            text("UPDATE reimbursements SET status='in_review', submit_at=NOW() WHERE id=:id"),
            {"id": reimbursement_id},
        )
        _log_action(conn, reimbursement_id, "submit", row.status, "in_review", operator, role or "")

    return {"id": reimbursement_id, "status": "in_review"}


def approve_reimbursement(reimbursement_id: int, operator: str, role: str, comment: str = None) -> Dict[str, object]:
    if not operator:
        raise ReimbursementError("operator_required")
    if role not in ("approver", "admin"):
        raise ReimbursementError("permission_denied")
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status != "in_review":
            raise ReimbursementError("invalid_status_transition")

        conn.execute(
            text("UPDATE reimbursements SET status='approved', approve_at=NOW(), reject_reason=NULL WHERE id=:id"),
            {"id": reimbursement_id},
        )
        _log_action(conn, reimbursement_id, "approve", row.status, "approved", operator, role, comment)

    return {"id": reimbursement_id, "status": "approved"}


def reject_reimbursement(reimbursement_id: int, operator: str, role: str, reason: str) -> Dict[str, object]:
    if not operator:
        raise ReimbursementError("operator_required")
    if role not in ("approver", "admin"):
        raise ReimbursementError("permission_denied")
    if not reason:
        raise ReimbursementError("reject_reason_required")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status != "in_review":
            raise ReimbursementError("invalid_status_transition")

        conn.execute(
            text("UPDATE reimbursements SET status='rejected', reject_at=NOW(), reject_reason=:reason WHERE id=:id"),
            {"id": reimbursement_id, "reason": reason},
        )
        _log_action(conn, reimbursement_id, "reject", row.status, "rejected", operator, role, reason)

    return {"id": reimbursement_id, "status": "rejected"}


def list_reimbursements(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    status = (params.get("status") or "").strip()
    if not book_id_raw:
        raise ReimbursementError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReimbursementError("book_id must be integer")

    sql = """
        SELECT id, title, applicant, department, total_amount, status, reject_reason, created_at
        FROM reimbursements
        WHERE book_id=:book_id
    """
    params_sql = {"book_id": book_id}
    if status:
        sql += " AND status=:status"
        params_sql["status"] = status
    sql += " ORDER BY id DESC"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "title": r.title or "",
                "applicant": r.applicant or "",
                "department": r.department or "",
                "total_amount": float(r.total_amount),
                "status": r.status,
                "reject_reason": r.reject_reason or "",
                "created_at": r.created_at.isoformat(),
            }
        )

    return {"book_id": book_id, "items": items}


def get_reimbursement_detail(reimbursement_id: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        header = conn.execute(
            text("SELECT * FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not header:
            raise ReimbursementError("not_found")

        items = conn.execute(
            text(
                """
                SELECT line_no, expense_date, category, description, amount
                FROM reimbursement_items
                WHERE reimbursement_id=:id
                ORDER BY line_no ASC
                """
            ),
            {"id": reimbursement_id},
        ).fetchall()

        logs = conn.execute(
            text(
                """
                SELECT action, from_status, to_status, operator, operator_role, comment, created_at
                FROM reimbursement_logs
                WHERE reimbursement_id=:id
                ORDER BY created_at ASC
                """
            ),
            {"id": reimbursement_id},
        ).fetchall()

    return {
        "id": header.id,
        "book_id": header.book_id,
        "title": header.title or "",
        "applicant": header.applicant or "",
        "department": header.department or "",
        "total_amount": float(header.total_amount),
        "status": header.status,
        "reject_reason": header.reject_reason or "",
        "attachment_count": header.attachment_count,
        "attachments": header.attachments,
        "items": [
            {
                "line_no": r.line_no,
                "expense_date": r.expense_date.isoformat() if r.expense_date else "",
                "category": r.category or "",
                "description": r.description or "",
                "amount": float(r.amount),
            }
            for r in items
        ],
        "logs": [
            {
                "action": l.action,
                "from_status": l.from_status,
                "to_status": l.to_status,
                "operator": l.operator,
                "operator_role": l.operator_role,
                "comment": l.comment or "",
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }


def get_reimbursement_stats(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise ReimbursementError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReimbursementError("book_id must be integer")

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt, SUM(total_amount) AS amt
                FROM reimbursements
                WHERE book_id=:book_id
                GROUP BY status
                """
            ),
            {"book_id": book_id},
        ).fetchall()

    items = []
    for r in rows:
        items.append({"status": r.status, "count": int(r.cnt), "amount": float(r.amt or 0)})

    return {"book_id": book_id, "items": items}
