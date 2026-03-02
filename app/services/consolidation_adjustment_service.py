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
                "set_id": str(item.get("set_id") or "").strip(),
                "source": str(item.get("source") or "").strip(),
                "rule": str(item.get("rule") or "").strip(),
                "evidence_ref": str(item.get("evidence_ref") or "").strip(),
                "operator_id": str(item.get("operator_id") or "").strip(),
            }
        )
    return out


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


def create_consolidation_adjustment(payload: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(payload.get("consolidation_group_id") or payload.get("group_id"), "consolidation_group_id")
    period = _parse_period(payload.get("period"))
    operator_id = _parse_positive_int(payload.get("operator_id"), "operator_id")
    lines = _normalize_lines(payload.get("lines"))

    status = str(payload.get("status") or "active").strip().lower() or "active"
    if status not in ("active", "draft", "disabled"):
        raise ConsolidationAdjustmentError("status_invalid")
    source = str(payload.get("source") or "").strip() or None
    tag = str(payload.get("tag") or "").strip() or None
    rule_code = str(payload.get("rule_code") or "").strip() or None
    evidence_ref = str(payload.get("evidence_ref") or "").strip() or None
    batch_id = str(payload.get("batch_id") or payload.get("set_id") or "").strip() or None

    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        row = conn.execute(
            text("SELECT id FROM consolidation_groups WHERE id=:group_id LIMIT 1"),
            {"group_id": group_id},
        ).fetchone()
        if not row:
            raise ConsolidationAdjustmentError("consolidation_group_not_found")
        insert_cols = ["group_id", "period", "status", "operator_id", "lines_json"]
        insert_vals = [":group_id", ":period", ":status", ":operator_id", ":lines_json"]
        params = {
            "group_id": group_id,
            "period": period,
            "status": status,
            "operator_id": operator_id,
            "lines_json": json.dumps(lines, ensure_ascii=False),
            "source": source,
            "tag": tag,
            "rule_code": rule_code,
            "evidence_ref": evidence_ref,
            "batch_id": batch_id,
        }
        if "source" in cols:
            insert_cols.append("source")
            insert_vals.append(":source")
        if "tag" in cols:
            insert_cols.append("tag")
            insert_vals.append(":tag")
        if "rule_code" in cols:
            insert_cols.append("rule_code")
            insert_vals.append(":rule_code")
        if "evidence_ref" in cols:
            insert_cols.append("evidence_ref")
            insert_vals.append(":evidence_ref")
        if "batch_id" in cols:
            insert_cols.append("batch_id")
            insert_vals.append(":batch_id")
        result = conn.execute(
            text(
                f"""
                INSERT INTO consolidation_adjustments
                    ({', '.join(insert_cols)})
                VALUES
                    ({', '.join(insert_vals)})
                """
            ),
            params,
        )
        adjustment_id = int(result.lastrowid)
    return {
        "id": adjustment_id,
        "group_id": group_id,
        "period": period,
        "status": status,
        "operator_id": operator_id,
        "source": source or "",
        "tag": tag or "",
        "rule_code": rule_code or "",
        "evidence_ref": evidence_ref or "",
        "batch_id": batch_id or "",
        "lines": lines,
    }


def list_consolidation_adjustments(params: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(params.get("consolidation_group_id") or params.get("group_id"), "consolidation_group_id")
    period = _parse_period(params.get("period"))
    provider = get_connection_provider()
    with provider.connect() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        source_col = "source" if "source" in cols else "'' AS source"
        tag_col = "tag" if "tag" in cols else "'' AS tag"
        rule_col = "rule_code" if "rule_code" in cols else "'' AS rule_code"
        evidence_col = "evidence_ref" if "evidence_ref" in cols else "'' AS evidence_ref"
        batch_col = "batch_id" if "batch_id" in cols else "'' AS batch_id"
        rows = conn.execute(
            text(
                f"""
                SELECT id, group_id, period, status, operator_id, lines_json, created_at,
                       {source_col}, {tag_col}, {rule_col}, {evidence_col}, {batch_col}
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
                "source": str(row.source or ""),
                "tag": str(row.tag or ""),
                "rule_code": str(row.rule_code or ""),
                "evidence_ref": str(row.evidence_ref or ""),
                "batch_id": str(row.batch_id or ""),
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
