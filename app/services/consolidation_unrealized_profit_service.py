from datetime import date
from decimal import Decimal
import json
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import create_consolidation_adjustment


class ConsolidationUnrealizedProfitError(RuntimeError):
    pass


RULE_CODE = "UP_INV"
RULE_CODE_DT = "UP_INV_DT"
SOURCE = "generated"
TAG = "unrealized_profit_inventory"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationUnrealizedProfitError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationUnrealizedProfitError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationUnrealizedProfitError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationUnrealizedProfitError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationUnrealizedProfitError(f"{field}_invalid") from err


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


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _set_id(group_id: int, start_date: date, end_date: date) -> str:
    return f"UPINV-{group_id}-{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"


def _period(end_date: date) -> str:
    return end_date.strftime("%Y-%m")


def _line(
    set_id: str,
    operator_id: int,
    amount: Decimal,
    note: str,
    is_debit: bool,
    *,
    rule_code: str,
    subject_code: str,
) -> Dict[str, object]:
    debit = amount if is_debit else Decimal("0")
    credit = amount if not is_debit else Decimal("0")
    return {
        "subject_code": subject_code,
        "debit": str(debit),
        "credit": str(credit),
        "note": note,
        "set_id": set_id,
        "source": SOURCE,
        "rule": rule_code,
        "evidence_ref": set_id,
        "operator_id": str(operator_id),
    }


def _normalize_tax_rate(value: object) -> Decimal:
    rate = _to_decimal(value)
    if rate <= 0:
        return Decimal("0.25")
    if rate > 1 and rate <= 100:
        rate = rate / Decimal("100")
    if rate > 1:
        return Decimal("0.25")
    return rate.quantize(Decimal("0.0001"))


