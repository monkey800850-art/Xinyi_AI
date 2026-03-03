from datetime import datetime
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class UserDashboardError(RuntimeError):
    pass


ROLE_ALIASES = {
    "财务经理": "finance_manager",
    "finance_manager": "finance_manager",
    "manager": "finance_manager",
    "出纳": "cashier",
    "cashier": "cashier",
    "税务": "tax",
    "tax": "tax",
    "审计": "auditor",
    "auditor": "auditor",
    "admin": "admin",
}


TASK_TEMPLATES = {
    "finance_manager": [
        {"task_code": "reimbursement_review", "title": "审核报销单", "source": "reimbursements"},
        {"task_code": "reconciliation_review", "title": "审核对账差异", "source": "bank_transactions"},
        {"task_code": "consolidation_review", "title": "审核合并审批流", "source": "consolidation_approval_flows"},
    ],
    "cashier": [
        {"task_code": "bank_reconcile_submit", "title": "提交银行对账", "source": "bank_transactions"},
        {"task_code": "payment_execute", "title": "处理付款申请", "source": "payment_requests"},
    ],
    "tax": [
        {"task_code": "tax_invoice_verify", "title": "发票查验处理", "source": "tax_invoices"},
        {"task_code": "tax_declare_prepare", "title": "税务申报准备", "source": "tax_difference_ledger"},
    ],
    "auditor": [
        {"task_code": "audit_financial_package", "title": "审计财务报表包", "source": "consolidation_audit_packages"},
        {"task_code": "audit_tax_package", "title": "审计税务差异台账", "source": "tax_difference_ledger"},
    ],
}


def _normalize_role(role: object) -> str:
    raw = str(role or "").strip()
    if not raw:
        raise UserDashboardError("role_required")
    normalized = ROLE_ALIASES.get(raw, ROLE_ALIASES.get(raw.lower()))
    if not normalized:
        raise UserDashboardError("role_invalid")
    return normalized


def _parse_optional_book_id(book_id: object) -> int | None:
    raw = str(book_id or "").strip()
    if not raw:
        return None
    try:
        val = int(raw)
    except Exception as err:
        raise UserDashboardError("book_id_invalid") from err
    if val <= 0:
        raise UserDashboardError("book_id_invalid")
    return val


