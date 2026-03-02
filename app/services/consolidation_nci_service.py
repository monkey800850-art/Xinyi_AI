from datetime import date
from decimal import Decimal
from typing import Dict, List

from app.services.consolidation_control_service import (
    ConsolidationControlError,
    get_consolidation_control_decision,
)


class ConsolidationNciError(RuntimeError):
    pass


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationNciError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationNciError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationNciError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationNciError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationNciError(f"{field}_invalid") from err


def get_consolidation_nci(group_id_value: object, as_of_value: object) -> Dict[str, object]:
    group_id = _parse_positive_int(group_id_value, "consolidation_group_id")
    as_of = _parse_date(as_of_value, "as_of")
    try:
        control = get_consolidation_control_decision(group_id, as_of.isoformat())
    except ConsolidationControlError as err:
        raise ConsolidationNciError(str(err)) from err

    out: List[Dict[str, object]] = []
    for item in control.get("items") or []:
        ownership_pct = Decimal(str(item.get("ownership_pct") or 0))
        is_controlled = bool(item.get("classification") == "subsidiary" or item.get("controlled"))
        include_in_consolidation = bool(item.get("include_in_full")) if is_controlled else False
        nci_pct = Decimal("1") - ownership_pct if is_controlled else Decimal("0")
        if nci_pct < 0:
            nci_pct = Decimal("0")
        rationale = (
            f"母公司持股{float(ownership_pct) * 100:.2f}%，少数股东{float(nci_pct) * 100:.2f}%"
            if is_controlled
            else f"非控制口径，母公司持股{float(ownership_pct) * 100:.2f}%，少数股东权益按0披露"
        )
        out.append(
            {
                "entity_id": int(item.get("child_entity_id") or 0),
                "ownership_pct": float(ownership_pct),
                "nci_pct": float(nci_pct),
                "is_controlled": is_controlled,
                "include_in_consolidation": include_in_consolidation,
                "rationale": rationale,
            }
        )

    return {
        "consolidation_group_id": group_id,
        "as_of": as_of.isoformat(),
        "items": out,
    }