def _load_tax_rate(conn, group_id: int) -> Decimal:
    cols = _table_columns(conn, "consolidation_parameters")
    if "virtual_subject_id" not in cols:
        return Decimal("0.25")
    if "tax_rate" not in cols:
        return Decimal("0.25")
    status_filter = " AND status='active'" if "status" in cols else ""
    row = conn.execute(
        text(
            f"""
            SELECT tax_rate
            FROM consolidation_parameters
            WHERE virtual_subject_id=:group_id
            {status_filter}
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"group_id": int(group_id)},
    ).fetchone()
    if not row:
        return Decimal("0.25")
    return _normalize_tax_rate(getattr(row, "tax_rate", None))


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _upsert_inventory_adjustment_set(
    *,
    group_id: int,
    period: str,
    set_id: str,
    operator_id: int,
    lines: List[Dict[str, object]],
    original_unrealized_profit: Decimal,
    original_tax_amount: Decimal,
    tax_rate_snapshot: Decimal,
    period_start: date,
    period_end: date,
) -> Dict[str, object]:
    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        row = conn.execute(
            text(
                """
                SELECT id, status, lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND source='generated'
                  AND batch_id=:batch_id
                  AND evidence_ref=:evidence_ref
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"group_id": group_id, "period": period, "batch_id": set_id, "evidence_ref": set_id},
        ).fetchone()

        if not row:
            created = create_consolidation_adjustment(
                {
                    "consolidation_group_id": group_id,
                    "period": period,
                    "operator_id": operator_id,
                    "status": "draft",
                    "source": "generated",
                    "tag": TAG,
                    "rule_code": RULE_CODE,
                    "evidence_ref": set_id,
                    "batch_id": set_id,
                    "original_unrealized_profit": str(original_unrealized_profit),
                    "remaining_unrealized_profit": str(original_unrealized_profit),
                    "original_amount": str(original_unrealized_profit),
                    "remaining_amount": str(original_unrealized_profit),
                    "original_tax_amount": str(original_tax_amount),
                    "remaining_tax_amount": str(original_tax_amount),
                    "tax_rate_snapshot": str(tax_rate_snapshot),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "origin_period_start": period_start.isoformat(),
                    "origin_period_end": period_end.isoformat(),
                    "lines": lines,
                }
            )
            return {"reused_existing_set": False, "item": created}

        status = str(row.status or "").strip().lower()
        if status == "reviewed":
            raise ConsolidationUnrealizedProfitError("adjustment_set_reviewed_blocked")
        if status == "locked":
            raise ConsolidationUnrealizedProfitError("adjustment_set_locked_blocked")
        if status != "draft":
            raise ConsolidationUnrealizedProfitError("adjustment_set_status_invalid")

        existing_lines = _parse_lines_json(row.lines_json)
        retained_lines: List[Dict[str, object]] = []
        for line in existing_lines:
            if not isinstance(line, dict):
                continue
            if str(line.get("source") or "") == "generated" and str(line.get("rule") or "") in {RULE_CODE, RULE_CODE_DT}:
                continue
            retained_lines.append(line)
        merged = retained_lines + lines

        assignments = [
            "lines_json=:lines_json",
            "operator_id=:operator_id",
            "status='draft'",
            "rule_code=:rule_code",
        ]
        params = {
            "lines_json": json.dumps(merged, ensure_ascii=False),
            "operator_id": operator_id,
            "id": int(row.id),
            "rule_code": RULE_CODE,
            "original_unrealized_profit": str(original_unrealized_profit),
            "remaining_unrealized_profit": str(original_unrealized_profit),
            "original_amount": str(original_unrealized_profit),
            "remaining_amount": str(original_unrealized_profit),
            "original_tax_amount": str(original_tax_amount),
            "remaining_tax_amount": str(original_tax_amount),
            "tax_rate_snapshot": str(tax_rate_snapshot),
            "period_start": period_start,
            "period_end": period_end,
            "origin_period_start": period_start,
            "origin_period_end": period_end,
        }
        for col in [
            "original_unrealized_profit",
            "remaining_unrealized_profit",
            "original_amount",
            "remaining_amount",
            "original_tax_amount",
            "remaining_tax_amount",
            "tax_rate_snapshot",
            "period_start",
            "period_end",
            "origin_period_start",
            "origin_period_end",
        ]:
            if col in cols:
                assignments.append(f"{col}=:{col}")
        conn.execute(
            text(
                f"""
                UPDATE consolidation_adjustments
                SET {', '.join(assignments)}
                WHERE id=:id
                """
            ),
            params,
        )
        return {
            "reused_existing_set": True,
            "item": {
                "id": int(row.id),
                "group_id": group_id,
                "period": period,
                "status": "draft",
                "operator_id": operator_id,
                "source": "generated",
                "tag": TAG,
                "rule_code": RULE_CODE,
                "evidence_ref": set_id,
                "batch_id": set_id,
                "original_unrealized_profit": str(original_unrealized_profit),
                "remaining_unrealized_profit": str(original_unrealized_profit),
                "original_amount": str(original_unrealized_profit),
                "remaining_amount": str(original_unrealized_profit),
                "original_tax_amount": str(original_tax_amount),
                "remaining_tax_amount": str(original_tax_amount),
                "tax_rate_snapshot": str(tax_rate_snapshot),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "origin_period_start": period_start.isoformat(),
                "origin_period_end": period_end.isoformat(),
                "lines": merged,
            },
        }


