import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import create_consolidation_adjustment


class ConsolidationUnrealizedProfitReversalError(RuntimeError):
    pass


RULE_CODE = "UP_INV_REVERSAL"
RULE_CODE_DT = "UP_INV_DTL_REVERSAL"
SOURCE = "generated"
TAG = "unrealized_profit_inventory_reversal"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationUnrealizedProfitReversalError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationUnrealizedProfitReversalError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationUnrealizedProfitReversalError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationUnrealizedProfitReversalError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationUnrealizedProfitReversalError(f"{field}_invalid") from err


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _set_id(group_id: int, start_date: date, end_date: date) -> str:
    return f"UPINV-REV-{group_id}-{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"


def _period(end_date: date) -> str:
    return end_date.strftime("%Y-%m")


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


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


def _find_existing_set(conn, group_id: int, period: str, set_id: str):
    return conn.execute(
        text(
            """
            SELECT id, status, lines_json
            FROM consolidation_adjustments
            WHERE group_id=:group_id
              AND period=:period
              AND source='generated'
              AND rule_code=:rule_code
              AND batch_id=:batch_id
              AND evidence_ref=:evidence_ref
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {
            "group_id": group_id,
            "period": period,
            "rule_code": RULE_CODE,
            "batch_id": set_id,
            "evidence_ref": set_id,
        },
    ).fetchone()


def _load_realized_amount(conn, group_id: int, start_date: date, end_date: date) -> Decimal:
    rows = conn.execute(
        text(
            """
            SELECT qty, sales_amount, cost_amount, ending_inventory_qty
            FROM consolidation_ic_inventory_txn
            WHERE group_id=:group_id
              AND txn_date>=:start_date
              AND txn_date<=:end_date
            """
        ),
        {"group_id": group_id, "start_date": start_date, "end_date": end_date},
    ).fetchall()
    total = Decimal("0")
    for row in rows:
        qty = _to_decimal(row.qty)
        if qty == 0:
            continue
        margin = _to_decimal(row.sales_amount) - _to_decimal(row.cost_amount)
        realized_ratio = Decimal("1") - (_to_decimal(row.ending_inventory_qty) / qty)
        if realized_ratio < 0:
            realized_ratio = Decimal("0")
        if realized_ratio > 1:
            realized_ratio = Decimal("1")
        total += (margin * realized_ratio)
    return total.quantize(Decimal("0.01"))


def _load_remaining_rows(conn, group_id: int, start_date: date):
    cols = _table_columns(conn, "consolidation_adjustments")
    rem_amt_col = "remaining_amount" if "remaining_amount" in cols else "remaining_unrealized_profit AS remaining_amount"
    rem_tax_col = "remaining_tax_amount" if "remaining_tax_amount" in cols else "NULL AS remaining_tax_amount"
    rate_col = "tax_rate_snapshot" if "tax_rate_snapshot" in cols else "NULL AS tax_rate_snapshot"
    period_end_col = "period_end" if "period_end" in cols else "NULL AS period_end"
    return conn.execute(
        text(
            f"""
            SELECT id,
                   remaining_unrealized_profit,
                   {rem_amt_col},
                   {rem_tax_col},
                   {rate_col},
                   {period_end_col}
            FROM consolidation_adjustments
            WHERE group_id=:group_id
              AND source='generated'
              AND rule_code='UP_INV'
              AND COALESCE({rem_amt_col.split(' AS ')[0]}, remaining_unrealized_profit, 0) > 0
              AND ({period_end_col.split(' AS ')[0]} IS NULL OR {period_end_col.split(' AS ')[0]}<:start_date)
            ORDER BY period_end ASC, id ASC
            """
        ),
        {"group_id": group_id, "start_date": start_date},
    ).fetchall()


def _build_lines(set_id: str, operator_id: int, amount: Decimal, dt_amount: Decimal) -> List[Dict[str, object]]:
    lines = [
        {
            "subject_code": "UP_INV_REVERSAL_PNL",
            "debit": "0",
            "credit": str(amount),
            "note": "存货未实现利润跨期转回",
            "set_id": set_id,
            "source": SOURCE,
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
        {
            "subject_code": "UP_INV_REVERSAL_BAL",
            "debit": str(amount),
            "credit": "0",
            "note": "存货未实现利润跨期转回",
            "set_id": set_id,
            "source": SOURCE,
            "rule": RULE_CODE,
            "evidence_ref": set_id,
            "operator_id": str(operator_id),
        },
    ]
    if dt_amount > 0:
        lines.extend(
            [
                {
                    "subject_code": "UP_INV_DTL_REV_EXPENSE",
                    "debit": str(dt_amount),
                    "credit": "0",
                    "note": "存货未实现利润递延税转回",
                    "set_id": set_id,
                    "source": SOURCE,
                    "rule": RULE_CODE_DT,
                    "evidence_ref": set_id,
                    "operator_id": str(operator_id),
                },
                {
                    "subject_code": "UP_INV_DTL_REV_ASSET",
                    "debit": "0",
                    "credit": str(dt_amount),
                    "note": "存货未实现利润递延税转回",
                    "set_id": set_id,
                    "source": SOURCE,
                    "rule": RULE_CODE_DT,
                    "evidence_ref": set_id,
                    "operator_id": str(operator_id),
                },
            ]
        )
    return lines


def generate_inventory_unrealized_profit_reversal(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("group_id") or payload.get("consolidation_group_id"), "group_id")
    start_date = _parse_date(payload.get("start_date"), "start_date")
    end_date = _parse_date(payload.get("end_date"), "end_date")
    if end_date < start_date:
        raise ConsolidationUnrealizedProfitReversalError("date_range_invalid")
    operator = _parse_positive_int(operator_id, "operator_id")
    set_id = _set_id(group_id, start_date, end_date)
    period = _period(end_date)

    provider = get_connection_provider()
    with provider.begin() as conn:
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationUnrealizedProfitReversalError("consolidation_group_not_found")

        existing_set = _find_existing_set(conn, group_id, period, set_id)
        if existing_set:
            status = str(existing_set.status or "").strip().lower()
            if status == "reviewed":
                raise ConsolidationUnrealizedProfitReversalError("adjustment_set_reviewed_blocked")
            if status == "locked":
                raise ConsolidationUnrealizedProfitReversalError("adjustment_set_locked_blocked")
            if status != "draft":
                raise ConsolidationUnrealizedProfitReversalError("adjustment_set_status_invalid")
            parsed = _parse_lines_json(existing_set.lines_json)
            reversal_amount = sum(_to_decimal(x.get("credit")) for x in parsed if str(x.get("rule") or "") == RULE_CODE)
            dt_amount = sum(_to_decimal(x.get("debit")) for x in parsed if str(x.get("rule") or "") == RULE_CODE_DT)
            return {
                "group_id": group_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "adjustment_set_id": set_id,
                "set_id": set_id,
                "reversal_amount": float(reversal_amount),
                "dt_reversal_amount": float(dt_amount),
                "counts": {"lines": len(parsed)},
                "preview_lines": parsed,
                "reused_existing_set": True,
            }

        realized_amount = _load_realized_amount(conn, group_id, start_date, end_date)
        if realized_amount <= 0:
            raise ConsolidationUnrealizedProfitReversalError("no_realized_inventory_profit")

        remaining_rows = _load_remaining_rows(conn, group_id, start_date)
        remaining_total = sum(_to_decimal(r.remaining_amount if r.remaining_amount is not None else r.remaining_unrealized_profit) for r in remaining_rows)
        if remaining_total <= 0:
            raise ConsolidationUnrealizedProfitReversalError("no_remaining_unrealized_profit")

        reversal_amount = min(realized_amount, remaining_total).quantize(Decimal("0.01"))
        if reversal_amount <= 0:
            raise ConsolidationUnrealizedProfitReversalError("reversal_amount_invalid")

        dt_reversal_amount = Decimal("0")
        to_consume = reversal_amount
        adj_cols = _table_columns(conn, "consolidation_adjustments")
        for row in remaining_rows:
            if to_consume <= 0:
                break
            rem = _to_decimal(row.remaining_amount if row.remaining_amount is not None else row.remaining_unrealized_profit)
            if rem <= 0:
                continue
            delta = rem if rem <= to_consume else to_consume
            rate = _to_decimal(row.tax_rate_snapshot)
            if rate <= 0:
                rate = Decimal("0.25")
            rem_tax = _to_decimal(row.remaining_tax_amount)
            if rem_tax > 0 and rem > 0:
                delta_tax = (rem_tax * (delta / rem)).quantize(Decimal("0.01"))
                if delta_tax > rem_tax:
                    delta_tax = rem_tax
            else:
                delta_tax = (delta * rate).quantize(Decimal("0.01"))
            dt_reversal_amount += delta_tax
            new_rem = (rem - delta).quantize(Decimal("0.01"))
            new_rem_tax = (rem_tax - delta_tax).quantize(Decimal("0.01")) if rem_tax > 0 else Decimal("0.00")
            if new_rem_tax < 0:
                new_rem_tax = Decimal("0.00")
            assigns = ["remaining_unrealized_profit=:remaining_up"]
            if "remaining_amount" in adj_cols:
                assigns.append("remaining_amount=:remaining_up")
            if "remaining_tax_amount" in adj_cols:
                assigns.append("remaining_tax_amount=:remaining_tax")
            conn.execute(
                text(
                    f"""
                    UPDATE consolidation_adjustments
                    SET {', '.join(assigns)}
                    WHERE id=:id
                    """
                ),
                {"id": int(row.id), "remaining_up": str(new_rem), "remaining_tax": str(new_rem_tax)},
            )
            to_consume -= delta

        lines = _build_lines(set_id, operator, reversal_amount, dt_reversal_amount)
        tax_rate_snapshot = (dt_reversal_amount / reversal_amount).quantize(Decimal("0.0001")) if reversal_amount > 0 else Decimal("0")
        created = create_consolidation_adjustment(
            {
                "consolidation_group_id": group_id,
                "period": period,
                "operator_id": operator,
                "status": "draft",
                "source": SOURCE,
                "tag": TAG,
                "rule_code": RULE_CODE,
                "evidence_ref": set_id,
                "batch_id": set_id,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "origin_period_start": start_date.isoformat(),
                "origin_period_end": end_date.isoformat(),
                "original_unrealized_profit": str(reversal_amount),
                "remaining_unrealized_profit": "0",
                "original_amount": str(reversal_amount),
                "remaining_amount": "0",
                "original_tax_amount": str(dt_reversal_amount),
                "remaining_tax_amount": "0",
                "tax_rate_snapshot": str(tax_rate_snapshot),
                "lines": lines,
            }
        )

    return {
        "group_id": group_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "reversal_amount": float(reversal_amount),
        "dt_reversal_amount": float(dt_reversal_amount),
        "counts": {"lines": len(lines)},
        "preview_lines": list(created.get("lines") or lines),
        "reused_existing_set": False,
    }
