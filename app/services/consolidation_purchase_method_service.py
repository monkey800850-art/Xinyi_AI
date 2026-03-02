import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set
from app.services.consolidation_nci_service import ConsolidationNciError, get_consolidation_nci


class ConsolidationPurchaseMethodError(RuntimeError):
    pass


RULE_CODE = "PPA_PURCHASE_METHOD"
SOURCE = "generated"
TAG = "purchase_method"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationPurchaseMethodError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid")
    return parsed


def _parse_optional_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid") from err
    if parsed < 0:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationPurchaseMethodError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid") from err


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as err:
        raise ConsolidationPurchaseMethodError(f"{field}_invalid") from err


def _json_or_empty(value: object, field: str) -> str:
    if value in (None, ""):
        return "{}"
    if isinstance(value, str):
        raw = value.strip() or "{}"
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return json.dumps(parsed, ensure_ascii=False)
            raise ConsolidationPurchaseMethodError(f"{field}_invalid")
        except ConsolidationPurchaseMethodError:
            raise
        except Exception as err:
            raise ConsolidationPurchaseMethodError(f"{field}_invalid") from err
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    raise ConsolidationPurchaseMethodError(f"{field}_invalid")


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


def _resolve_nci_fv(group_id: int, as_of: date, acquiree_id: int, fv_net_assets: Decimal) -> Decimal:
    if acquiree_id <= 0:
        return Decimal("0")
    try:
        nci_data = get_consolidation_nci(group_id, as_of.isoformat())
    except ConsolidationNciError:
        return Decimal("0")
    for item in nci_data.get("items") or []:
        if int(item.get("entity_id") or 0) == int(acquiree_id):
            nci_pct = _to_decimal(item.get("nci_pct") or 0, "nci_pct")
            if nci_pct < 0:
                nci_pct = Decimal("0")
            return (fv_net_assets * nci_pct).quantize(Decimal("0.01"))
    return Decimal("0")


def _period(as_of: date) -> str:
    return as_of.strftime("%Y-%m")


def _set_id(group_id: int, as_of: date, acquiree_book_id: int, acquiree_entity_id: int) -> str:
    target = acquiree_entity_id if acquiree_entity_id > 0 else acquiree_book_id
    return f"PPA-{group_id}-{as_of.strftime('%Y%m%d')}-{target}"


def _build_lines(
    *,
    set_id: str,
    evidence_ref: str,
    operator_id: int,
    fv_net_assets: Decimal,
    consideration: Decimal,
    nci_fv: Decimal,
    goodwill: Decimal,
) -> List[Dict[str, object]]:
    lines: List[Dict[str, object]] = []

    def _line(subject_code: str, debit: Decimal, credit: Decimal, note: str) -> Dict[str, object]:
        return {
            "subject_code": subject_code,
            "debit": str(debit),
            "credit": str(credit),
            "note": note,
            "set_id": set_id,
            "source": SOURCE,
            "rule": RULE_CODE,
            "evidence_ref": evidence_ref,
            "operator_id": str(operator_id),
        }

    lines.append(_line("PPA_FV_NET_ASSETS", fv_net_assets, Decimal("0"), "确认可辨认净资产公允价值"))
    lines.append(_line("PPA_CONSIDERATION", Decimal("0"), consideration, "确认购买对价"))
    if nci_fv > 0:
        lines.append(_line("PPA_NCI", Decimal("0"), nci_fv, "确认少数股东权益公允价值"))

    if goodwill >= 0:
        if goodwill > 0:
            lines.append(_line("PPA_GOODWILL", goodwill, Decimal("0"), "确认商誉"))
    else:
        lines.append(_line("PPA_BARGAIN_GAIN", Decimal("0"), abs(goodwill), "确认廉价购买收益"))

    return lines


