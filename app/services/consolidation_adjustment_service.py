import json
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db_router import get_connection_provider


class ConsolidationAdjustmentError(RuntimeError):
    pass


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAdjustmentError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationAdjustmentError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationAdjustmentError(f"{field}_invalid")
    return parsed


def _parse_period(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ConsolidationAdjustmentError("period_invalid")
    yy = raw[:4]
    mm = raw[5:]
    if not yy.isdigit() or not mm.isdigit():
        raise ConsolidationAdjustmentError("period_invalid")
    month = int(mm)
    if month < 1 or month > 12:
        raise ConsolidationAdjustmentError("period_invalid")
    return f"{int(yy):04d}-{month:02d}"


def _to_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception as err:
        raise ConsolidationAdjustmentError(f"{field}_invalid") from err


def _normalize_lines(lines: object) -> List[Dict[str, str]]:
    if not isinstance(lines, list) or not lines:
        raise ConsolidationAdjustmentError("lines_required")
    out: List[Dict[str, str]] = []
    for idx, item in enumerate(lines):
        if not isinstance(item, dict):
            raise ConsolidationAdjustmentError(f"lines_{idx}_invalid")
        subject_code = str(item.get("subject_code") or "").strip()
        if not subject_code:
            raise ConsolidationAdjustmentError(f"lines_{idx}_subject_code_required")
        debit = _to_decimal(item.get("debit", "0"), f"lines_{idx}_debit")
        credit = _to_decimal(item.get("credit", "0"), f"lines_{idx}_credit")
        note = str(item.get("note") or "").strip()
        out.append(
            {
                "subject_code": subject_code,
                "debit": str(debit),
                "credit": str(credit),
                "note": note,
            }
        )
    return out


def create_consolidation_adjustment(payload: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period = _parse_period(payload.get("period"))
    operator_id = _parse_positive_int(payload.get("operator_id"), "operator_id")
    lines = _normalize_lines(payload.get("lines"))

    provider = get_connection_provider()
    with provider.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE id=:group_id LIMIT 1"),
            {"group_id": group_id},
        ).fetchone()
        if not row:
            raise ConsolidationAdjustmentError("consolidation_group_not_found")
        result = conn.execute(
            text(
                """
                INSERT INTO consolidation_adjustments
                    (group_id, period, status, operator_id, lines_json)
                VALUES
                    (:group_id, :period, 'active', :operator_id, :lines_json)
                """
            ),
            {
                "group_id": group_id,
                "period": period,
                "operator_id": operator_id,
                "lines_json": json.dumps(lines, ensure_ascii=False),
            },
        )
        adjustment_id = int(result.lastrowid)
    return {
        "id": adjustment_id,
        "group_id": group_id,
        "period": period,
        "status": "active",
        "operator_id": operator_id,
        "lines": lines,
    }


def list_consolidation_adjustments(params: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(params.get("consolidation_group_id") or params.get("group_id"), "consolidation_group_id")
    period = _parse_period(params.get("period"))
    provider = get_connection_provider()
    with provider.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, group_id, period, status, operator_id, lines_json, created_at
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                ORDER BY id DESC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
    items: List[Dict[str, object]] = []
    for row in rows:
        parsed_lines = []
        try:
            parsed_lines = json.loads(str(row.lines_json or "[]"))
            if not isinstance(parsed_lines, list):
                parsed_lines = []
        except Exception:
            parsed_lines = []
        items.append(
            {
                "id": int(row.id),
                "group_id": int(row.group_id),
                "period": str(row.period or ""),
                "status": str(row.status or ""),
                "operator_id": int(row.operator_id or 0),
                "created_at": str(row.created_at or ""),
                "lines": parsed_lines,
            }
        )
    return {"items": items, "group_id": group_id, "period": period}


def get_adjustment_totals_by_subject(conn, group_id: int, period: str) -> Dict[str, Dict[str, Decimal]]:
    rows = conn.execute(
        text(
            """
            SELECT lines_json
            FROM consolidation_adjustments
            WHERE group_id=:group_id
              AND period=:period
              AND status='active'
            ORDER BY id ASC
            """
        ),
        {"group_id": int(group_id), "period": _parse_period(period)},
    ).fetchall()
    totals: Dict[str, Dict[str, Decimal]] = {}
    for row in rows:
        try:
            lines = json.loads(str(row.lines_json or "[]"))
        except Exception:
            lines = []
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, dict):
                continue
            subject_code = str(line.get("subject_code") or "").strip()
            if not subject_code:
                continue
            debit = _to_decimal(line.get("debit", "0"), "debit")
            credit = _to_decimal(line.get("credit", "0"), "credit")
            bucket = totals.setdefault(subject_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            bucket["debit"] += debit
            bucket["credit"] += credit
    return totals
