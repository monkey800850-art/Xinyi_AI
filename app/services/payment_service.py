from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class PaymentError(RuntimeError):
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


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def _log_action(conn, pid: int, action: str, from_status: str, to_status: str, operator: str, role: str, comment: str = None):
    conn.execute(
        text(
            """
            INSERT INTO payment_request_logs (
                payment_request_id, action, from_status, to_status, operator, operator_role, comment
            ) VALUES (
                :pid, :action, :from_status, :to_status, :operator, :role, :comment
            )
            """
        ),
        {
            "pid": pid,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "operator": operator,
            "role": role,
            "comment": comment,
        },
    )


def create_or_update_payment(payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id = payload.get("book_id")
    title = (payload.get("title") or "").strip()
    payee_name = (payload.get("payee_name") or "").strip()
    payee_account = (payload.get("payee_account") or "").strip()
    pay_method = (payload.get("pay_method") or "").strip()
    amount_raw = payload.get("amount")
    status = (payload.get("status") or "draft").strip()
    related_type = (payload.get("related_type") or "").strip()
    related_id = payload.get("related_id")
    reimbursement_id = payload.get("reimbursement_id")
    pid = payload.get("id")

    _require(book_id is not None, errors, "book_id", "book_id is required")
    _require(pay_method, errors, "pay_method", "pay_method is required")
    if errors:
        raise PaymentError("validation_error", errors)

    try:
        book_id = int(book_id)
    except Exception:
        raise PaymentError("validation_error", [{"field": "book_id", "message": "book_id must be integer"}])

    try:
        amount = _parse_decimal(amount_raw)
    except ValueError:
        raise PaymentError("validation_error", [{"field": "amount", "message": "金额格式非法"}])

    if amount < 0:
        raise PaymentError("validation_error", [{"field": "amount", "message": "金额不能为负"}])

    engine = get_engine()
    with engine.begin() as conn:
        if pid:
            current = conn.execute(
                text("SELECT status FROM payment_requests WHERE id=:id AND book_id=:book_id"),
                {"id": pid, "book_id": book_id},
            ).fetchone()
            if not current:
                raise PaymentError("not_found")
            conn.execute(
                text(
                    """
                    UPDATE payment_requests
                    SET title=:title, payee_name=:payee_name, payee_account=:payee_account,
                        pay_method=:pay_method, amount=:amount, related_type=:related_type,
                        related_id=:related_id, reimbursement_id=:reimbursement_id, updated_at=NOW()
                    WHERE id=:id AND book_id=:book_id
                    """
                ),
                {
                    "id": pid,
                    "book_id": book_id,
                    "title": title,
                    "payee_name": payee_name,
                    "payee_account": payee_account,
                    "pay_method": pay_method,
                    "amount": amount,
                    "related_type": related_type or None,
                    "related_id": related_id or None,
                    "reimbursement_id": reimbursement_id or None,
                },
            )
            payment_id = pid
            status = current.status
        else:
            if status not in ("draft", "pending"):
                raise PaymentError("validation_error", [{"field": "status", "message": "invalid_status"}])
            result = conn.execute(
                text(
                    """
                    INSERT INTO payment_requests (
                        book_id, title, payee_name, payee_account, pay_method, amount,
                        status, related_type, related_id, reimbursement_id
                    ) VALUES (
                        :book_id, :title, :payee_name, :payee_account, :pay_method, :amount,
                        :status, :related_type, :related_id, :reimbursement_id
                    )
                    """
                ),
                {
                    "book_id": book_id,
                    "title": title,
                    "payee_name": payee_name,
                    "payee_account": payee_account,
                    "pay_method": pay_method,
                    "amount": amount,
                    "status": status,
                    "related_type": related_type or None,
                    "related_id": related_id or None,
                    "reimbursement_id": reimbursement_id or None,
                },
            )
            payment_id = result.lastrowid

    return {"id": payment_id, "status": status, "amount": float(amount)}


def submit_payment(payment_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise PaymentError("operator_required")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status not in ("draft", "pending"):
            raise PaymentError("invalid_status_transition")

        conn.execute(
            text("UPDATE payment_requests SET status='in_review' WHERE id=:id"),
            {"id": payment_id},
        )
        _log_action(conn, payment_id, "submit", row.status, "in_review", operator, role or "")

    return {"id": payment_id, "status": "in_review"}


def approve_payment(payment_id: int, operator: str, role: str, comment: str = None) -> Dict[str, object]:
    if not operator:
        raise PaymentError("operator_required")
    if role not in ("approver", "admin"):
        raise PaymentError("permission_denied")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status != "in_review":
            raise PaymentError("invalid_status_transition")

        conn.execute(
            text("UPDATE payment_requests SET status='approved', approve_at=NOW(), reject_reason=NULL WHERE id=:id"),
            {"id": payment_id},
        )
        _log_action(conn, payment_id, "approve", row.status, "approved", operator, role, comment)

    return {"id": payment_id, "status": "approved"}


def reject_payment(payment_id: int, operator: str, role: str, reason: str) -> Dict[str, object]:
    if not operator:
        raise PaymentError("operator_required")
    if role not in ("approver", "admin"):
        raise PaymentError("permission_denied")
    if not reason:
        raise PaymentError("reject_reason_required")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status != "in_review":
            raise PaymentError("invalid_status_transition")

        conn.execute(
            text("UPDATE payment_requests SET status='rejected', reject_at=NOW(), reject_reason=:reason WHERE id=:id"),
            {"id": payment_id, "reason": reason},
        )
        _log_action(conn, payment_id, "reject", row.status, "rejected", operator, role, reason)

    return {"id": payment_id, "status": "rejected"}


def execute_payment(payment_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise PaymentError("operator_required")
    if role not in ("cashier", "admin"):
        raise PaymentError("permission_denied")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status != "approved":
            raise PaymentError("invalid_status_transition")

        conn.execute(
            text("UPDATE payment_requests SET status='paid', pay_at=NOW() WHERE id=:id"),
            {"id": payment_id},
        )
        _log_action(conn, payment_id, "execute", row.status, "paid", operator, role)

    return {"id": payment_id, "status": "paid"}


def list_payments(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    status = (params.get("status") or "").strip()
    if not book_id_raw:
        raise PaymentError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise PaymentError("book_id must be integer")

    sql = """
        SELECT id, title, payee_name, pay_method, amount, status, related_type, related_id, reimbursement_id
        FROM payment_requests
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
                "payee_name": r.payee_name or "",
                "pay_method": r.pay_method,
                "amount": float(r.amount),
                "status": r.status,
                "related_type": r.related_type or "",
                "related_id": r.related_id or "",
                "reimbursement_id": r.reimbursement_id or "",
            }
        )

    return {"book_id": book_id, "items": items}


def get_payment_detail(payment_id: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        header = conn.execute(
            text("SELECT * FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not header:
            raise PaymentError("not_found")

        logs = conn.execute(
            text(
                """
                SELECT action, from_status, to_status, operator, operator_role, comment, created_at
                FROM payment_request_logs
                WHERE payment_request_id=:id
                ORDER BY created_at ASC
                """
            ),
            {"id": payment_id},
        ).fetchall()

    return {
        "id": header.id,
        "book_id": header.book_id,
        "title": header.title or "",
        "payee_name": header.payee_name or "",
        "payee_account": header.payee_account or "",
        "pay_method": header.pay_method,
        "amount": float(header.amount),
        "status": header.status,
        "reject_reason": header.reject_reason or "",
        "related_type": header.related_type or "",
        "related_id": header.related_id or "",
        "reimbursement_id": header.reimbursement_id or "",
        "voucher_id": header.voucher_id or "",
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


def delete_payment(payment_id: int, operator: str, role: str) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status not in ("draft", "pending", "rejected"):
            raise PaymentError("invalid_status_transition")
        conn.execute(text("DELETE FROM payment_requests WHERE id=:id"), {"id": payment_id})
        _log_action(conn, payment_id, "delete", row.status, "deleted", operator or "", role or "")
    return {"id": payment_id, "status": "deleted"}


def void_payment(payment_id: int, operator: str, role: str, reason: str = "") -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payment_requests WHERE id=:id"),
            {"id": payment_id},
        ).fetchone()
        if not row:
            raise PaymentError("not_found")
        if row.status in ("paid", "void"):
            raise PaymentError("invalid_status_transition")
        conn.execute(
            text("UPDATE payment_requests SET status='void', updated_at=NOW() WHERE id=:id"),
            {"id": payment_id},
        )
        _log_action(conn, payment_id, "void", row.status, "void", operator or "", role or "", reason or "")
    return {"id": payment_id, "status": "void"}
