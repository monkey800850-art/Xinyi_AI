from datetime import date
from typing import Dict, Optional

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.audit_service import log_audit


class ConsolidationAuthorizationError(RuntimeError):
    pass


VALID_STATUS = {"active", "suspended", "revoked"}


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAuthorizationError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationAuthorizationError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationAuthorizationError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAuthorizationError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationAuthorizationError(f"{field}_invalid") from err


def _status_or_default(value: object) -> str:
    status = str(value or "active").strip().lower()
    if status not in VALID_STATUS:
        raise ConsolidationAuthorizationError("status_invalid")
    return status


def _row_to_dict(row) -> Dict[str, object]:
    return {
        "id": int(row.id),
        "virtual_subject_id": int(row.virtual_subject_id),
        "approval_document_number": str(row.approval_document_number or ""),
        "approval_document_name": str(row.approval_document_name or ""),
        "effective_start": row.effective_start.isoformat() if row.effective_start else "",
        "effective_end": row.effective_end.isoformat() if row.effective_end else "",
        "status": str(row.status or ""),
        "operator_id": int(row.operator_id) if row.operator_id is not None else None,
        "created_at": str(row.created_at or ""),
        "updated_at": str(row.updated_at or ""),
    }


def create_authorization(payload: Dict[str, object], operator: str = "", role: str = "") -> Dict[str, object]:
    virtual_subject_id = _parse_positive_int(payload.get("virtual_subject_id"), "virtual_subject_id")
    operator_id = _parse_positive_int(payload.get("operator_id"), "operator_id")
    approval_document_number = str(payload.get("approval_document_number") or "").strip()
    approval_document_name = str(payload.get("approval_document_name") or "").strip()
    if not approval_document_number:
        raise ConsolidationAuthorizationError("approval_document_number_required")
    if not approval_document_name:
        raise ConsolidationAuthorizationError("approval_document_name_required")
    effective_start = _parse_date(payload.get("effective_start"), "effective_start")
    effective_end = _parse_date(payload.get("effective_end"), "effective_end")
    if effective_start > effective_end:
        raise ConsolidationAuthorizationError("effective_period_invalid")
    status = _status_or_default(payload.get("status"))

    tenant_id = str(payload.get("tenant_id") or "").strip() or None
    provider = get_connection_provider()
    with provider.begin(tenant_id=tenant_id) as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_authorizations
                  (virtual_subject_id, approval_document_number, approval_document_name,
                   effective_start, effective_end, status, operator_id)
                VALUES
                  (:virtual_subject_id, :approval_document_number, :approval_document_name,
                   :effective_start, :effective_end, :status, :operator_id)
                """
            ),
            {
                "virtual_subject_id": virtual_subject_id,
                "approval_document_number": approval_document_number,
                "approval_document_name": approval_document_name,
                "effective_start": effective_start,
                "effective_end": effective_end,
                "status": status,
                "operator_id": operator_id,
            },
        )
        auth_id = int(result.lastrowid or 0)
        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, approval_document_number, approval_document_name,
                       effective_start, effective_end, status, operator_id, created_at, updated_at
                FROM consolidation_authorizations
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": auth_id},
        ).fetchone()

    log_audit(
        "consolidation_auth",
        "create",
        "consolidation_authorization",
        auth_id,
        operator,
        role,
        {
            "virtual_subject_id": virtual_subject_id,
            "status": status,
            "effective_start": effective_start.isoformat(),
            "effective_end": effective_end.isoformat(),
        },
    )
    return {
        "item": _row_to_dict(row),
        "evidence": {
            "table": "consolidation_authorizations",
            "key_fields": [
                "virtual_subject_id",
                "approval_document_number",
                "effective_start",
                "effective_end",
                "status",
            ],
            "api": "POST /api/authorizations",
        },
    }


def list_authorizations(params: Dict[str, object]) -> Dict[str, object]:
    virtual_subject_id_raw = str(params.get("virtual_subject_id") or "").strip()
    status = str(params.get("status") or "").strip().lower()
    tenant_id = str(params.get("tenant_id") or "").strip() or None
    provider = get_connection_provider()

    sql = """
        SELECT id, virtual_subject_id, approval_document_number, approval_document_name,
               effective_start, effective_end, status, operator_id, created_at, updated_at
        FROM consolidation_authorizations
        WHERE 1=1
    """
    bind = {}
    if virtual_subject_id_raw:
        bind["virtual_subject_id"] = _parse_positive_int(virtual_subject_id_raw, "virtual_subject_id")
        sql += " AND virtual_subject_id=:virtual_subject_id"
    if status:
        if status not in VALID_STATUS:
            raise ConsolidationAuthorizationError("status_invalid")
        bind["status"] = status
        sql += " AND status=:status"
    sql += " ORDER BY id DESC"

    with provider.connect(tenant_id=tenant_id) as conn:
        rows = conn.execute(text(sql), bind).fetchall()

    return {
        "items": [_row_to_dict(row) for row in rows],
        "evidence": {
            "table": "consolidation_authorizations",
            "api": "GET /api/authorizations",
            "filters": {
                "virtual_subject_id": bool(virtual_subject_id_raw),
                "status": bool(status),
            },
        },
    }


def set_authorization_status(
    auth_id: int, next_status: str, operator: str = "", role: str = "", payload: Optional[Dict[str, object]] = None
) -> Dict[str, object]:
    if next_status not in VALID_STATUS:
        raise ConsolidationAuthorizationError("status_invalid")
    tenant_id = str((payload or {}).get("tenant_id") or "").strip() or None
    operator_id = _parse_positive_int((payload or {}).get("operator_id"), "operator_id")
    provider = get_connection_provider()
    with provider.begin(tenant_id=tenant_id) as conn:
        existing = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, approval_document_number, approval_document_name,
                       effective_start, effective_end, status, operator_id, created_at, updated_at
                FROM consolidation_authorizations
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": int(auth_id)},
        ).fetchone()
        if not existing:
            raise ConsolidationAuthorizationError("authorization_not_found")

        conn.execute(
            text(
                """
                UPDATE consolidation_authorizations
                SET status=:status, operator_id=:operator_id, updated_at=NOW()
                WHERE id=:id
                """
            ),
            {"id": int(auth_id), "status": next_status, "operator_id": operator_id},
        )
        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, approval_document_number, approval_document_name,
                       effective_start, effective_end, status, operator_id, created_at, updated_at
                FROM consolidation_authorizations
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": int(auth_id)},
        ).fetchone()

    log_audit(
        "consolidation_auth",
        f"status_{next_status}",
        "consolidation_authorization",
        int(auth_id),
        operator,
        role,
        {
            "from_status": str(existing.status or ""),
            "to_status": next_status,
            "operator_id": operator_id,
            "virtual_subject_id": int(existing.virtual_subject_id or 0),
        },
    )
    return {
        "item": _row_to_dict(row),
        "evidence": {
            "table": "consolidation_authorizations",
            "api": f"PATCH /api/authorizations/{int(auth_id)}/{next_status}",
            "status_changed_to": next_status,
        },
    }


def assert_virtual_authorized(conn, virtual_subject_id: int, as_of_date: date) -> None:
    active = conn.execute(
        text(
            """
            SELECT id
            FROM consolidation_authorizations
            WHERE virtual_subject_id=:virtual_subject_id
              AND status='active'
              AND effective_start<=:as_of_date
              AND effective_end>=:as_of_date
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"virtual_subject_id": int(virtual_subject_id), "as_of_date": as_of_date},
    ).fetchone()
    if active:
        return

    latest = conn.execute(
        text(
            """
            SELECT id, status, effective_start, effective_end
            FROM consolidation_authorizations
            WHERE virtual_subject_id=:virtual_subject_id
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"virtual_subject_id": int(virtual_subject_id)},
    ).fetchone()
    if not latest:
        raise ConsolidationAuthorizationError("authorization_missing")
    status = str(latest.status or "").strip().lower()
    if status == "suspended":
        raise ConsolidationAuthorizationError("authorization_suspended")
    if status == "revoked":
        raise ConsolidationAuthorizationError("authorization_revoked")
    raise ConsolidationAuthorizationError("authorization_expired")
