import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set
from app.services.consolidation_nci_service import ConsolidationNciError, get_consolidation_nci


class ConsolidationNciDynamicError(RuntimeError):
    pass


RULE_CODE = "NCI_DYNAMIC"
SOURCE = "generated"
TAG = "nci_dynamic"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationNciDynamicError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationNciDynamicError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationNciDynamicError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationNciDynamicError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationNciDynamicError(f"{field}_invalid") from err


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as err:
        raise ConsolidationNciDynamicError(f"{field}_invalid") from err


def _parse_amount_map(value: object, field: str) -> Dict[int, Decimal]:
    if value in (None, "", {}):
        return {}
    data = value
    if isinstance(value, str):
        try:
            data = json.loads(value)
        except Exception as err:
            raise ConsolidationNciDynamicError(f"{field}_invalid") from err
    if not isinstance(data, dict):
        raise ConsolidationNciDynamicError(f"{field}_invalid")
    out: Dict[int, Decimal] = {}
    for key, raw_amount in data.items():
        try:
            entity_id = int(str(key).strip())
        except Exception as err:
            raise ConsolidationNciDynamicError(f"{field}_invalid") from err
        if entity_id <= 0:
            raise ConsolidationNciDynamicError(f"{field}_invalid")
        out[entity_id] = _to_decimal(raw_amount, field).quantize(Decimal("0.01"))
    return out


def _period(as_of: date) -> str:
    return as_of.strftime("%Y-%m")


def _set_id(group_id: int, as_of: date) -> str:
    return f"NCI-{group_id}-{as_of.strftime('%Y%m%d')}"


def _line(
    *,
    set_id: str,
    operator_id: int,
    subject_code: str,
    debit: Decimal,
    credit: Decimal,
    note: str,
) -> Dict[str, object]:
    return {
        "subject_code": subject_code,
        "debit": str(debit),
        "credit": str(credit),
        "note": note,
        "set_id": set_id,
        "source": SOURCE,
        "rule": RULE_CODE,
        "evidence_ref": set_id,
        "operator_id": str(operator_id),
    }


def generate_nci_dynamic(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    as_of = _parse_date(payload.get("as_of"), "as_of")
    operator = _parse_positive_int(operator_id, "operator_id")

    entity_net_assets = _parse_amount_map(payload.get("entity_net_assets"), "entity_net_assets")
    entity_net_profit = _parse_amount_map(payload.get("entity_net_profit"), "entity_net_profit")
    opening_nci_balance = _parse_amount_map(payload.get("opening_nci_balance"), "opening_nci_balance")

    try:
        nci = get_consolidation_nci(group_id, as_of.isoformat())
    except ConsolidationNciError as err:
        raise ConsolidationNciDynamicError(str(err)) from err

    set_id = _set_id(group_id, as_of)
    lines: List[Dict[str, object]] = []
    items: List[Dict[str, object]] = []

    for item in nci.get("items") or []:
        entity_id = int(item.get("entity_id") or 0)
        nci_pct = Decimal(str(item.get("nci_pct") or 0))
        if entity_id <= 0 or nci_pct <= 0:
            continue
        net_assets = entity_net_assets.get(entity_id, Decimal("0"))
        net_profit = entity_net_profit.get(entity_id, Decimal("0"))
        opening = opening_nci_balance.get(entity_id, Decimal("0"))
        share_net_assets = (net_assets * nci_pct).quantize(Decimal("0.01"))
        share_profit = (net_profit * nci_pct).quantize(Decimal("0.01"))
        closing = (opening + share_profit).quantize(Decimal("0.01"))

        items.append(
            {
                "entity_id": entity_id,
                "nci_pct": float(nci_pct),
                "net_assets": float(net_assets),
                "net_profit": float(net_profit),
                "opening_nci_balance": float(opening),
                "nci_share_of_net_assets": float(share_net_assets),
                "nci_share_of_profit": float(share_profit),
                "closing_nci_balance": float(closing),
            }
        )

        if share_profit > 0:
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator,
                    subject_code="NCI_PNL_ALLOC",
                    debit=share_profit,
                    credit=Decimal("0"),
                    note=f"NCI损益归属调整 entity={entity_id}",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator,
                    subject_code="NCI_EQUITY",
                    debit=Decimal("0"),
                    credit=share_profit,
                    note=f"NCI权益增加 entity={entity_id}",
                )
            )
        elif share_profit < 0:
            amt = abs(share_profit)
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator,
                    subject_code="NCI_EQUITY",
                    debit=amt,
                    credit=Decimal("0"),
                    note=f"NCI权益减少 entity={entity_id}",
                )
            )
            lines.append(
                _line(
                    set_id=set_id,
                    operator_id=operator,
                    subject_code="NCI_PNL_ALLOC",
                    debit=Decimal("0"),
                    credit=amt,
                    note=f"NCI损益归属冲回 entity={entity_id}",
                )
            )

    if not items:
        raise ConsolidationNciDynamicError("nci_dynamic_no_controlled_entities")
    if not lines:
        raise ConsolidationNciDynamicError("nci_dynamic_no_profit_allocation")

    upserted = regenerate_generated_adjustment_set(
        group_id=group_id,
        period=_period(as_of),
        operator_id=operator,
        set_id=set_id,
        rule_code=RULE_CODE,
        evidence_ref=set_id,
        tag=TAG,
        generated_lines=lines,
    )
    upsert_item = dict(upserted.get("item") or {})
    actual_lines = list(upsert_item.get("lines") or lines)
    return {
        "group_id": group_id,
        "as_of": as_of.isoformat(),
        "period": _period(as_of),
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "rule_code": RULE_CODE,
        "items": items,
        "preview_lines": actual_lines,
        "line_count": len(actual_lines),
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
        "changed": bool(upsert_item.get("changed", True)),
    }
