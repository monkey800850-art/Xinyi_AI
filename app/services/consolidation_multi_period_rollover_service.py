import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import ConsolidationAdjustmentError, regenerate_generated_adjustment_set


class ConsolidationMultiPeriodRolloverError(RuntimeError):
    pass


RULE_CODE = "ROLL_CARRY_FORWARD"
SOURCE = "generated"
TAG = "multi_period_rollover"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationMultiPeriodRolloverError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationMultiPeriodRolloverError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationMultiPeriodRolloverError(f"{field}_invalid")
    return parsed


def _parse_period(value: object, field: str) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationMultiPeriodRolloverError(f"{field}_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationMultiPeriodRolloverError(f"{field}_invalid")
    month = int(mm)
    if month < 1 or month > 12:
        raise ConsolidationMultiPeriodRolloverError(f"{field}_invalid")
    return f"{int(yy):04d}-{month:02d}"


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationMultiPeriodRolloverError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationMultiPeriodRolloverError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


def _prev_period(period: str) -> str:
    year = int(period[:4])
    month = int(period[5:])
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


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


def _period_start(period: str) -> str:
    return f"{period}-01"


def _period_end(period: str) -> str:
    yy = int(period[:4])
    mm = int(period[5:])
    if mm in (1, 3, 5, 7, 8, 10, 12):
        dd = 31
    elif mm in (4, 6, 9, 11):
        dd = 30
    else:
        leap = (yy % 4 == 0 and yy % 100 != 0) or (yy % 400 == 0)
        dd = 29 if leap else 28
    return f"{yy:04d}-{mm:02d}-{dd:02d}"


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _set_id(group_id: int, to_period: str, source_batch_id: str) -> str:
    digest = hashlib.md5(source_batch_id.encode("utf-8")).hexdigest()[:10]
    return f"ROLL-{group_id}-{to_period.replace('-', '')}-{digest}"


def _carry_line(
    *,
    src_line: Dict[str, object],
    set_id: str,
    operator_id: int,
    from_period: str,
    source_batch_id: str,
) -> Dict[str, object]:
    return {
        "subject_code": str(src_line.get("subject_code") or "").strip(),
        "debit": str(src_line.get("debit") or "0"),
        "credit": str(src_line.get("credit") or "0"),
        "note": f"期初滚动({from_period}/{source_batch_id}) {str(src_line.get('note') or '').strip()}".strip(),
        "set_id": set_id,
        "source": SOURCE,
        "rule": RULE_CODE,
        "evidence_ref": set_id,
        "operator_id": str(operator_id),
    }


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


def _update_tracking_fields(
    conn,
    *,
    adjustment_id: int,
    cols: set[str],
    to_period: str,
    from_period: str,
    source_batch_id: str,
    source_rule_code: str,
    source_row,
) -> None:
    sets: List[str] = []
    params: Dict[str, object] = {"id": int(adjustment_id)}
    if "note" in cols:
        sets.append("note=:note")
        params["note"] = f"carry_from={from_period};source_batch={source_batch_id};source_rule={source_rule_code}"
    if "period_start" in cols:
        sets.append("period_start=:period_start")
        params["period_start"] = _period_start(to_period)
    if "period_end" in cols:
        sets.append("period_end=:period_end")
        params["period_end"] = _period_end(to_period)
    if "origin_period_start" in cols:
        origin_start = str(getattr(source_row, "origin_period_start", "") or "").strip() or _period_start(from_period)
        sets.append("origin_period_start=:origin_period_start")
        params["origin_period_start"] = origin_start
    if "origin_period_end" in cols:
        origin_end = str(getattr(source_row, "origin_period_end", "") or "").strip() or _period_end(from_period)
        sets.append("origin_period_end=:origin_period_end")
        params["origin_period_end"] = origin_end

    # Carry forward cumulative elimination tracking on remaining balances if present.
    if "original_unrealized_profit" in cols and "remaining_unrealized_profit" in cols:
        rem_up = _to_decimal(getattr(source_row, "remaining_unrealized_profit", None))
        sets.append("original_unrealized_profit=:original_unrealized_profit")
        sets.append("remaining_unrealized_profit=:remaining_unrealized_profit")
        params["original_unrealized_profit"] = str(rem_up)
        params["remaining_unrealized_profit"] = str(rem_up)
    if "original_amount" in cols and "remaining_amount" in cols:
        rem_amt = _to_decimal(getattr(source_row, "remaining_amount", None))
        sets.append("original_amount=:original_amount")
        sets.append("remaining_amount=:remaining_amount")
        params["original_amount"] = str(rem_amt)
        params["remaining_amount"] = str(rem_amt)
    if "original_tax_amount" in cols and "remaining_tax_amount" in cols:
        rem_tax = _to_decimal(getattr(source_row, "remaining_tax_amount", None))
        sets.append("original_tax_amount=:original_tax_amount")
        sets.append("remaining_tax_amount=:remaining_tax_amount")
        params["original_tax_amount"] = str(rem_tax)
        params["remaining_tax_amount"] = str(rem_tax)
    if "tax_rate_snapshot" in cols:
        tax_rate = getattr(source_row, "tax_rate_snapshot", None)
        if tax_rate is not None:
            sets.append("tax_rate_snapshot=:tax_rate_snapshot")
            params["tax_rate_snapshot"] = str(tax_rate)

    if not sets:
        return
    conn.execute(
        text(
            f"""
            UPDATE consolidation_adjustments
            SET {', '.join(sets)}
            WHERE id=:id
            """
        ),
        params,
    )


def generate_multi_period_rollover(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    to_period_raw = str(payload.get("to_period") or "").strip()
    as_of_raw = str(payload.get("as_of") or "").strip()
    if to_period_raw:
        to_period = _parse_period(to_period_raw, "to_period")
    elif as_of_raw:
        to_period = _as_of_to_period(as_of_raw)
    else:
        raise ConsolidationMultiPeriodRolloverError("to_period_or_as_of_required")
    from_period = _parse_period(payload.get("from_period") or _prev_period(to_period), "from_period")
    operator = _parse_positive_int(operator_id, "operator_id")

    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        required_cols = {"source", "rule_code", "evidence_ref", "batch_id", "lines_json", "status"}
        if not required_cols.issubset(cols):
            raise ConsolidationMultiPeriodRolloverError("adjustment_model_not_ready")
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationMultiPeriodRolloverError("consolidation_group_not_found")

        query = """
            SELECT id, period, status, source, rule_code, batch_id, lines_json,
                   origin_period_start, origin_period_end,
                   remaining_unrealized_profit, remaining_amount, remaining_tax_amount, tax_rate_snapshot
            FROM consolidation_adjustments
            WHERE group_id=:group_id
              AND period=:from_period
              AND source='generated'
              AND COALESCE(batch_id, '') <> ''
              AND COALESCE(rule_code, '') <> ''
              AND rule_code <> :rollover_rule_code
              AND status IN ('draft', 'reviewed', 'locked', 'active')
            ORDER BY id ASC
        """
        source_rows = conn.execute(
            text(query),
            {"group_id": group_id, "from_period": from_period, "rollover_rule_code": RULE_CODE},
        ).fetchall()
        if not source_rows:
            raise ConsolidationMultiPeriodRolloverError("no_source_adjustments_for_rollover")

        created_count = 0
        reused_count = 0
        total_lines = 0
        items: List[Dict[str, object]] = []

        for row in source_rows:
            source_batch_id = str(row.batch_id or "").strip()
            if not source_batch_id:
                continue
            source_lines = _parse_lines_json(row.lines_json)
            carry_lines: List[Dict[str, object]] = []
            for line in source_lines:
                if not isinstance(line, dict):
                    continue
                subject_code = str(line.get("subject_code") or "").strip()
                if not subject_code:
                    continue
                carry_lines.append(
                    _carry_line(
                        src_line=line,
                        set_id="",
                        operator_id=operator,
                        from_period=from_period,
                        source_batch_id=source_batch_id,
                    )
                )
            if not carry_lines:
                continue

            set_id = _set_id(group_id, to_period, source_batch_id)
            for line in carry_lines:
                line["set_id"] = set_id
                line["evidence_ref"] = set_id

            upserted = regenerate_generated_adjustment_set(
                group_id=group_id,
                period=to_period,
                operator_id=operator,
                set_id=set_id,
                rule_code=RULE_CODE,
                evidence_ref=set_id,
                tag=TAG,
                generated_lines=carry_lines,
            )
            item = dict(upserted.get("item") or {})
            adj_id = int(item.get("id") or 0)
            if adj_id > 0:
                _update_tracking_fields(
                    conn,
                    adjustment_id=adj_id,
                    cols=cols,
                    to_period=to_period,
                    from_period=from_period,
                    source_batch_id=source_batch_id,
                    source_rule_code=str(row.rule_code or ""),
                    source_row=row,
                )
            if bool(upserted.get("created")):
                created_count += 1
            else:
                reused_count += 1
            lines = list(item.get("lines") or carry_lines)
            total_lines += len(lines)
            items.append(
                {
                    "set_id": set_id,
                    "source_batch_id": source_batch_id,
                    "source_rule_code": str(row.rule_code or ""),
                    "line_count": len(lines),
                    "reused_existing_set": bool(upserted.get("reused_existing_set")),
                }
            )

    if not items:
        raise ConsolidationMultiPeriodRolloverError("no_rollover_lines_generated")
    return {
        "group_id": group_id,
        "from_period": from_period,
        "to_period": to_period,
        "rule_code": RULE_CODE,
        "source_set_count": len(items),
        "created_set_count": created_count,
        "reused_set_count": reused_count,
        "line_count": total_lines,
        "items": items,
    }
