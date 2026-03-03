import json
from datetime import date
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import regenerate_generated_adjustment_set


class ConsolidationMergeJournalError(RuntimeError):
    pass


RULE_CODE = "MERGE_JOURNAL_POST_BALANCE"
SOURCE = "generated"
TAG = "merge_journal_post_balance"


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationMergeJournalError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationMergeJournalError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationMergeJournalError(f"{field}_invalid")
    return parsed


def _parse_period(value: object, field: str) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationMergeJournalError(f"{field}_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationMergeJournalError(f"{field}_invalid")
    month = int(mm)
    if month < 1 or month > 12:
        raise ConsolidationMergeJournalError(f"{field}_invalid")
    return f"{int(yy):04d}-{month:02d}"


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationMergeJournalError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationMergeJournalError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:
        return Decimal("0")


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


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _set_id(group_id: int, period: str) -> str:
    return f"MJB-{group_id}-{period.replace('-', '')}"


def _line(*, set_id: str, operator_id: int, subject_code: str, debit: Decimal, credit: Decimal, note: str) -> Dict[str, object]:
    return {
        "subject_code": subject_code,
        "debit": str(debit.quantize(Decimal("0.01"))),
        "credit": str(credit.quantize(Decimal("0.01"))),
        "note": note,
        "set_id": set_id,
        "source": SOURCE,
        "rule": RULE_CODE,
        "evidence_ref": set_id,
        "operator_id": str(operator_id),
    }


def generate_merge_journal_and_post_merge_balance(payload: Dict[str, object], operator_id: object = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period_raw = str(payload.get("period") or "").strip()
    if period_raw:
        period = _parse_period(period_raw, "period")
    else:
        period = _as_of_to_period(payload.get("as_of"))
    operator = _parse_positive_int(operator_id, "operator_id")

    provider = get_connection_provider()
    with provider.connect() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        required_cols = {"lines_json", "status", "source", "rule_code", "batch_id"}
        if not required_cols.issubset(cols):
            raise ConsolidationMergeJournalError("adjustment_model_not_ready")
        exists = conn.execute(text("SELECT id FROM consolidation_groups WHERE id=:gid LIMIT 1"), {"gid": group_id}).fetchone()
        if not exists:
            raise ConsolidationMergeJournalError("consolidation_group_not_found")
        rows = conn.execute(
            text(
                """
                SELECT id, batch_id, rule_code, status, lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND status IN ('draft', 'reviewed', 'locked', 'active')
                  AND COALESCE(source, '')='generated'
                  AND COALESCE(rule_code, '') <> ''
                  AND rule_code <> :rule_code
                ORDER BY id ASC
                """
            ),
            {"group_id": group_id, "period": period, "rule_code": RULE_CODE},
        ).fetchall()

    if not rows:
        raise ConsolidationMergeJournalError("no_generated_adjustments_for_merge")

    subject_totals: Dict[str, Dict[str, Decimal]] = {}
    source_set_count = 0
    journal_line_count = 0
    for row in rows:
        source_set_count += 1
        lines = _parse_lines_json(row.lines_json)
        for line in lines:
            if not isinstance(line, dict):
                continue
            subject_code = str(line.get("subject_code") or "").strip()
            if not subject_code:
                continue
            debit = _to_decimal(line.get("debit"))
            credit = _to_decimal(line.get("credit"))
            bucket = subject_totals.setdefault(subject_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket["debit"] += debit
            bucket["credit"] += credit
            journal_line_count += 1

    if not subject_totals:
        raise ConsolidationMergeJournalError("no_valid_merge_journal_lines")

    set_id = _set_id(group_id, period)
    generated_lines: List[Dict[str, object]] = []
    post_merge_balance: List[Dict[str, object]] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for subject_code in sorted(subject_totals.keys()):
        debit = subject_totals[subject_code]["debit"].quantize(Decimal("0.01"))
        credit = subject_totals[subject_code]["credit"].quantize(Decimal("0.01"))
        if debit == 0 and credit == 0:
            continue
        generated_lines.append(
            _line(
                set_id=set_id,
                operator_id=operator,
                subject_code=subject_code,
                debit=debit,
                credit=credit,
                note="合并作业单汇总行",
            )
        )
        net = (debit - credit).quantize(Decimal("0.01"))
        post_merge_balance.append(
            {
                "subject_code": subject_code,
                "total_debit": float(debit),
                "total_credit": float(credit),
                "net_debit": float(net if net > 0 else Decimal("0")),
                "net_credit": float(abs(net) if net < 0 else Decimal("0")),
            }
        )
        total_debit += debit
        total_credit += credit

    upserted = regenerate_generated_adjustment_set(
        group_id=group_id,
        period=period,
        operator_id=operator,
        set_id=set_id,
        rule_code=RULE_CODE,
        evidence_ref=set_id,
        tag=TAG,
        generated_lines=generated_lines,
    )
    item = dict(upserted.get("item") or {})
    actual_lines = list(item.get("lines") or generated_lines)
    return {
        "group_id": group_id,
        "period": period,
        "adjustment_set_id": set_id,
        "set_id": set_id,
        "rule_code": RULE_CODE,
        "source_set_count": source_set_count,
        "merged_journal_line_count": journal_line_count,
        "line_count": len(actual_lines),
        "total_debit": float(total_debit.quantize(Decimal("0.01"))),
        "total_credit": float(total_credit.quantize(Decimal("0.01"))),
        "post_merge_balance": post_merge_balance,
        "preview_lines": actual_lines,
        "reused_existing_set": bool(upserted.get("reused_existing_set")),
    }
