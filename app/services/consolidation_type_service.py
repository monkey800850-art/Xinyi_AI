from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationTypeError(RuntimeError):
    pass


ALLOWED_TYPES = {"same_control", "non_same_control", "purchase"}
DEFAULT_TYPE = "non_same_control"


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


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationTypeError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationTypeError(f"{field}_invalid") from err


def _normalize_type(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw not in ALLOWED_TYPES:
        raise ConsolidationTypeError("consolidation_type_invalid")
    if raw == "purchase":
        return "non_same_control"
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
    if ctype == "purchase":
        ctype = "non_same_control"
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


def _parse_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _truthy(value: object) -> bool:
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def evaluate_type(group_id: object, as_of_value: object) -> Dict[str, object]:
    gid = _parse_positive_int(group_id, "group_id")
    as_of = _parse_date(as_of_value, "as_of")
    provider = get_connection_provider()
    with provider.connect() as conn:
        _ensure_group_exists(conn, gid)
        cols = _table_columns(conn, "consolidation_ownership")
        if "group_id" not in cols or "ownership_pct" not in cols:
            raise ConsolidationTypeError("ownership_model_not_ready")
        select_parts = ["id", "group_id", "parent_entity_id", "child_entity_id", "ownership_pct"]
        if "control_type" in cols:
            select_parts.append("control_type")
        else:
            select_parts.append("NULL AS control_type")
        if "under_common_control" in cols:
            select_parts.append("under_common_control")
        else:
            select_parts.append("NULL AS under_common_control")
        where_parts = ["group_id=:group_id"]
        if "effective_from" in cols:
            where_parts.append("effective_from<=:as_of")
        if "effective_to" in cols:
            where_parts.append("(effective_to IS NULL OR effective_to>=:as_of)")
        if "status" in cols:
            where_parts.append("status='active'")
        if "is_enabled" in cols:
            where_parts.append("is_enabled=1")
        rows = conn.execute(
            text(
                f"""
                SELECT {', '.join(select_parts)}
                FROM consolidation_ownership
                WHERE {' AND '.join(where_parts)}
                ORDER BY id DESC
                """
            ),
            {"group_id": gid, "as_of": as_of},
        ).fetchall()

    items: List[Dict[str, object]] = []
    same_count = 0
    non_same_count = 0
    subsidiary_count = 0
    associate_count = 0

    for row in rows:
        pct = _parse_decimal(getattr(row, "ownership_pct", 0))
        controlled = pct >= Decimal("0.5")
        classification = "none"
        if controlled:
            classification = "subsidiary"
            subsidiary_count += 1
        elif Decimal("0.2") <= pct < Decimal("0.5"):
            classification = "associate"
            associate_count += 1

        ctype_raw = str(getattr(row, "control_type", "") or "").strip().lower()
        same_flag = _truthy(getattr(row, "under_common_control", None)) or ctype_raw in {
            "same_control",
            "common_control",
            "同一控制",
        }
        if classification == "subsidiary" and same_flag:
            consolidation_type = "same_control"
            same_count += 1
        elif classification in {"subsidiary", "associate"}:
            consolidation_type = "non_same_control"
            non_same_count += 1
        else:
            consolidation_type = "non_same_control"

        rationale = (
            f"ownership={float(pct):.4f}; controlled={'yes' if controlled else 'no'}; "
            f"classification={classification}; control_type={ctype_raw or 'n/a'}; "
            f"under_common_control={'yes' if same_flag else 'no'}"
        )
        items.append(
            {
                "ownership_id": int(getattr(row, "id", 0) or 0),
                "parent_entity_id": int(getattr(row, "parent_entity_id", 0) or 0),
                "child_entity_id": int(getattr(row, "child_entity_id", 0) or 0),
                "ownership_pct": float(pct),
                "controlled": bool(controlled),
                "classification": classification,
                "consolidation_type": consolidation_type,
                "same_control": bool(consolidation_type == "same_control"),
                "rationale": rationale,
            }
        )

    return {
        "group_id": gid,
        "as_of": as_of.isoformat(),
        "items": items,
        "summary": {
            "total": len(items),
            "subsidiary_count": subsidiary_count,
            "associate_count": associate_count,
            "same_control_count": same_count,
            "non_same_control_count": non_same_count,
        },
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
                "consolidation_type": _normalize_type(created.consolidation_type),
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
            "consolidation_type": _normalize_type(row.consolidation_type),
            "note": str(row.note or ""),
            "created_by": int(row.created_by or 0),
            "created_at": str(row.created_at or ""),
            "updated_by": int(row.updated_by or 0),
            "updated_at": str(row.updated_at or ""),
            "is_default": False,
            "changed": changed,
        }
