from datetime import date

from sqlalchemy import text

from app.db import get_engine
from app.db_router import get_connection_provider


class ConsolidationParameterError(Exception):
    pass


VALID_METHODS = {"full", "equity", "proportion"}
VALID_SCOPES = {"raw", "after_elim"}


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


def _table_columns(conn, table_name: str) -> set[str]:
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
    return {str(r[0] or "").strip().lower() for r in rows}


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


def _normalize_method(value: object) -> str:
    method = str(value or "full").strip().lower() or "full"
    if method not in VALID_METHODS:
        raise ConsolidationParameterError("consolidation_method_invalid")
    return method


def _normalize_scope(value: object) -> str:
    scope = str(value or "raw").strip().lower() or "raw"
    if scope not in VALID_SCOPES:
        raise ConsolidationParameterError("default_scope_invalid")
    return scope


def _normalize_effective_from(value: object, fallback_period: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return _period_to_date_start(fallback_period)
    if len(raw) == 7 and raw[4] == "-":
        return _period_to_date_start(_normalize_start_period(raw))
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationParameterError("effective_from_invalid") from err
    return parsed.isoformat()


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
    method = str(getattr(row, "consolidation_method", "") or "").strip().lower() or "full"
    if method not in VALID_METHODS:
        method = "full"
    default_scope = str(getattr(row, "default_scope", "") or "").strip().lower() or "raw"
    if default_scope not in VALID_SCOPES:
        default_scope = "raw"
    effective_from = str(getattr(row, "effective_from", "") or "").strip()
    if not effective_from:
        effective_from = str(getattr(row, "effective_start", "") or "").strip()
    return {
        "id": int(row.id),
        "consolidation_group_id": int(row.virtual_subject_id),
        "group_code": _decode_group_code(row.parent_subject_type),
        "start_period": str(row.control_type or ""),
        "note": str(row.child_subject_type or ""),
        "consolidation_method": method,
        "default_scope": default_scope,
        "effective_from": effective_from,
        "updated_at": str(row.updated_at or ""),
    }


def list_consolidation_parameters_contract(group_id: int, tenant_id: str | None = None) -> dict:
    provider = get_connection_provider()
    with provider.connect(tenant_id=tenant_id) as conn:
        cols = _table_columns(conn, "consolidation_parameters")
        method_col = "consolidation_method" if "consolidation_method" in cols else "'full' AS consolidation_method"
        scope_col = "default_scope" if "default_scope" in cols else "'raw' AS default_scope"
        effective_from_col = "effective_from" if "effective_from" in cols else "effective_start AS effective_from"
        row = conn.execute(
            text(
                f"""
                SELECT id, virtual_subject_id, control_type, parent_subject_type, child_subject_type,
                       {method_col}, {scope_col}, {effective_from_col}, effective_start, updated_at
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
    method = _normalize_method(payload.get("consolidation_method"))
    default_scope = _normalize_scope(payload.get("default_scope"))
    effective_from = _normalize_effective_from(payload.get("effective_from"), start_period)
    operator_raw = payload.get("operator_id")
    operator_id = int(operator_raw) if str(operator_raw or "").strip().isdigit() else 1

    start_date = _period_to_date_start(start_period)
    provider = get_connection_provider()
    with provider.begin(tenant_id=tenant_id) as conn:
        cols = _table_columns(conn, "consolidation_parameters")
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
            set_parts = [
                "parent_subject_type=:group_code_tag",
                "parent_subject_id=:group_id",
                "child_subject_type=:note",
                "child_subject_id=:group_id",
                "control_type=:start_period",
                "ownership_ratio=1.000000",
                "include_in_consolidation=1",
                "effective_start=:start_date",
                "effective_end='2099-12-31'",
                "status='active'",
                "operator_id=:operator_id",
            ]
            if "consolidation_method" in cols:
                set_parts.append("consolidation_method=:consolidation_method")
            if "default_scope" in cols:
                set_parts.append("default_scope=:default_scope")
            if "effective_from" in cols:
                set_parts.append("effective_from=:effective_from")
            if "updated_at" in cols:
                set_parts.append("updated_at=NOW()")
            conn.execute(
                text(
                    f"""
                    UPDATE consolidation_parameters
                    SET {', '.join(set_parts)}
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
                    "consolidation_method": method,
                    "default_scope": default_scope,
                    "effective_from": effective_from,
                },
            )
        else:
            insert_cols = [
                "virtual_subject_id",
                "parent_subject_type",
                "parent_subject_id",
                "child_subject_type",
                "child_subject_id",
                "ownership_ratio",
                "control_type",
                "include_in_consolidation",
                "effective_start",
                "effective_end",
                "status",
                "operator_id",
            ]
            insert_vals = [
                ":group_id",
                ":group_code_tag",
                ":group_id",
                ":note",
                ":group_id",
                "1.000000",
                ":start_period",
                "1",
                ":start_date",
                "'2099-12-31'",
                "'active'",
                ":operator_id",
            ]
            if "consolidation_method" in cols:
                insert_cols.append("consolidation_method")
                insert_vals.append(":consolidation_method")
            if "default_scope" in cols:
                insert_cols.append("default_scope")
                insert_vals.append(":default_scope")
            if "effective_from" in cols:
                insert_cols.append("effective_from")
                insert_vals.append(":effective_from")
            result = conn.execute(
                text(
                    f"""
                    INSERT INTO consolidation_parameters ({', '.join(insert_cols)})
                    VALUES ({', '.join(insert_vals)})
                    """
                ),
                {
                    "group_id": group_id,
                    "group_code_tag": f"group_code:{group_code}" if group_code else "",
                    "note": note,
                    "start_period": start_period,
                    "start_date": start_date,
                    "operator_id": operator_id,
                    "consolidation_method": method,
                    "default_scope": default_scope,
                    "effective_from": effective_from,
                },
            )
            param_id = int(result.lastrowid or 0)

        method_col = "consolidation_method" if "consolidation_method" in cols else "'full' AS consolidation_method"
        scope_col = "default_scope" if "default_scope" in cols else "'raw' AS default_scope"
        effective_from_col = "effective_from" if "effective_from" in cols else "effective_start AS effective_from"
        row = conn.execute(
            text(
                f"""
                SELECT id, virtual_subject_id, control_type, parent_subject_type, child_subject_type,
                       {method_col}, {scope_col}, {effective_from_col}, effective_start, updated_at
                FROM consolidation_parameters
                WHERE id=:id
                LIMIT 1
                """
            ),
            {"id": param_id},
        ).fetchone()

    return {"item": _row_to_contract_item(row)}


def get_trial_balance_scope_config(conn, group_id: int, as_of_date: date) -> dict:
    cols = _table_columns(conn, "consolidation_parameters")
    method_col = "consolidation_method" if "consolidation_method" in cols else "'full' AS consolidation_method"
    scope_col = "default_scope" if "default_scope" in cols else "'raw' AS default_scope"
    effective_from_col = "effective_from" if "effective_from" in cols else "effective_start AS effective_from"
    where_effective = ""
    if "effective_from" in cols:
        where_effective = "AND (effective_from IS NULL OR effective_from<=:as_of_date)"
    elif "effective_start" in cols:
        where_effective = "AND (effective_start IS NULL OR effective_start<=:as_of_date)"
    row = conn.execute(
        text(
            f"""
            SELECT {method_col}, {scope_col}, {effective_from_col}
            FROM consolidation_parameters
            WHERE virtual_subject_id=:group_id
              {where_effective}
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"group_id": int(group_id), "as_of_date": as_of_date},
    ).fetchone()
    method = str((getattr(row, "consolidation_method", "") if row else "") or "").strip().lower() or "full"
    if method not in VALID_METHODS:
        method = "full"
    default_scope = str((getattr(row, "default_scope", "") if row else "") or "").strip().lower() or "raw"
    if default_scope not in VALID_SCOPES:
        default_scope = "raw"
    return {"consolidation_method": method, "default_scope": default_scope}
