from typing import Dict

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationTypeError(RuntimeError):
    pass


ALLOWED_TYPES = {"same_control", "purchase"}
DEFAULT_TYPE = "purchase"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationTypeError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationTypeError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationTypeError(f"{field}_invalid")
    return parsed


def _normalize_type(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw not in ALLOWED_TYPES:
        raise ConsolidationTypeError("consolidation_type_invalid")
    return raw


def _normalize_note(value: object) -> str:
    note = str(value or "").strip()
    return note[:255]


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


def _ensure_group_exists(conn, group_id: int) -> None:
    row = conn.execute(
        text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"),
        {"gid": int(group_id)},
    ).fetchone()
    if not row:
        raise ConsolidationTypeError("consolidation_group_not_found")


def get_type(group_id: object) -> Dict[str, object]:
    gid = _parse_positive_int(group_id, "group_id")
    provider = get_connection_provider()
    with provider.connect() as conn:
        _ensure_group_exists(conn, gid)
        cols = _table_columns(conn, "consolidation_group_types")
        if not {"group_id", "consolidation_type", "note", "created_by", "created_at", "updated_by", "updated_at"}.issubset(cols):
            raise ConsolidationTypeError("consolidation_type_model_not_ready")
        row = conn.execute(
            text(
                """
                SELECT id, group_id, consolidation_type, note,
                       created_by, created_at, updated_by, updated_at
                FROM consolidation_group_types
                WHERE group_id=:gid
                LIMIT 1
                """
            ),
            {"gid": gid},
        ).fetchone()
    if not row:
        return {
            "group_id": gid,
            "consolidation_type": DEFAULT_TYPE,
            "note": "",
            "created_by": None,
            "created_at": "",
            "updated_by": None,
            "updated_at": "",
            "is_default": True,
        }
    ctype = str(row.consolidation_type or "").strip().lower()
    if ctype not in ALLOWED_TYPES:
        ctype = DEFAULT_TYPE
    return {
        "id": int(row.id),
        "group_id": int(row.group_id),
        "consolidation_type": ctype,
        "note": str(row.note or ""),
        "created_by": int(row.created_by or 0),
        "created_at": str(row.created_at or ""),
        "updated_by": int(row.updated_by or 0),
        "updated_at": str(row.updated_at or ""),
        "is_default": False,
    }


def set_type(group_id: object, payload: Dict[str, object], operator_id: object) -> Dict[str, object]:
    gid = _parse_positive_int(group_id, "group_id")
    ctype = _normalize_type(payload.get("consolidation_type"))
    note = _normalize_note(payload.get("note"))
    operator = _parse_positive_int(operator_id, "operator_id")

    provider = get_connection_provider()
    with provider.begin() as conn:
        _ensure_group_exists(conn, gid)
        cols = _table_columns(conn, "consolidation_group_types")
        if not {"group_id", "consolidation_type", "note", "created_by", "created_at", "updated_by", "updated_at"}.issubset(cols):
            raise ConsolidationTypeError("consolidation_type_model_not_ready")
        row = conn.execute(
            text(
                """
                SELECT id, group_id, consolidation_type, note,
                       created_by, created_at, updated_by, updated_at
                FROM consolidation_group_types
                WHERE group_id=:gid
                LIMIT 1
                """
            ),
            {"gid": gid},
        ).fetchone()

        if not row:
            result = conn.execute(
                text(
                    """
                    INSERT INTO consolidation_group_types
                        (group_id, consolidation_type, note, created_by, updated_by)
                    VALUES
                        (:gid, :ctype, :note, :operator, :operator)
                    """
                ),
                {"gid": gid, "ctype": ctype, "note": note, "operator": operator},
            )
            new_id = int(result.lastrowid)
            created = conn.execute(
                text(
                    """
                    SELECT id, group_id, consolidation_type, note,
                           created_by, created_at, updated_by, updated_at
                    FROM consolidation_group_types
                    WHERE id=:id
                    LIMIT 1
                    """
                ),
                {"id": new_id},
            ).fetchone()
            return {
                "id": int(created.id),
                "group_id": int(created.group_id),
                "consolidation_type": str(created.consolidation_type or ""),
                "note": str(created.note or ""),
                "created_by": int(created.created_by or 0),
                "created_at": str(created.created_at or ""),
                "updated_by": int(created.updated_by or 0),
                "updated_at": str(created.updated_at or ""),
                "is_default": False,
                "changed": True,
            }

        current_type = str(row.consolidation_type or "").strip().lower()
        current_note = str(row.note or "")
        changed = not (current_type == ctype and current_note == note)
        if changed:
            conn.execute(
                text(
                    """
                    UPDATE consolidation_group_types
                    SET consolidation_type=:ctype,
                        note=:note,
                        updated_by=:operator,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {"id": int(row.id), "ctype": ctype, "note": note, "operator": operator},
            )
            row = conn.execute(
                text(
                    """
                    SELECT id, group_id, consolidation_type, note,
                           created_by, created_at, updated_by, updated_at
                    FROM consolidation_group_types
                    WHERE id=:id
                    LIMIT 1
                    """
                ),
                {"id": int(row.id)},
            ).fetchone()

        return {
            "id": int(row.id),
            "group_id": int(row.group_id),
            "consolidation_type": str(row.consolidation_type or ""),
            "note": str(row.note or ""),
            "created_by": int(row.created_by or 0),
            "created_at": str(row.created_at or ""),
            "updated_by": int(row.updated_by or 0),
            "updated_at": str(row.updated_at or ""),
            "is_default": False,
            "changed": changed,
        }
