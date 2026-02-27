from typing import Dict, Tuple

from sqlalchemy import text

from app.db import get_engine


class VoucherStatusError(RuntimeError):
    pass


def _require_role(action: str, role: str):
    if action in ("approve", "unapprove"):
        if role not in ("reviewer", "admin"):
            raise VoucherStatusError("permission_denied")
    if action in ("post", "unpost"):
        if role not in ("accountant", "admin"):
            raise VoucherStatusError("permission_denied")


def _transition_allowed(action: str, current: str) -> Tuple[bool, str, str]:
    # returns (ok, from_status, to_status)
    if action == "approve":
        return (current == "draft"), "draft", "approved"
    if action == "unapprove":
        return (current == "approved"), "approved", "draft"
    if action == "post":
        return (current == "approved"), "approved", "posted"
    if action == "unpost":
        return (current == "posted"), "posted", "approved"
    return False, current, current


def change_voucher_status(
    voucher_id: int, action: str, operator: str, role: str
) -> Dict[str, object]:
    if not operator:
        raise VoucherStatusError("operator_required")
    if not role:
        raise VoucherStatusError("role_required")

    _require_role(action, role)

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status, voucher_no FROM vouchers WHERE id=:id"),
            {"id": voucher_id},
        ).fetchone()
        if not row:
            raise VoucherStatusError("voucher_not_found")

        ok, from_status, to_status = _transition_allowed(action, row.status)
        if not ok:
            raise VoucherStatusError("invalid_status_transition")

        conn.execute(
            text("UPDATE vouchers SET status=:status WHERE id=:id"),
            {"status": to_status, "id": voucher_id},
        )

        conn.execute(
            text(
                """
                INSERT INTO voucher_audit_logs (
                    voucher_id, action, from_status, to_status, operator, operator_role
                ) VALUES (
                    :voucher_id, :action, :from_status, :to_status, :operator, :operator_role
                )
                """
            ),
            {
                "voucher_id": voucher_id,
                "action": action,
                "from_status": from_status,
                "to_status": to_status,
                "operator": operator,
                "operator_role": role,
            },
        )

    return {
        "voucher_id": voucher_id,
        "action": action,
        "from_status": from_status,
        "to_status": to_status,
        "operator": operator,
        "operator_role": role,
    }
