import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Set, Tuple

from sqlalchemy import bindparam, text

from app.db_router import get_connection_provider
from app.services.consolidation_adjustment_service import create_consolidation_adjustment


class ConsolidationOnboardingIcMatchError(RuntimeError):
    pass


def _parse_positive_int(value: object, field: str) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationOnboardingIcMatchError(f"{field}_required")
    try:
        parsed = int(raw)
    except Exception as err:
        raise ConsolidationOnboardingIcMatchError(f"{field}_invalid") from err
    if parsed <= 0:
        raise ConsolidationOnboardingIcMatchError(f"{field}_invalid")
    return parsed


def _parse_date(value: object, field: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ConsolidationOnboardingIcMatchError(f"{field}_required")
    try:
        return date.fromisoformat(raw)
    except Exception as err:
        raise ConsolidationOnboardingIcMatchError(f"{field}_invalid") from err


def _table_columns(conn, table_name: str) -> Set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {str(r[0] or "").strip().lower() for r in rows}


def _effective_member_book_ids(conn, group_id: int, as_of: date) -> List[int]:
    mcols = _table_columns(conn, "consolidation_group_members")
    book_col = "member_book_id" if "member_book_id" in mcols else ("book_id" if "book_id" in mcols else "")
    from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
    to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
    if not book_col:
        raise ConsolidationOnboardingIcMatchError("consolidation_member_model_not_ready")
    where_parts = ["group_id=:group_id", f"{book_col} IS NOT NULL"]
    if "status" in mcols:
        where_parts.append("status='active'")
    if "is_enabled" in mcols:
        where_parts.append("is_enabled=1")
    if from_col:
        where_parts.append(f"({from_col} IS NULL OR {from_col}<=:as_of)")
    if to_col:
        where_parts.append(f"({to_col} IS NULL OR {to_col}>=:as_of)")
    rows = conn.execute(
        text(
            f"""
            SELECT DISTINCT {book_col} AS book_id
            FROM consolidation_group_members
            WHERE {' AND '.join(where_parts)}
            """
        ),
        {"group_id": int(group_id), "as_of": as_of},
    ).fetchall()
    return sorted({int(r.book_id) for r in rows if r.book_id is not None and int(r.book_id) > 0})


def _load_ic_balances(conn, member_book_ids: List[int], as_of: date) -> List[Dict[str, object]]:
    if not member_book_ids:
        return []
    rows = conn.execute(
        text(
            """
            SELECT v.book_id, COALESCE(vl.aux_code, '') AS aux_code, COALESCE(vl.subject_code, '') AS subject_code,
                   SUM(COALESCE(vl.debit, 0) - COALESCE(vl.credit, 0)) AS net_amount
            FROM voucher_lines vl
            JOIN vouchers v ON v.id = vl.voucher_id
            WHERE v.book_id IN :book_ids
              AND v.status='posted'
              AND v.voucher_date<=:as_of
              AND COALESCE(vl.aux_code, '') <> ''
            GROUP BY v.book_id, aux_code, subject_code
            HAVING ABS(SUM(COALESCE(vl.debit, 0) - COALESCE(vl.credit, 0))) > 0.000001
            ORDER BY aux_code ASC, subject_code ASC, v.book_id ASC
            """
        ).bindparams(bindparam("book_ids", expanding=True)),
        {"book_ids": member_book_ids, "as_of": as_of},
    ).fetchall()
    out: List[Dict[str, object]] = []
    for r in rows:
        out.append(
            {
                "book_id": int(r.book_id),
                "aux_code": str(r.aux_code or ""),
                "subject_code": str(r.subject_code or ""),
                "net_amount": Decimal(str(r.net_amount or 0)),
            }
        )
    return out


def _match_by_key(balance_rows: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = {}
    for row in balance_rows:
        key = (str(row["aux_code"]), str(row["subject_code"]))
        grouped.setdefault(key, []).append(row)

    matched_pairs: List[Dict[str, object]] = []
    unmatched: List[Dict[str, object]] = []
    for (aux_code, subject_code), rows in grouped.items():
        pos = [{"book_id": int(r["book_id"]), "amount": Decimal(str(r["net_amount"]))} for r in rows if Decimal(str(r["net_amount"])) > 0]
        neg = [{"book_id": int(r["book_id"]), "amount": abs(Decimal(str(r["net_amount"])))} for r in rows if Decimal(str(r["net_amount"])) < 0]
        i = 0
        j = 0
        while i < len(pos) and j < len(neg):
            amount = min(pos[i]["amount"], neg[j]["amount"])
            if amount <= 0:
                break
            matched_pairs.append(
                {
                    "a_entity": int(pos[i]["book_id"]),
                    "b_entity": int(neg[j]["book_id"]),
                    "a_code": subject_code,
                    "b_code": subject_code,
                    "amount": float(amount),
                    "aux_code": aux_code,
                    "rationale": f"aux={aux_code} 科目{subject_code} 内部往来自动配对",
                }
            )
            pos[i]["amount"] -= amount
            neg[j]["amount"] -= amount
            if pos[i]["amount"] <= 0:
                i += 1
            if neg[j]["amount"] <= 0:
                j += 1
        for item in pos[i:]:
            if item["amount"] > 0:
                unmatched.append(
                    {
                        "entity": int(item["book_id"]),
                        "subject_code": subject_code,
                        "aux_code": aux_code,
                        "side": "debit_net",
                        "amount": float(item["amount"]),
                    }
                )
        for item in neg[j:]:
            if item["amount"] > 0:
                unmatched.append(
                    {
                        "entity": int(item["book_id"]),
                        "subject_code": subject_code,
                        "aux_code": aux_code,
                        "side": "credit_net",
                        "amount": float(item["amount"]),
                    }
                )
    return matched_pairs, unmatched


def _build_unmatched_export_csv(unmatched: List[Dict[str, object]]) -> str:
    head = "entity,subject_code,aux_code,side,amount"
    if not unmatched:
        return head
    lines = [head]
    for u in unmatched:
        lines.append(
            ",".join(
                [
                    str(u.get("entity") or ""),
                    str(u.get("subject_code") or ""),
                    str(u.get("aux_code") or ""),
                    str(u.get("side") or ""),
                    str(u.get("amount") or ""),
                ]
            )
        )
    return "\n".join(lines)


def _find_existing_adjustment_set(conn, group_id: int, period: str, as_of: date) -> Dict[str, object] | None:
    cols = _table_columns(conn, "consolidation_adjustments")
    if not {"batch_id", "tag", "source", "rule_code", "evidence_ref", "lines_json"}.issubset(cols):
        return None
    row = conn.execute(
        text(
            """
            SELECT id, batch_id, lines_json
            FROM consolidation_adjustments
            WHERE group_id=:group_id
              AND period=:period
              AND status='draft'
              AND tag='onboarding_ic'
              AND source='generated'
              AND rule_code='ONBOARD_IC'
              AND evidence_ref=:evidence_ref
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"group_id": int(group_id), "period": period, "evidence_ref": f"as_of:{as_of.isoformat()}"},
    ).fetchone()
    if not row:
        return None
    lines = []
    try:
        lines = json.loads(str(row.lines_json or "[]"))
    except Exception:
        lines = []
    return {"id": int(row.id), "set_id": str(row.batch_id or ""), "lines": lines if isinstance(lines, list) else []}


def run_onboarding_ic_match(group_id_value: object, as_of_value: object, operator_id: int = 1) -> Dict[str, object]:
    group_id = _parse_positive_int(group_id_value, "consolidation_group_id")
    as_of = _parse_date(as_of_value, "as_of")
    period = as_of.strftime("%Y-%m")
    set_id = f"ICM-{group_id}-{as_of.strftime('%Y%m%d')}"

    provider = get_connection_provider()
    with provider.connect() as conn:
        member_book_ids = _effective_member_book_ids(conn, group_id, as_of)
        rows = _load_ic_balances(conn, member_book_ids, as_of)
        existing = _find_existing_adjustment_set(conn, group_id, period, as_of)

    matched_pairs, unmatched = _match_by_key(rows)
    draft_lines: List[Dict[str, object]] = []
    for pair in matched_pairs:
        amount = Decimal(str(pair["amount"]))
        draft_lines.append(
            {
                "subject_code": str(pair["a_code"]),
                "debit": str(amount),
                "credit": "0",
                "note": f"onboarding_ic set={set_id} {pair['a_entity']}->{pair['b_entity']} aux={pair['aux_code']}",
                "set_id": set_id,
                "source": "generated",
                "rule": "ONBOARD_IC",
                "evidence_ref": f"as_of:{as_of.isoformat()}",
                "operator_id": str(int(operator_id or 1)),
            }
        )
        draft_lines.append(
            {
                "subject_code": str(pair["b_code"]),
                "debit": "0",
                "credit": str(amount),
                "note": f"onboarding_ic set={set_id} {pair['a_entity']}->{pair['b_entity']} aux={pair['aux_code']}",
                "set_id": set_id,
                "source": "generated",
                "rule": "ONBOARD_IC",
                "evidence_ref": f"as_of:{as_of.isoformat()}",
                "operator_id": str(int(operator_id or 1)),
            }
        )

    adjustment = None
    reused = False
    if existing:
        reused = True
        set_id = str(existing.get("set_id") or set_id)
        adjustment = {"id": int(existing.get("id") or 0)}
        draft_lines = list(existing.get("lines") or [])
    elif draft_lines:
        adjustment = create_consolidation_adjustment(
            {
                "consolidation_group_id": group_id,
                "period": period,
                "operator_id": int(operator_id or 1),
                "status": "draft",
                "source": "generated",
                "tag": "onboarding_ic",
                "rule_code": "ONBOARD_IC",
                "evidence_ref": f"as_of:{as_of.isoformat()}",
                "batch_id": set_id,
                "lines": draft_lines,
            }
        )

    return {
        "set_id": set_id,
        "group_id": group_id,
        "as_of": as_of.isoformat(),
        "member_count": len(member_book_ids),
        "matched_pairs": matched_pairs,
        "unmatched": unmatched,
        "unmatched_export_csv": _build_unmatched_export_csv(unmatched),
        "draft_adjustment_lines": draft_lines,
        "adjustment_id": (adjustment or {}).get("id"),
        "reused_existing_set": reused,
        "matched_count": len(matched_pairs),
        "unmatched_count": len(unmatched),
        "line_count": len(draft_lines),
    }
