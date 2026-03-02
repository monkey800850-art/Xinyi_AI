from sqlalchemy import text

from app.db import get_engine
from app.db_router import get_connection_provider


class ConsolidationParameterError(Exception):
    pass


def create_consolidation_parameter(payload: dict):
    required_fields = [
        "virtual_subject_id",
        "parent_subject_type",
        "parent_subject_id",
        "child_subject_type",
        "child_subject_id",
        "ownership_ratio",
        "effective_start",
        "effective_end",
    ]

    for f in required_fields:
        if not payload.get(f):
            raise ConsolidationParameterError(f"{f}_required")

    engine = get_engine()

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO consolidation_parameters (
                    virtual_subject_id,
                    parent_subject_type,
                    parent_subject_id,
                    child_subject_type,
                    child_subject_id,
                    ownership_ratio,
                    control_type,
                    include_in_consolidation,
                    effective_start,
                    effective_end,
                    status,
                    operator_id
                )
                VALUES (
                    :virtual_subject_id,
                    :parent_subject_type,
                    :parent_subject_id,
                    :child_subject_type,
                    :child_subject_id,
                    :ownership_ratio,
                    :control_type,
                    :include_in_consolidation,
                    :effective_start,
                    :effective_end,
                    'active',
                    :operator_id
                )
            """),
            {
                "virtual_subject_id": payload["virtual_subject_id"],
                "parent_subject_type": payload["parent_subject_type"],
                "parent_subject_id": payload["parent_subject_id"],
                "child_subject_type": payload["child_subject_type"],
                "child_subject_id": payload["child_subject_id"],
                "ownership_ratio": payload["ownership_ratio"],
                "control_type": payload.get("control_type", "control"),
                "include_in_consolidation": payload.get("include_in_consolidation", 1),
                "effective_start": payload["effective_start"],
                "effective_end": payload["effective_end"],
                "operator_id": payload.get("operator_id", 1),
            },
        )

        new_id = result.lastrowid

    return {
        "id": new_id,
        "status": "active"
    }


def list_consolidation_parameters(params: dict):
    engine = get_engine()

    sql = """
        SELECT *
        FROM consolidation_parameters
        WHERE 1=1
    """

    bind = {}

    if params.get("virtual_subject_id"):
        sql += " AND virtual_subject_id = :virtual_subject_id"
        bind["virtual_subject_id"] = params["virtual_subject_id"]

    sql += " ORDER BY id DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(sql), bind).mappings().all()

    return {
        "items": [dict(r) for r in rows]
    }


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationParameterError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationParameterError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationParameterError(f"{field}_invalid")
    return parsed


def _normalize_start_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationParameterError("start_period_required")
    parts = raw.split("-")
    if len(parts) != 2:
        raise ConsolidationParameterError("start_period_invalid")
    try:
        year = int(parts[0])
        month = int(parts[1])
    except Exception as err:
        raise ConsolidationParameterError("start_period_invalid") from err
    if year < 2000 or month < 1 or month > 12:
        raise ConsolidationParameterError("start_period_invalid")
    return f"{year:04d}-{month:02d}"


def _normalize_note(value: object) -> str:
    note = str(value or "").strip()
    if len(note) > 32:
        note = note[:32]
    return note


def _period_to_date_start(period: str) -> str:
    return f"{period}-01"


def _decode_group_code(raw: str) -> str:
    prefix = "group_code:"
    text = str(raw or "").strip()
    if text.startswith(prefix):
        return text[len(prefix) :]
    return ""


def _resolve_group_id(conn, group_id_value: object, group_code_value: object) -> int:
    gid_raw = str(group_id_value or "").strip()
    if gid_raw:
        return _parse_positive_int(gid_raw, "consolidation_group_id")
    code = str(group_code_value or "").strip()
    if not code:
        raise ConsolidationParameterError("consolidation_group_id_or_group_code_required")
    row = conn.execute(
        text(
            """
            SELECT id
            FROM consolidation_groups
            WHERE group_code=:group_code
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"group_code": code},
    ).fetchone()
    if not row:
        raise ConsolidationParameterError("group_code_not_found")
    return int(row.id)


def _row_to_contract_item(row) -> dict:
    return {
        "id": int(row.id),
        "consolidation_group_id": int(row.virtual_subject_id),
        "group_code": _decode_group_code(row.parent_subject_type),
        "start_period": str(row.control_type or ""),
        "note": str(row.child_subject_type or ""),
        "updated_at": str(row.updated_at or ""),
    }


def list_consolidation_parameters_contract(group_id: int, tenant_id: str | None = None) -> dict:
    provider = get_connection_provider()
    with provider.connect(tenant_id=tenant_id) as conn:
        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, control_type, parent_subject_type, child_subject_type, updated_at
                FROM consolidation_parameters
                WHERE virtual_subject_id=:group_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": int(group_id)},
        ).fetchone()
    if not row:
        return {"items": []}
    return {"items": [_row_to_contract_item(row)]}


def upsert_consolidation_parameters_contract(payload: dict, tenant_id: str | None = None) -> dict:
    start_period = _normalize_start_period(payload.get("start_period"))
    note = _normalize_note(payload.get("note"))
    group_code = str(payload.get("group_code") or "").strip()
    operator_raw = payload.get("operator_id")
    operator_id = int(operator_raw) if str(operator_raw or "").strip().isdigit() else 1

    start_date = _period_to_date_start(start_period)
    provider = get_connection_provider()
    with provider.begin(tenant_id=tenant_id) as conn:
        group_id = _resolve_group_id(conn, payload.get("consolidation_group_id"), payload.get("group_code"))
        existing = conn.execute(
            text(
                """
                SELECT id
                FROM consolidation_parameters
                WHERE virtual_subject_id=:group_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": group_id},
        ).fetchone()

        if existing:
            param_id = int(existing.id)
            conn.execute(
                text(
                    """
                    UPDATE consolidation_parameters
                    SET parent_subject_type=:group_code_tag,
                        parent_subject_id=:group_id,
                        child_subject_type=:note,
                        child_subject_id=:group_id,
                        control_type=:start_period,
                        ownership_ratio=1.000000,
                        include_in_consolidation=1,
                        effective_start=:start_date,
                        effective_end='2099-12-31',
                        status='active',
                        operator_id=:operator_id,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": param_id,
                    "group_id": group_id,
                    "group_code_tag": f"group_code:{group_code}" if group_code else "",
                    "note": note,
                    "start_period": start_period,
                    "start_date": start_date,
                    "operator_id": operator_id,
                },
            )
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                      virtual_subject_id,
                      parent_subject_type,
                      parent_subject_id,
                      child_subject_type,
                      child_subject_id,
                      ownership_ratio,
                      control_type,
                      include_in_consolidation,
                      effective_start,
                      effective_end,
                      status,
                      operator_id
                    ) VALUES (
                      :group_id,
                      :group_code_tag,
                      :group_id,
                      :note,
                      :group_id,
                      1.000000,
                      :start_period,
                      1,
                      :start_date,
                      '2099-12-31',
                      'active',
                      :operator_id
                    )
                    """
                ),
                {
                    "group_id": group_id,
                    "group_code_tag": f"group_code:{group_code}" if group_code else "",
                    "note": note,
                    "start_period": start_period,
                    "start_date": start_date,
                    "operator_id": operator_id,
                },
            )
            param_id = int(result.lastrowid or 0)

        row = conn.execute(
            text(
                """
                SELECT id, virtual_subject_id, control_type, parent_subject_type, child_subject_type, updated_at
                FROM consolidation_parameters
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": param_id},
        ).fetchone()

    return {"item": _row_to_contract_item(row)}
