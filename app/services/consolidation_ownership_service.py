from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationOwnershipError(RuntimeError):
    pass


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationOwnershipError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationOwnershipError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationOwnershipError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str, required: bool = True) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise ConsolidationOwnershipError(f"{field}_required")
        return None
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationOwnershipError(f"{field}_invalid") from err


def _normalize_ownership_ratio(value: object) -> Decimal:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationOwnershipError("ownership_pct_required")
    try:
        pct = Decimal(raw)
    except Exception as err:
        raise ConsolidationOwnershipError("ownership_pct_invalid") from err
    if pct <= 0:
        raise ConsolidationOwnershipError("ownership_pct_invalid")
    if pct <= 1:
        return pct
    if pct <= 100:
        return pct / Decimal("100")
    raise ConsolidationOwnershipError("ownership_pct_invalid")


def create_consolidation_ownership(payload: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    parent_entity_id = _parse_positive_int(payload.get("parent_entity_id"), "parent_entity_id")
    child_entity_id = _parse_positive_int(payload.get("child_entity_id"), "child_entity_id")
    if parent_entity_id == child_entity_id:
        raise ConsolidationOwnershipError("parent_child_same_invalid")
    ownership_ratio = _normalize_ownership_ratio(payload.get("ownership_pct"))
    effective_from = _parse_date(payload.get("effective_from"), "effective_from", required=True)
    effective_to = _parse_date(payload.get("effective_to"), "effective_to", required=False)
    if effective_to and effective_to < effective_from:
        raise ConsolidationOwnershipError("effective_period_invalid")
    operator_raw = payload.get("operator_id")
    operator_id = int(operator_raw) if str(operator_raw or "").strip().isdigit() else 0

    provider = get_connection_provider()
    with provider.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"),
            {"gid": group_id},
        ).fetchone()
        if not exists:
            raise ConsolidationOwnershipError("consolidation_group_not_found")

        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_ownership (
                    group_id, parent_entity_id, child_entity_id,
                    ownership_pct, effective_from, effective_to,
                    status, is_enabled, operator_id
                ) VALUES (
                    :group_id, :parent_entity_id, :child_entity_id,
                    :ownership_pct, :effective_from, :effective_to,
                    'active', 1, :operator_id
                )
                """
            ),
            {
                "group_id": group_id,
                "parent_entity_id": parent_entity_id,
                "child_entity_id": child_entity_id,
                "ownership_pct": ownership_ratio,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "operator_id": operator_id,
            },
        )
        oid = int(result.lastrowid or 0)

    return {
        "id": oid,
        "consolidation_group_id": group_id,
        "parent_entity_id": parent_entity_id,
        "child_entity_id": child_entity_id,
        "ownership_pct": float(ownership_ratio),
        "ownership_scale": "0_to_1_ratio",
        "effective_from": effective_from.isoformat(),
        "effective_to": effective_to.isoformat() if effective_to else "",
        "status": "active",
        "is_enabled": 1,
        "operator_id": operator_id,
    }


def list_consolidation_ownership(params: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(params.get("consolidation_group_id") or params.get("group_id"), "consolidation_group_id")
    as_of = _parse_date(params.get("as_of"), "as_of", required=True)
    provider = get_connection_provider()
    with provider.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, group_id, parent_entity_id, child_entity_id, ownership_pct,
                       effective_from, effective_to, status, is_enabled, operator_id, created_at
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
        items.append(
            {
                "id": int(row.id),
                "consolidation_group_id": int(row.group_id),
                "parent_entity_id": int(row.parent_entity_id),
                "child_entity_id": int(row.child_entity_id),
                "ownership_pct": float(Decimal(str(row.ownership_pct or 0))),
                "ownership_scale": "0_to_1_ratio",
                "effective_from": row.effective_from.isoformat() if row.effective_from else "",
                "effective_to": row.effective_to.isoformat() if row.effective_to else "",
                "status": str(row.status or ""),
                "is_enabled": int(row.is_enabled or 0),
                "operator_id": int(row.operator_id or 0),
                "created_at": str(row.created_at or ""),
            }
        )
    return {"items": items, "consolidation_group_id": group_id, "as_of": as_of.isoformat(), "ownership_scale": "0_to_1_ratio"}
