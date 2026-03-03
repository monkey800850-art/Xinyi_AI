import os
from datetime import datetime, date, timedelta
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


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
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


def _table_columns(conn, table_name: str) -> set[str]:
    def _read_column_name(row) -> str:
        if row is None:
            return ""
        value = getattr(row, "column_name", None)
        if value is None:
            mapping = getattr(row, "_mapping", None)
            if mapping is not None:
                try:
                    value = mapping.get("column_name")
                except Exception:
                    value = None
                if value is None:
                    try:
                        value = mapping.get("COLUMN_NAME")
                    except Exception:
                        value = None
            if value is None and isinstance(row, (tuple, list)) and len(row) > 0:
                value = row[0]
        return str(value or "").strip().lower()

    try:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()
        cols = {_read_column_name(r) for r in rows}
        cols.discard("")
        if cols:
            return cols
    except Exception:
        pass

    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {str(getattr(r, "name", r[1]) or "").strip().lower() for r in rows}


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _has_attachments(attachment_count: int, attachments) -> bool:
    if int(attachment_count or 0) > 0:
        return True
    if isinstance(attachments, list):
        return len(attachments) > 0
    if isinstance(attachments, dict):
        return len(attachments.keys()) > 0
    if isinstance(attachments, str):
        return bool(attachments.strip())
    return False


def _load_budget_limit(conn, book_id: int, department: str) -> Decimal | None:
    keys = []
    dep = str(department or "").strip()
    if dep:
        keys.append(f"reimbursement_budget_limit:{book_id}:{dep}")
        keys.append(f"reimbursement_budget_limit:{dep}")
    keys.append(f"reimbursement_budget_limit:{book_id}")
    keys.append("reimbursement_budget_limit_default")
    for key in keys:
        row = conn.execute(
            text("SELECT rule_value FROM sys_rules WHERE rule_key=:k LIMIT 1"),
            {"k": key},
        ).fetchone()
        if not row:
            continue
        try:
            return Decimal(str(row.rule_value))
        except Exception:
            continue
    return None


