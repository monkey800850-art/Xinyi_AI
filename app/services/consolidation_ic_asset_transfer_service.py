import re
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set


class ConsolidationIcAssetTransferError(RuntimeError):
    pass


RULE_CODE = "IC_ASSET_TRANSFER_ONBOARD"
SOURCE = "generated"
TAG = "ic_asset_transfer_onboard"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationIcAssetTransferError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationIcAssetTransferError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationIcAssetTransferError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationIcAssetTransferError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationIcAssetTransferError(f"{field}_invalid") from err


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as err:
        raise ConsolidationIcAssetTransferError(f"{field}_invalid") from err


def _normalize_asset_class(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        raise ConsolidationIcAssetTransferError("asset_class_required")
    return raw[:32]


def _normalize_asset_ref(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationIcAssetTransferError("asset_ref_required")
    return raw[:128]


def _slug(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    out = out.strip("_")
    return out[:64] or "NA"


def _period(as_of: date) -> str:
    return as_of.strftime("%Y-%m")


def _set_id(group_id: int, as_of: date, asset_class: str, seller_book_id: int, buyer_book_id: int, asset_ref: str) -> str:
    return f"ICAST-{group_id}-{as_of.strftime('%Y%m%d')}-{_slug(asset_class)}-{seller_book_id}-{buyer_book_id}-{_slug(asset_ref)}"


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


def _normalize_tax_rate(value: object) -> Decimal:
    try:
        rate = Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0.25")
    if rate <= 0:
        return Decimal("0.25")
    if rate > 1 and rate <= 100:
        rate = rate / Decimal("100")
    if rate > 1:
        return Decimal("0.25")
    return rate.quantize(Decimal("0.0001"))


def _load_tax_rate(conn, group_id: int) -> Decimal:
    cols = _table_columns(conn, "consolidation_parameters")
    if "virtual_subject_id" not in cols or "tax_rate" not in cols:
        return Decimal("0.25")
    status_sql = " AND status='active'" if "status" in cols else ""
    row = conn.execute(
        text(
            f"""
            SELECT tax_rate
            FROM consolidation_parameters
            WHERE virtual_subject_id=:gid
            {status_sql}
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"gid": int(group_id)},
    ).fetchone()
    return _normalize_tax_rate(getattr(row, "tax_rate", None) if row else None)


def _upsert_event(
    conn,
    *,
    group_id: int,
    as_of: date,
    asset_class: str,
    seller_book_id: int,
    buyer_book_id: int,
    asset_ref: str,
    transfer_price: Decimal,
    carrying_amount: Decimal,
    gain_loss_amount: Decimal,
    tax_rate: Decimal,
    dtl_amount: Decimal,
    note: str,
    operator_id: int,
) -> int:
    row = conn.execute(
        text(
            """
            SELECT id
            FROM consolidation_ic_asset_transfer_events
            WHERE group_id=:group_id
              AND as_of_date=:as_of_date
              AND asset_class=:asset_class
              AND seller_book_id=:seller_book_id
              AND buyer_book_id=:buyer_book_id
              AND asset_ref=:asset_ref
            LIMIT 1
            """
        ),
        {
            "group_id": group_id,
            "as_of_date": as_of,
            "asset_class": asset_class,
            "seller_book_id": seller_book_id,
            "buyer_book_id": buyer_book_id,
            "asset_ref": asset_ref,
        },
    ).fetchone()
    params = {
        "group_id": group_id,
        "as_of_date": as_of,
        "asset_class": asset_class,
        "seller_book_id": seller_book_id,
        "buyer_book_id": buyer_book_id,
        "asset_ref": asset_ref,
        "transfer_price": str(transfer_price),
        "carrying_amount": str(carrying_amount),
        "gain_loss_amount": str(gain_loss_amount),
        "tax_rate_snapshot": str(tax_rate),
        "dtl_amount": str(dtl_amount),
        "original_gain_loss_amount": str(gain_loss_amount),
        "remaining_gain_loss_amount": str(gain_loss_amount),
        "original_dtl_amount": str(dtl_amount),
        "remaining_dtl_amount": str(dtl_amount),
        "note": note,
        "operator_id": operator_id,
    }
    if not row:
        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_ic_asset_transfer_events (
                    group_id, as_of_date, asset_class, seller_book_id, buyer_book_id, asset_ref,
                    transfer_price, carrying_amount, gain_loss_amount,
                    tax_rate_snapshot, dtl_amount,
                    original_gain_loss_amount, remaining_gain_loss_amount,
                    original_dtl_amount, remaining_dtl_amount,
                    note, created_by, updated_by
                ) VALUES (
                    :group_id, :as_of_date, :asset_class, :seller_book_id, :buyer_book_id, :asset_ref,
                    :transfer_price, :carrying_amount, :gain_loss_amount,
                    :tax_rate_snapshot, :dtl_amount,
                    :original_gain_loss_amount, :remaining_gain_loss_amount,
                    :original_dtl_amount, :remaining_dtl_amount,
                    :note, :operator_id, :operator_id
                )
                """
            ),
            params,
        )
        return int(result.lastrowid)

    params["id"] = int(row.id)
    conn.execute(
        text(
            """
            UPDATE consolidation_ic_asset_transfer_events
            SET transfer_price=:transfer_price,
                carrying_amount=:carrying_amount,
                gain_loss_amount=:gain_loss_amount,
                tax_rate_snapshot=:tax_rate_snapshot,
                dtl_amount=:dtl_amount,
                original_gain_loss_amount=:original_gain_loss_amount,
                remaining_gain_loss_amount=:remaining_gain_loss_amount,
                original_dtl_amount=:original_dtl_amount,
                remaining_dtl_amount=:remaining_dtl_amount,
                note=:note,
                updated_by=:operator_id,
                updated_at=NOW()
            WHERE id=:id
            """
        ),
        params,
    )
    return int(row.id)


def _build_lines(set_id: str, operator_id: int, gain_loss_amount: Decimal, dtl_amount: Decimal) -> List[Dict[str, object]]:
    lines: List[Dict[str, object]] = [
        {
            "subject_code": "IC_AST_GAIN_LOSS_PNL",
            "debit": str(gain_loss_amount if gain_loss_amount > 0 else Decimal("0")),
            "credit": str(abs(gain_loss_amount) if gain_loss_amount < 0 else Decimal("0")),
            "note": "内部资产转移损益抵销",
            "set_id": set_id,
            "source": SOURCE,
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
        {
            "subject_code": "IC_AST_GAIN_LOSS_BAL",
            "debit": str(abs(gain_loss_amount) if gain_loss_amount < 0 else Decimal("0")),
            "credit": str(gain_loss_amount if gain_loss_amount > 0 else Decimal("0")),
            "note": "内部资产转移损益抵销",
            "set_id": set_id,
            "source": SOURCE,
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
    ]
    if dtl_amount != 0:
        lines.extend(
            [
                {
                    "subject_code": "IC_AST_DTL_EXPENSE",
                    "debit": str(dtl_amount if dtl_amount > 0 else Decimal("0")),
                    "credit": str(abs(dtl_amount) if dtl_amount < 0 else Decimal("0")),
                    "note": "内部资产转移递延所得税调整",
                    "set_id": set_id,
                    "source": SOURCE,
                    "rule": RULE_CODE,
                    "evidence_ref": set_id,
                    "operator_id": str(operator_id),
                },
                {
                    "subject_code": "IC_AST_DTL_BAL",
                    "debit": str(abs(dtl_amount) if dtl_amount < 0 else Decimal("0")),
                    "credit": str(dtl_amount if dtl_amount > 0 else Decimal("0")),
                    "note": "内部资产转移递延所得税调整",
                    "set_id": set_id,
                    "source": SOURCE,
                    "rule": RULE_CODE,
                    "evidence_ref": set_id,
                    "operator_id": str(operator_id),
                },
            ]
        )
    return lines


def generate_ic_asset_transfer_onboard(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("group_id") or payload.get("consolidation_group_id"), "group_id")
    as_of = _parse_date(payload.get("as_of") or payload.get("as_of_date"), "as_of")
    asset_class = _normalize_asset_class(payload.get("asset_class"))
    seller_book_id = _parse_positive_int(payload.get("seller_book_id"), "seller_book_id")
    buyer_book_id = _parse_positive_int(payload.get("buyer_book_id"), "buyer_book_id")
    asset_ref = _normalize_asset_ref(payload.get("asset_ref"))
    transfer_price = _to_decimal(payload.get("transfer_price"), "transfer_price")
    carrying_amount = _to_decimal(payload.get("carrying_amount"), "carrying_amount")
    note = str(payload.get("note") or "").strip()[:255]
    operator = _parse_positive_int(operator_id, "operator_id")

    gain_loss_amount = (transfer_price - carrying_amount).quantize(Decimal("0.01"))

    provider = get_connection_provider()
    with provider.begin() as conn:
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationIcAssetTransferError("consolidation_group_not_found")
        tax_rate = _load_tax_rate(conn, group_id)
        dtl_amount = (gain_loss_amount * tax_rate).quantize(Decimal("0.01"))
        event_id = _upsert_event(
            conn,
            group_id=group_id,
            as_of=as_of,
            asset_class=asset_class,
            seller_book_id=seller_book_id,
            buyer_book_id=buyer_book_id,
            asset_ref=asset_ref,
            transfer_price=transfer_price,
            carrying_amount=carrying_amount,
            gain_loss_amount=gain_loss_amount,
            tax_rate=tax_rate,
            dtl_amount=dtl_amount,
            note=note,
            operator_id=operator,
        )

    set_id = _set_id(group_id, as_of, asset_class, seller_book_id, buyer_book_id, asset_ref)
    lines = _build_lines(set_id, operator, gain_loss_amount, dtl_amount)
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

    item = dict(upserted.get("item") or {})
    out_lines = list(item.get("lines") or lines)
    return {
        "group_id": group_id,
        "event_id": event_id,
        "as_of": as_of.isoformat(),
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "gain_loss_amount": float(gain_loss_amount),
        "dtl_amount": float(dtl_amount),
        "tax_rate": float(tax_rate),
        "counts": {"lines": len(out_lines)},
        "preview_lines": out_lines,
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
    }
