from datetime import date
from decimal import Decimal
from typing import Dict, List, Set

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_parameters_service import get_trial_balance_scope_config


class ConsolidationControlError(RuntimeError):
    pass


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationControlError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationControlError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationControlError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationControlError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationControlError(f"{field}_invalid") from err


def _table_columns(conn, table_name: str) -> Set[str]:
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


def _effective_member_book_ids(conn, group_id: int, as_of: date) -> Set[int]:
    mcols = _table_columns(conn, "consolidation_group_members")
    member_book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
    from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
    to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
    if not member_book_col:
        return set()
    where_parts = ["group_id=:group_id", f"{member_book_col} IS NOT NULL"]
    if "status" in mcols:
        where_parts.append("status='active'")
    if "is_enabled" in mcols:
        where_parts.append("is_enabled=1")
    if from_col:
        where_parts.append(f"({from_col} IS NULL OR {from_col}<=:as_of)")
    if to_col:
        where_parts.append(f"({to_col} IS NULL OR {to_col}>=:as_of)")
    rows = conn.execute(
        text(
            f"""
            SELECT {member_book_col} AS member_book_id
            FROM consolidation_group_members
            WHERE {' AND '.join(where_parts)}
            """
        ),
        {"group_id": int(group_id), "as_of": as_of},
    ).fetchall()
    out = set()
    for r in rows:
        if r.member_book_id is not None:
            out.add(int(r.member_book_id))
    return out


def get_consolidation_control_decision(group_id_value: object, as_of_value: object) -> Dict[str, object]:
    group_id = _parse_positive_int(group_id_value, "consolidation_group_id")
    as_of = _parse_date(as_of_value, "as_of")
    provider = get_connection_provider()
    with provider.connect() as conn:
        method_cfg = get_trial_balance_scope_config(conn, group_id, as_of)
        method = str(method_cfg.get("consolidation_method") or "full").strip().lower() or "full"
        scope_book_ids = _effective_member_book_ids(conn, group_id, as_of)

        rows = conn.execute(
            text(
                """
                SELECT id, parent_entity_id, child_entity_id, ownership_pct
                FROM consolidation_ownership
                WHERE group_id=:group_id
                  AND effective_from<=:as_of
                  AND (effective_to IS NULL OR effective_to>=:as_of)
                  AND status='active'
                  AND is_enabled=1
                ORDER BY id DESC
                """
            ),
            {"group_id": group_id, "as_of": as_of},
        ).fetchall()

    items: List[Dict[str, object]] = []
    for row in rows:
        pct = Decimal(str(row.ownership_pct or 0))
        controlled = pct >= Decimal("0.5")
        classification = "none"
        include_in_full = False
        if method == "full" and controlled:
            classification = "subsidiary"
            include_in_full = True
        elif method == "equity" and Decimal("0.2") <= pct < Decimal("0.5"):
            classification = "associate"
        rationale = (
            f"method={method}; ownership={float(pct):.4f}; controlled={'yes' if controlled else 'no'}; "
            f"scope_members={len(scope_book_ids)}"
        )
        items.append(
            {
                "ownership_id": int(row.id),
                "parent_entity_id": int(row.parent_entity_id),
                "child_entity_id": int(row.child_entity_id),
                "ownership_pct": float(pct),
                "controlled": bool(controlled),
                "classification": classification,
                "include_in_full": bool(include_in_full),
                "rationale": rationale,
            }
        )

    return {
        "consolidation_group_id": group_id,
        "as_of": as_of.isoformat(),
        "method": method,
        "scope_member_count": len(scope_book_ids),
        "items": items,
    }
