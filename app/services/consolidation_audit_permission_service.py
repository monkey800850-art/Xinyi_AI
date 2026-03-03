import json
from datetime import date
from typing import Dict

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_authorization_service import (
    ConsolidationAuthorizationError,
    assert_virtual_authorized,
)


class ConsolidationAuditPermissionError(RuntimeError):
    pass


ACTION_CODE = "cons26_audit_permission_control"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAuditPermissionError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationAuditPermissionError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationAuditPermissionError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAuditPermissionError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationAuditPermissionError(f"{field}_invalid") from err


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name=:table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {str(r[0] or "").strip().lower() for r in rows}


def run_audit_logs_and_permission_control(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    as_of = _parse_date(payload.get("as_of"), "as_of")
    operator = _parse_positive_int(operator_id, "operator_id")
    action_content = str(payload.get("action_content") or "consolidation_operation").strip()[:255]
    if not action_content:
        action_content = "consolidation_operation"

    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_audit_log")
        required = {"ts", "operator_id", "action", "group_id", "payload_json", "result_status", "result_code", "note"}
        if not required.issubset(cols):
            raise ConsolidationAuditPermissionError("audit_log_model_not_ready")
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationAuditPermissionError("consolidation_group_not_found")

        permission_granted = True
        deny_reason = ""
        try:
            assert_virtual_authorized(conn, group_id, as_of)
        except ConsolidationAuthorizationError as err:
            permission_granted = False
            deny_reason = str(err)

        payload_json = {
            "task": "CONS-26",
            "as_of": as_of.isoformat(),
            "action_content": action_content,
            "permission_granted": permission_granted,
            "operator_id": operator,
        }
        result_status = "success" if permission_granted else "forbidden"
        result_code = 200 if permission_granted else 403
        note = action_content if permission_granted else f"{action_content};{deny_reason or 'forbidden'}"
        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_audit_log
                    (ts, operator_id, action, group_id, payload_json, result_status, result_code, note)
                VALUES
                    (NOW(), :operator_id, :action, :group_id, :payload_json, :result_status, :result_code, :note)
                """
            ),
            {
                "operator_id": operator,
                "action": ACTION_CODE,
                "group_id": group_id,
                "payload_json": json.dumps(payload_json, ensure_ascii=False),
                "result_status": result_status,
                "result_code": result_code,
                "note": note,
            },
        )
        audit_id = int(result.lastrowid or 0)
        row = conn.execute(
            text(
                """
                SELECT id, ts, operator_id, action, group_id, payload_json, result_status, result_code, note
                FROM consolidation_audit_log
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": audit_id},
        ).fetchone()

    return {
        "group_id": group_id,
        "as_of": as_of.isoformat(),
        "permission_granted": permission_granted,
        "deny_reason": deny_reason,
        "audit_log": {
            "id": int(row.id or 0),
            "ts": str(row.ts or ""),
            "operator_id": int(row.operator_id or 0),
            "action": str(row.action or ""),
            "group_id": int(row.group_id or 0),
            "payload_json": str(row.payload_json or "{}"),
            "result_status": str(row.result_status or ""),
            "result_code": int(row.result_code or 0),
            "note": str(row.note or ""),
        },
    }