def _department_occupied_amount(conn, book_id: int, department: str, exclude_id: int | None = None) -> Decimal:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS occupied
            FROM reimbursements
            WHERE book_id=:book_id
              AND department=:department
              AND status IN ('pending', 'in_review', 'approved')
              AND (:exclude_id IS NULL OR id<>:exclude_id)
            """
        ),
        {"book_id": int(book_id), "department": str(department or "").strip(), "exclude_id": exclude_id},
    ).fetchone()
    return _parse_decimal(getattr(row, "occupied", 0) if row else 0)


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
    approval_sla = _parse_datetime(payload.get("approval_sla"))
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
        cols = _table_columns(conn, "reimbursements")
        has_budget_check = "budget_check" in cols
        has_attachment_check = "attachment_check" in cols
        has_approval_sla = "approval_sla" in cols
        attachment_ok = _has_attachments(_as_int(attachment_count, 0), attachments)

        if rid:
            current = conn.execute(
                text("SELECT status FROM reimbursements WHERE id=:id AND book_id=:book_id"),
                {"id": rid, "book_id": book_id},
            ).fetchone()
            if not current:
                raise ReimbursementError("not_found")
            set_parts = [
                "title=:title",
                "applicant=:applicant",
                "department=:department",
                "total_amount=:total_amount",
                "attachment_count=:attachment_count",
                "attachments=:attachments",
                "updated_at=NOW()",
            ]
            params = {
                "id": rid,
                "book_id": book_id,
                "title": title,
                "applicant": applicant,
                "department": department,
                "total_amount": total_amount,
                "attachment_count": attachment_count or 0,
                "attachments": attachments,
            }
            if has_attachment_check:
                set_parts.append("attachment_check=:attachment_check")
                params["attachment_check"] = 1 if attachment_ok else 0
            if has_approval_sla:
                set_parts.append("approval_sla=:approval_sla")
                params["approval_sla"] = approval_sla
            conn.execute(
                text(
                    f"""
                    UPDATE reimbursements
                    SET {", ".join(set_parts)}
                    WHERE id=:id AND book_id=:book_id
                    """
                ),
                params,
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
            insert_cols = [
                "book_id",
                "title",
                "applicant",
                "department",
                "total_amount",
                "status",
                "attachment_count",
                "attachments",
            ]
            insert_vals = [
                ":book_id",
                ":title",
                ":applicant",
                ":department",
                ":total_amount",
                ":status",
                ":attachment_count",
                ":attachments",
            ]
            params = {
                "book_id": book_id,
                "title": title,
                "applicant": applicant,
                "department": department,
                "total_amount": total_amount,
                "status": status,
                "attachment_count": attachment_count or 0,
                "attachments": attachments,
            }
            if has_budget_check:
                insert_cols.append("budget_check")
                insert_vals.append("0")
            if has_attachment_check:
                insert_cols.append("attachment_check")
                insert_vals.append(":attachment_check")
                params["attachment_check"] = 1 if attachment_ok else 0
            if has_approval_sla:
                insert_cols.append("approval_sla")
                insert_vals.append(":approval_sla")
                params["approval_sla"] = approval_sla
            result = conn.execute(
                text(
                    f"""
                    INSERT INTO reimbursements ({", ".join(insert_cols)})
                    VALUES ({", ".join(insert_vals)})
                    """
                ),
                params,
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
        cols = _table_columns(conn, "reimbursements")
        has_budget_check = "budget_check" in cols
        has_attachment_check = "attachment_check" in cols
        has_approval_sla = "approval_sla" in cols
        row = conn.execute(
            text("SELECT * FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status not in ("draft", "pending"):
            raise ReimbursementError("invalid_status_transition")

        attachment_count = _as_int(getattr(row, "attachment_count", 0), 0)
        attachments = getattr(row, "attachments", None)
        if not _has_attachments(attachment_count, attachments):
            raise ReimbursementError(
                "attachment_required",
                [{"field": "attachments", "message": "必须上传附件后才能提交"}],
            )

        book_id = int(getattr(row, "book_id", 0) or 0)
        department = str(getattr(row, "department", "") or "").strip()
        total_amount = _parse_decimal(getattr(row, "total_amount", 0))
        budget_limit = _load_budget_limit(conn, book_id, department)
        occupied_amount = _department_occupied_amount(conn, book_id, department, exclude_id=int(row.id))
        budget_ok = True
        if budget_limit is not None:
            if total_amount + occupied_amount > budget_limit:
                raise ReimbursementError(
                    "budget_exceeded",
                    [
                        {
                            "field": "total_amount",
                            "message": "超出预算",
                            "budget_limit": float(budget_limit),
                            "occupied_amount": float(occupied_amount),
                            "current_amount": float(total_amount),
                        }
                    ],
                )
            budget_ok = True

        submit_sla = getattr(row, "approval_sla", None)
        if has_approval_sla and submit_sla is None:
            sla_hours = _as_int(os.getenv("REIMBURSEMENT_APPROVAL_SLA_HOURS", "48"), 48)
            submit_sla = datetime.now() + timedelta(hours=max(1, sla_hours))

        set_parts = ["status='in_review'", "submit_at=NOW()"]
        params = {"id": reimbursement_id}
        if has_attachment_check:
            set_parts.append("attachment_check=:attachment_check")
            params["attachment_check"] = 1
        if has_budget_check:
            set_parts.append("budget_check=:budget_check")
            params["budget_check"] = 1 if budget_ok else 0
        if has_approval_sla:
            set_parts.append("approval_sla=:approval_sla")
            params["approval_sla"] = submit_sla

        conn.execute(
            text(f"UPDATE reimbursements SET {', '.join(set_parts)} WHERE id=:id"),
            params,
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
        "budget_check": int(getattr(header, "budget_check", 0) or 0),
        "attachment_check": int(getattr(header, "attachment_check", 0) or 0),
        "approval_sla": (
            getattr(header, "approval_sla", None).isoformat() if getattr(header, "approval_sla", None) else ""
        ),
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


def list_reimbursement_sla_reminders(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise ReimbursementError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReimbursementError("book_id must be integer")

    now = datetime.now()
    engine = get_engine()
    with engine.connect() as conn:
        cols = _table_columns(conn, "reimbursements")
        if "approval_sla" not in cols:
            return {"book_id": book_id, "items": []}
        rows = conn.execute(
            text(
                """
                SELECT id, title, applicant, department, status, approval_sla
                FROM reimbursements
                WHERE book_id=:book_id
                  AND status='in_review'
                  AND approval_sla IS NOT NULL
                  AND approval_sla < :now
                ORDER BY approval_sla ASC
                """
            ),
            {"book_id": book_id, "now": now},
        ).fetchall()

    items = []
    for r in rows:
        overdue_hours = (now - r.approval_sla).total_seconds() / 3600 if r.approval_sla else 0
        items.append(
            {
                "id": int(r.id),
                "title": str(r.title or ""),
                "applicant": str(r.applicant or ""),
                "department": str(r.department or ""),
                "status": str(r.status or ""),
                "approval_sla": r.approval_sla.isoformat() if r.approval_sla else "",
                "overdue_hours": round(max(0.0, overdue_hours), 2),
            }
        )
    return {"book_id": book_id, "items": items}


def delete_reimbursement(reimbursement_id: int, operator: str, role: str) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status not in ("draft", "pending", "rejected"):
            raise ReimbursementError("invalid_status_transition")
        conn.execute(text("DELETE FROM reimbursements WHERE id=:id"), {"id": reimbursement_id})
        _log_action(conn, reimbursement_id, "delete", row.status, "deleted", operator or "", role or "")
    return {"id": reimbursement_id, "status": "deleted"}


def void_reimbursement(reimbursement_id: int, operator: str, role: str, reason: str = "") -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM reimbursements WHERE id=:id"),
            {"id": reimbursement_id},
        ).fetchone()
        if not row:
            raise ReimbursementError("not_found")
        if row.status in ("approved", "paid", "void"):
            raise ReimbursementError("invalid_status_transition")
        conn.execute(
            text("UPDATE reimbursements SET status='void', updated_at=NOW() WHERE id=:id"),
            {"id": reimbursement_id},
        )
        _log_action(conn, reimbursement_id, "void", row.status, "void", operator or "", role or "", reason or "")
    return {"id": reimbursement_id, "status": "void"}