def _upsert_event(
    conn,
    *,
    group_id: int,
    acquiree_book_id: int,
    acquiree_entity_id: int,
    acquisition_date: date,
    consideration_amount: Decimal,
    acquired_pct: Decimal,
    fv_net_assets: Decimal,
    fv_adjustments_json: str,
    deferred_tax_json: str,
    notes: str,
    operator_id: int,
) -> int:
    row = conn.execute(
        text(
            """
            SELECT id
            FROM consolidation_acquisition_events
            WHERE group_id=:group_id
              AND acquisition_date=:acquisition_date
              AND acquiree_book_id=:acquiree_book_id
              AND acquiree_entity_id=:acquiree_entity_id
            LIMIT 1
            """
        ),
        {
            "group_id": group_id,
            "acquisition_date": acquisition_date,
            "acquiree_book_id": acquiree_book_id,
            "acquiree_entity_id": acquiree_entity_id,
        },
    ).fetchone()
    if not row:
        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_acquisition_events (
                    group_id, acquiree_book_id, acquiree_entity_id, acquisition_date,
                    consideration_amount, acquired_pct, fv_net_assets,
                    fv_adjustments_json, deferred_tax_json, notes,
                    created_by, updated_by
                ) VALUES (
                    :group_id, :acquiree_book_id, :acquiree_entity_id, :acquisition_date,
                    :consideration_amount, :acquired_pct, :fv_net_assets,
                    :fv_adjustments_json, :deferred_tax_json, :notes,
                    :operator_id, :operator_id
                )
                """
            ),
            {
                "group_id": group_id,
                "acquiree_book_id": acquiree_book_id,
                "acquiree_entity_id": acquiree_entity_id,
                "acquisition_date": acquisition_date,
                "consideration_amount": str(consideration_amount),
                "acquired_pct": str(acquired_pct),
                "fv_net_assets": str(fv_net_assets),
                "fv_adjustments_json": fv_adjustments_json,
                "deferred_tax_json": deferred_tax_json,
                "notes": notes,
                "operator_id": operator_id,
            },
        )
        return int(result.lastrowid)

    conn.execute(
        text(
            """
            UPDATE consolidation_acquisition_events
            SET consideration_amount=:consideration_amount,
                acquired_pct=:acquired_pct,
                fv_net_assets=:fv_net_assets,
                fv_adjustments_json=:fv_adjustments_json,
                deferred_tax_json=:deferred_tax_json,
                notes=:notes,
                updated_by=:operator_id,
                updated_at=NOW()
            WHERE id=:id
            """
        ),
        {
            "id": int(row.id),
            "consideration_amount": str(consideration_amount),
            "acquired_pct": str(acquired_pct),
            "fv_net_assets": str(fv_net_assets),
            "fv_adjustments_json": fv_adjustments_json,
            "deferred_tax_json": deferred_tax_json,
            "notes": notes,
            "operator_id": operator_id,
        },
    )
    return int(row.id)


def generate_purchase_method(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    acquiree_book_id = _parse_optional_positive_int(payload.get("acquiree_book_id"), "acquiree_book_id")
    acquiree_entity_id = _parse_optional_positive_int(payload.get("acquiree_entity_id"), "acquiree_entity_id")
    if acquiree_book_id <= 0 and acquiree_entity_id <= 0:
        raise ConsolidationPurchaseMethodError("acquiree_book_id_or_entity_id_required")
    acquisition_date = _parse_date(payload.get("acquisition_date"), "acquisition_date")
    consideration_amount = _to_decimal(payload.get("consideration_amount"), "consideration_amount")
    acquired_pct = _to_decimal(payload.get("acquired_pct"), "acquired_pct")
    fv_net_assets = _to_decimal(payload.get("fv_net_assets"), "fv_net_assets")
    fv_adjustments_json = _json_or_empty(payload.get("fv_adjustments_json"), "fv_adjustments_json")
    deferred_tax_json = _json_or_empty(payload.get("deferred_tax_json"), "deferred_tax_json")
    notes = str(payload.get("notes") or payload.get("note") or "").strip()[:255]
    operator = _parse_positive_int(operator_id, "operator_id")

    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_acquisition_events")
        required = {
            "group_id",
            "acquiree_book_id",
            "acquiree_entity_id",
            "acquisition_date",
            "consideration_amount",
            "acquired_pct",
            "fv_net_assets",
            "fv_adjustments_json",
            "deferred_tax_json",
            "notes",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        }
        if not required.issubset(cols):
            raise ConsolidationPurchaseMethodError("acquisition_event_model_not_ready")
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationPurchaseMethodError("consolidation_group_not_found")
        event_id = _upsert_event(
            conn,
            group_id=group_id,
            acquiree_book_id=acquiree_book_id,
            acquiree_entity_id=acquiree_entity_id,
            acquisition_date=acquisition_date,
            consideration_amount=consideration_amount,
            acquired_pct=acquired_pct,
            fv_net_assets=fv_net_assets,
            fv_adjustments_json=fv_adjustments_json,
            deferred_tax_json=deferred_tax_json,
            notes=notes,
            operator_id=operator,
        )

    nci_fv = _resolve_nci_fv(group_id, acquisition_date, acquiree_entity_id if acquiree_entity_id > 0 else acquiree_book_id, fv_net_assets)
    goodwill = (consideration_amount + nci_fv - fv_net_assets).quantize(Decimal("0.01"))
    set_id = _set_id(group_id, acquisition_date, acquiree_book_id, acquiree_entity_id)
    period = _period(acquisition_date)
    lines = _build_lines(
        set_id=set_id,
        evidence_ref=set_id,
        operator_id=operator,
        fv_net_assets=fv_net_assets,
        consideration=consideration_amount,
        nci_fv=nci_fv,
        goodwill=goodwill,
    )

    upserted = regenerate_generated_adjustment_set(
        group_id=group_id,
        period=period,
        operator_id=operator,
        set_id=set_id,
        rule_code=RULE_CODE,
        evidence_ref=set_id,
        tag=TAG,
        generated_lines=lines,
    )
    item = dict(upserted.get("item") or {})
    return {
        "group_id": group_id,
        "acquisition_event_id": event_id,
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "period": period,
        "goodwill": float(goodwill),
        "nci_fv": float(nci_fv),
        "preview_lines": list(item.get("lines") or lines),
        "line_count": len(list(item.get("lines") or lines)),
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
        "changed": bool(item.get("changed", True)),
    }
