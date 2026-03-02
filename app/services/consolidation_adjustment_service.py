import json
import calendar
from decimal import Decimal
from datetime import date
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


def _period_to_as_of_date(period: str) -> date:
    normalized = _parse_period(period)
    year = int(normalized[:4])
    month = int(normalized[5:])
    day = calendar.monthrange(year, month)[1]
    return date(year, month, day)


def _as_of_to_period(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationAdjustmentError("as_of_required")
    try:
        parsed = date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationAdjustmentError("as_of_invalid") from err
    return parsed.strftime("%Y-%m")


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


def _parse_lines_json(value: object) -> List[Dict[str, object]]:
    try:
        parsed = json.loads(str(value or "[]"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


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
        parsed_lines = _parse_lines_json(row.lines_json)
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


def list_consolidation_adjustment_sets(params: Dict[str, object]) -> Dict[str, object]:
    group_id = _parse_positive_int(params.get("consolidation_group_id") or params.get("group_id"), "consolidation_group_id")
    period_raw = str(params.get("period") or "").strip()
    as_of_raw = str(params.get("as_of") or "").strip()
    if period_raw:
        period = _parse_period(period_raw)
    elif as_of_raw:
        period = _as_of_to_period(as_of_raw)
    else:
        raise ConsolidationAdjustmentError("period_or_as_of_required")
    provider = get_connection_provider()
    with provider.connect() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        source_col = "source" if "source" in cols else "'' AS source"
        rule_col = "rule_code" if "rule_code" in cols else "'' AS rule_code"
        evidence_col = "evidence_ref" if "evidence_ref" in cols else "'' AS evidence_ref"
        tag_col = "tag" if "tag" in cols else "'' AS tag"
        batch_expr = "batch_id" if "batch_id" in cols else "CAST(id AS CHAR)"
        batch_col = f"{batch_expr} AS batch_id"
        rows = conn.execute(
            text(
                f"""
                SELECT id, group_id, period, status, operator_id, created_at,
                       {source_col}, {rule_col}, {evidence_col}, {tag_col}, {batch_col}, lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND COALESCE({batch_expr}, '') <> ''
                ORDER BY id DESC
                """
            ),
            {"group_id": group_id, "period": period},
        ).fetchall()
    set_map: Dict[str, Dict[str, object]] = {}
    for row in rows:
        set_id = str(row.batch_id or "").strip()
        if not set_id:
            continue
        parsed_lines = _parse_lines_json(row.lines_json)
        item = set_map.get(set_id)
        if not item:
            item = {
                "set_id": set_id,
                "group_id": int(row.group_id),
                "period": str(row.period or ""),
                "status": str(row.status or ""),
                "operator_id": int(row.operator_id or 0),
                "created_at": str(row.created_at or ""),
                "source": str(row.source or ""),
                "rule_code": str(row.rule_code or ""),
                "evidence_ref": str(row.evidence_ref or ""),
                "tag": str(row.tag or ""),
                "adjustment_ids": [],
                "line_count": 0,
            }
            set_map[set_id] = item
        item["adjustment_ids"].append(int(row.id))
        item["line_count"] = int(item["line_count"]) + len(parsed_lines)
    items = list(set_map.values())
    items.sort(key=lambda it: str(it.get("created_at") or ""), reverse=True)
    return {"items": items, "group_id": group_id, "period": period}


def transition_adjustment_set_status(set_id_value: object, action: str, operator_id: object) -> Dict[str, object]:
    set_id = str(set_id_value or "").strip()
    if not set_id:
        raise ConsolidationAdjustmentError("adjustment_set_id_required")
    operator = _parse_positive_int(operator_id, "operator_id")
    act = str(action or "").strip().lower()
    if act not in ("review", "lock", "reopen"):
        raise ConsolidationAdjustmentError("action_invalid")
    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        if "batch_id" not in cols:
            raise ConsolidationAdjustmentError("adjustment_set_not_supported")
        row = conn.execute(
            text(
                """
                SELECT id, group_id, period, status
                FROM consolidation_adjustments
                WHERE batch_id=:set_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"set_id": set_id},
        ).fetchone()
        if not row:
            raise ConsolidationAdjustmentError("adjustment_set_not_found")
        current = str(row.status or "").strip().lower()
        if act == "review":
            if current != "draft":
                raise ConsolidationAdjustmentError("adjustment_set_transition_invalid")
            target = "reviewed"
        elif act == "lock":
            if current != "reviewed":
                raise ConsolidationAdjustmentError("adjustment_set_transition_invalid")
            target = "locked"
        else:
            if current not in ("reviewed", "locked"):
                raise ConsolidationAdjustmentError("adjustment_set_transition_invalid")
            target = "draft"
        conn.execute(
            text(
                """
                UPDATE consolidation_adjustments
                SET status=:status, operator_id=:operator_id
                WHERE batch_id=:set_id
                """
            ),
            {"status": target, "operator_id": operator, "set_id": set_id},
        )
    return {
        "set_id": set_id,
        "group_id": int(row.group_id),
        "period": str(row.period or ""),
        "from_status": current,
        "status": target,
        "operator_id": operator,
    }


def get_adjustment_set_meta(set_id_value: object) -> Dict[str, object]:
    set_id = str(set_id_value or "").strip()
    if not set_id:
        raise ConsolidationAdjustmentError("adjustment_set_id_required")
    provider = get_connection_provider()
    with provider.connect() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        if "batch_id" not in cols:
            raise ConsolidationAdjustmentError("adjustment_set_not_supported")
        row = conn.execute(
            text(
                """
                SELECT id, group_id, period, status, source, tag, rule_code, evidence_ref, batch_id
                FROM consolidation_adjustments
                WHERE batch_id=:set_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"set_id": set_id},
        ).fetchone()
        if not row:
            raise ConsolidationAdjustmentError("adjustment_set_not_found")
    return {
        "id": int(row.id),
        "set_id": str(row.batch_id or ""),
        "group_id": int(row.group_id),
        "period": str(row.period or ""),
        "status": str(row.status or "").strip().lower(),
        "source": str(row.source or ""),
        "tag": str(row.tag or ""),
        "rule_code": str(row.rule_code or ""),
        "evidence_ref": str(row.evidence_ref or ""),
    }


def regenerate_generated_adjustment_set(
    *,
    group_id: int,
    period: str,
    operator_id: int,
    set_id: str,
    rule_code: str,
    evidence_ref: str,
    tag: str,
    generated_lines: List[Dict[str, object]],
) -> Dict[str, object]:
    normalized_group_id = _parse_positive_int(group_id, "consolidation_group_id")
    normalized_period = _parse_period(period)
    normalized_operator = _parse_positive_int(operator_id, "operator_id")
    normalized_set_id = str(set_id or "").strip()
    normalized_rule = str(rule_code or "").strip()
    normalized_evidence = str(evidence_ref or "").strip()
    normalized_tag = str(tag or "").strip()
    if not normalized_set_id:
        raise ConsolidationAdjustmentError("adjustment_set_id_required")
    if not normalized_rule:
        raise ConsolidationAdjustmentError("rule_code_required")
    if not normalized_evidence:
        raise ConsolidationAdjustmentError("evidence_ref_required")

    normalized_generated_lines = _normalize_lines(generated_lines)
    provider = get_connection_provider()
    with provider.begin() as conn:
        cols = _table_columns(conn, "consolidation_adjustments")
        if not {"source", "rule_code", "evidence_ref", "batch_id", "tag"}.issubset(cols):
            raise ConsolidationAdjustmentError("generated_adjustment_model_not_ready")
        row = conn.execute(
            text(
                """
                SELECT id, status, lines_json
                FROM consolidation_adjustments
                WHERE group_id=:group_id
                  AND period=:period
                  AND source='generated'
                  AND rule_code=:rule_code
                  AND evidence_ref=:evidence_ref
                  AND batch_id=:batch_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {
                "group_id": normalized_group_id,
                "period": normalized_period,
                "rule_code": normalized_rule,
                "evidence_ref": normalized_evidence,
                "batch_id": normalized_set_id,
            },
        ).fetchone()
        if not row:
            insert_result = conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments
                        (group_id, period, status, operator_id, lines_json, source, tag, rule_code, evidence_ref, batch_id)
                    VALUES
                        (:group_id, :period, 'draft', :operator_id, :lines_json, 'generated', :tag, :rule_code, :evidence_ref, :batch_id)
                    """
                ),
                {
                    "group_id": normalized_group_id,
                    "period": normalized_period,
                    "operator_id": normalized_operator,
                    "lines_json": json.dumps(normalized_generated_lines, ensure_ascii=False),
                    "tag": normalized_tag,
                    "rule_code": normalized_rule,
                    "evidence_ref": normalized_evidence,
                    "batch_id": normalized_set_id,
                },
            )
            created_id = int(insert_result.lastrowid)
            return {
                "created": True,
                "reused_existing_set": False,
                "item": {
                    "id": created_id,
                    "group_id": normalized_group_id,
                    "period": normalized_period,
                    "status": "draft",
                    "operator_id": normalized_operator,
                    "source": "generated",
                    "tag": normalized_tag,
                    "rule_code": normalized_rule,
                    "evidence_ref": normalized_evidence,
                    "batch_id": normalized_set_id,
                    "lines": normalized_generated_lines,
                },
            }

        current_status = str(row.status or "").strip().lower()
        if current_status == "reviewed":
            raise ConsolidationAdjustmentError("adjustment_set_reviewed_blocked")
        if current_status == "locked":
            raise ConsolidationAdjustmentError("adjustment_set_locked_blocked")
        if current_status != "draft":
            raise ConsolidationAdjustmentError("adjustment_set_status_invalid")

        existing_lines = _parse_lines_json(row.lines_json)
        retained_lines: List[Dict[str, object]] = []
        for line in existing_lines:
            if not isinstance(line, dict):
                continue
            source = str(line.get("source") or "").strip()
            line_rule = str(line.get("rule") or "").strip()
            if source == "generated" and line_rule == normalized_rule:
                continue
            retained_lines.append(line)
        merged_lines = retained_lines + normalized_generated_lines
        conn.execute(
            text(
                """
                UPDATE consolidation_adjustments
                SET lines_json=:lines_json, operator_id=:operator_id, status='draft'
                WHERE id=:id
                """
            ),
            {"lines_json": json.dumps(merged_lines, ensure_ascii=False), "operator_id": normalized_operator, "id": int(row.id)},
        )
        return {
            "created": False,
            "reused_existing_set": True,
            "item": {
                "id": int(row.id),
                "group_id": normalized_group_id,
                "period": normalized_period,
                "status": "draft",
                "operator_id": normalized_operator,
                "source": "generated",
                "tag": normalized_tag,
                "rule_code": normalized_rule,
                "evidence_ref": normalized_evidence,
                "batch_id": normalized_set_id,
                "lines": merged_lines,
            },
        }


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