def _table_exists(conn, table_name: str) -> bool:
    try:
        row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name=:table_name
                """
            ),
            {"table_name": table_name},
        ).fetchone()
        return int(getattr(row, "cnt", 0) or 0) > 0
    except Exception:
        row = conn.execute(
            text("SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type='table' AND name=:table_name"),
            {"table_name": table_name},
        ).fetchone()
        return int(getattr(row, "cnt", 0) or 0) > 0


def _count_pending(conn, task_code: str, book_id: int | None) -> int:
    bind = {"book_id": book_id}
    if task_code == "reimbursement_review":
        if not _table_exists(conn, "reimbursements"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM reimbursements WHERE status='in_review'"
        if book_id:
            sql += " AND book_id=:book_id"
        return int(conn.execute(text(sql), bind).fetchone().cnt or 0)

    if task_code in ("reconciliation_review", "bank_reconcile_submit"):
        if not _table_exists(conn, "bank_transactions"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM bank_transactions WHERE COALESCE(match_status,'unmatched')='unmatched'"
        if book_id:
            sql += " AND book_id=:book_id"
        return int(conn.execute(text(sql), bind).fetchone().cnt or 0)

    if task_code == "payment_execute":
        if not _table_exists(conn, "payment_requests"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM payment_requests WHERE status='approved'"
        if book_id:
            sql += " AND book_id=:book_id"
        return int(conn.execute(text(sql), bind).fetchone().cnt or 0)

    if task_code == "consolidation_review":
        if not _table_exists(conn, "consolidation_approval_flows"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM consolidation_approval_flows WHERE approval_status IN ('submitted','in_review')"
        return int(conn.execute(text(sql)).fetchone().cnt or 0)

    if task_code == "tax_invoice_verify":
        if not _table_exists(conn, "tax_invoices"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM tax_invoices WHERE COALESCE(verification_status,'pending') IN ('pending','failed')"
        if book_id:
            sql += " AND book_id=:book_id"
        return int(conn.execute(text(sql), bind).fetchone().cnt or 0)

    if task_code in ("tax_declare_prepare", "audit_tax_package"):
        if not _table_exists(conn, "tax_difference_ledger"):
            return 0
        sql = "SELECT COUNT(*) AS cnt FROM tax_difference_ledger WHERE ABS(COALESCE(diff_amount,0)) > 0.01"
        if book_id:
            sql += " AND book_id=:book_id"
        return int(conn.execute(text(sql), bind).fetchone().cnt or 0)

    if task_code == "audit_financial_package":
        if not _table_exists(conn, "consolidation_audit_packages"):
            return 0
        return int(
            conn.execute(
                text("SELECT COUNT(*) AS cnt FROM consolidation_audit_packages WHERE COALESCE(status,'draft')='draft'")
            ).fetchone().cnt
            or 0
        )

    return 0


def _ensure_reminder_table(conn) -> None:
    try:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dashboard_task_reminders (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    role_code VARCHAR(32) NOT NULL,
                    task_code VARCHAR(64) NOT NULL,
                    assignee VARCHAR(64) NULL,
                    message VARCHAR(255) NOT NULL,
                    book_id BIGINT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'sent',
                    reminder_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    operator VARCHAR(64) NULL,
                    operator_role VARCHAR(64) NULL
                )
                """
            )
        )
    except Exception:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS dashboard_task_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_code TEXT NOT NULL,
                    task_code TEXT NOT NULL,
                    assignee TEXT NULL,
                    message TEXT NOT NULL,
                    book_id INTEGER NULL,
                    status TEXT NOT NULL DEFAULT 'sent',
                    reminder_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    operator TEXT NULL,
                    operator_role TEXT NULL
                )
                """
            )
        )


def _recent_reminder_count(conn, task_code: str, book_id: int | None) -> int:
    _ensure_reminder_table(conn)
    sql = """
        SELECT COUNT(*) AS cnt
        FROM dashboard_task_reminders
        WHERE task_code=:task_code
          AND reminder_at >= :since_at
    """
    params = {"task_code": task_code, "since_at": (datetime.now()).strftime("%Y-%m-%d %H:%M:%S")}
    # 轻量策略：仅统计同一天
    sql = """
        SELECT COUNT(*) AS cnt
        FROM dashboard_task_reminders
        WHERE task_code=:task_code
          AND DATE(reminder_at)=DATE(CURRENT_TIMESTAMP)
    """
    if book_id:
        sql += " AND COALESCE(book_id,0)=:book_id"
        params["book_id"] = book_id
    row = conn.execute(text(sql), params).fetchone()
    return int(row.cnt or 0)


def get_role_dashboard(role: object, book_id: object = None) -> Dict[str, object]:
    role_code = _normalize_role(role)
    scope_book_id = _parse_optional_book_id(book_id)
    templates = TASK_TEMPLATES.get(role_code) or []
    if role_code == "admin":
        templates = TASK_TEMPLATES["finance_manager"] + TASK_TEMPLATES["cashier"] + TASK_TEMPLATES["tax"] + TASK_TEMPLATES["auditor"]

    engine = get_engine()
    tasks: List[Dict[str, object]] = []
    with engine.connect() as conn:
        for item in templates:
            task_code = item["task_code"]
            pending = _count_pending(conn, task_code, scope_book_id)
            reminders = _recent_reminder_count(conn, task_code, scope_book_id)
            status = "待处理" if pending > 0 else "已清空"
            tasks.append(
                {
                    "task_code": task_code,
                    "title": item["title"],
                    "pending_count": int(pending),
                    "status": status,
                    "reminder_count_today": int(reminders),
                }
            )

    return {
        "role": role_code,
        "book_id": scope_book_id,
        "task_count": len(tasks),
        "pending_total": int(sum(x["pending_count"] for x in tasks)),
        "tasks": tasks,
    }


def track_task_status(role: object, task_code: object, book_id: object = None) -> Dict[str, object]:
    role_code = _normalize_role(role)
    code = str(task_code or "").strip()
    if not code:
        raise UserDashboardError("task_code_required")
    scope_book_id = _parse_optional_book_id(book_id)
    all_tasks = {x["task_code"]: x for k, arr in TASK_TEMPLATES.items() if k != "admin" for x in arr}
    if code not in all_tasks:
        raise UserDashboardError("task_code_invalid")

    engine = get_engine()
    with engine.connect() as conn:
        pending = _count_pending(conn, code, scope_book_id)
        reminder_cnt = _recent_reminder_count(conn, code, scope_book_id)
    status = "处理中" if pending > 0 else "已完成"
    return {
        "role": role_code,
        "book_id": scope_book_id,
        "task_code": code,
        "title": all_tasks[code]["title"],
        "status": status,
        "pending_count": int(pending),
        "reminder_count_today": int(reminder_cnt),
        "next_action": "执行催办" if pending > 0 else "无需催办",
    }


def send_reminder(
    role: object,
    task_code: object,
    operator: object,
    operator_role: object,
    assignee: object = None,
    book_id: object = None,
    note: object = None,
) -> Dict[str, object]:
    role_code = _normalize_role(role)
    code = str(task_code or "").strip()
    if not code:
        raise UserDashboardError("task_code_required")
    op = str(operator or "").strip()
    if not op:
        raise UserDashboardError("operator_required")
    op_role = str(operator_role or "").strip()
    scope_book_id = _parse_optional_book_id(book_id)
    all_tasks = {x["task_code"]: x for k, arr in TASK_TEMPLATES.items() if k != "admin" for x in arr}
    if code not in all_tasks:
        raise UserDashboardError("task_code_invalid")

    assignee_text = str(assignee or "").strip() or None
    message = f"{all_tasks[code]['title']} 超时，请尽快处理。"
    extra = str(note or "").strip()
    if extra:
        message = f"{message} 备注：{extra[:120]}"

    engine = get_engine()
    with engine.begin() as conn:
        _ensure_reminder_table(conn)
        result = conn.execute(
            text(
                """
                INSERT INTO dashboard_task_reminders (
                    role_code, task_code, assignee, message, book_id, status, operator, operator_role
                ) VALUES (
                    :role_code, :task_code, :assignee, :message, :book_id, 'sent', :operator, :operator_role
                )
                """
            ),
            {
                "role_code": role_code,
                "task_code": code,
                "assignee": assignee_text,
                "message": message,
                "book_id": scope_book_id,
                "operator": op,
                "operator_role": op_role,
            },
        )
        reminder_id = int(result.lastrowid)

    return {
        "id": reminder_id,
        "role": role_code,
        "task_code": code,
        "assignee": assignee_text or "",
        "message": message,
        "status": "sent",
        "book_id": scope_book_id,
    }