def generate_inventory_unrealized_profit(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("group_id") or payload.get("consolidation_group_id"), "group_id")
    start_date = _parse_date(payload.get("start_date"), "start_date")
    end_date = _parse_date(payload.get("end_date"), "end_date")
    if end_date < start_date:
        raise ConsolidationUnrealizedProfitError("date_range_invalid")
    operator = _parse_positive_int(operator_id, "operator_id")

    provider = get_connection_provider()
    with provider.connect() as conn:
        cols = _table_columns(conn, "consolidation_ic_inventory_txn")
        required = {
            "group_id",
            "seller_book_id",
            "buyer_book_id",
            "doc_no",
            "txn_date",
            "item_code",
            "qty",
            "sales_amount",
            "cost_amount",
            "ending_inventory_qty",
        }
        if not required.issubset(cols):
            raise ConsolidationUnrealizedProfitError("inventory_txn_model_not_ready")
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationUnrealizedProfitError("consolidation_group_not_found")
        tax_rate = _load_tax_rate(conn, group_id)
        rows = conn.execute(
            text(
                """
                SELECT id, seller_book_id, buyer_book_id, doc_no, txn_date, item_code,
                       qty, sales_amount, cost_amount, ending_inventory_qty
                FROM consolidation_ic_inventory_txn
                WHERE group_id=:group_id
                  AND txn_date>=:start_date
                  AND txn_date<=:end_date
                ORDER BY id ASC
                """
            ),
            {"group_id": group_id, "start_date": start_date, "end_date": end_date},
        ).fetchall()

    set_id = _set_id(group_id, start_date, end_date)
    preview_lines: List[Dict[str, object]] = []
    dt_lines: List[Dict[str, object]] = []
    total = Decimal("0")

    for row in rows:
        qty = _to_decimal(row.qty)
        sales_amount = _to_decimal(row.sales_amount)
        cost_amount = _to_decimal(row.cost_amount)
        ending_qty = _to_decimal(row.ending_inventory_qty)
        if qty == 0:
            continue
        ratio = ending_qty / qty
        unrealized_profit = (sales_amount - cost_amount) * ratio
        unrealized_profit = unrealized_profit.quantize(Decimal("0.01"))
        if unrealized_profit == 0:
            continue
        total += unrealized_profit
        base_note = f"doc={row.doc_no} item={row.item_code} seller={int(row.seller_book_id)} buyer={int(row.buyer_book_id)}"
        if unrealized_profit > 0:
            preview_lines.append(
                _line(
                    set_id,
                    operator,
                    unrealized_profit,
                    f"存货未实现利润抵销 {base_note}",
                    True,
                    rule_code=RULE_CODE,
                    subject_code="UP_INV_ELIM",
                )
            )
            preview_lines.append(
                _line(
                    set_id,
                    operator,
                    unrealized_profit,
                    f"存货未实现利润抵销 {base_note}",
                    False,
                    rule_code=RULE_CODE,
                    subject_code="UP_INV_ELIM",
                )
            )
        else:
            amt = abs(unrealized_profit)
            preview_lines.append(
                _line(
                    set_id,
                    operator,
                    amt,
                    f"存货未实现利润冲回 {base_note}",
                    False,
                    rule_code=RULE_CODE,
                    subject_code="UP_INV_ELIM",
                )
            )
            preview_lines.append(
                _line(
                    set_id,
                    operator,
                    amt,
                    f"存货未实现利润冲回 {base_note}",
                    True,
                    rule_code=RULE_CODE,
                    subject_code="UP_INV_ELIM",
                )
            )

    dt_total = (total * tax_rate).quantize(Decimal("0.01"))
    if dt_total != 0:
        if dt_total > 0:
            dt_lines.append(
                _line(
                    set_id,
                    operator,
                    dt_total,
                    "未实现利润递延所得税资产确认",
                    True,
                    rule_code=RULE_CODE_DT,
                    subject_code="UP_INV_DT_ASSET",
                )
            )
            dt_lines.append(
                _line(
                    set_id,
                    operator,
                    dt_total,
                    "未实现利润递延所得税费用调整",
                    False,
                    rule_code=RULE_CODE_DT,
                    subject_code="UP_INV_DT_EXPENSE",
                )
            )
        else:
            amt = abs(dt_total)
            dt_lines.append(
                _line(
                    set_id,
                    operator,
                    amt,
                    "未实现利润递延所得税冲回",
                    False,
                    rule_code=RULE_CODE_DT,
                    subject_code="UP_INV_DT_ASSET",
                )
            )
            dt_lines.append(
                _line(
                    set_id,
                    operator,
                    amt,
                    "未实现利润递延所得税冲回",
                    True,
                    rule_code=RULE_CODE_DT,
                    subject_code="UP_INV_DT_EXPENSE",
                )
            )

    upserted = _upsert_inventory_adjustment_set(
        group_id=group_id,
        period=_period(end_date),
        set_id=set_id,
        operator_id=operator,
        lines=(preview_lines + dt_lines),
        original_unrealized_profit=total,
        original_tax_amount=dt_total,
        tax_rate_snapshot=tax_rate,
        period_start=start_date,
        period_end=end_date,
    )
    item = dict(upserted.get("item") or {})
    lines = list(item.get("lines") or (preview_lines + dt_lines))
    return {
        "group_id": group_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "rule_code": RULE_CODE,
        "total_unrealized_profit": float(total),
        "tax_rate": float(tax_rate),
        "dt_amount": float(dt_total),
        "counts": {
            "txns": len(rows),
            "matched_txns": int(len(preview_lines) / 2),
            "dt_lines": len(dt_lines),
            "lines": len(lines),
        },
        "preview_lines": lines,
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
    }
