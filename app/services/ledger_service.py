from datetime import date
from typing import Dict, List

from sqlalchemy import bindparam, text

from app.db_router import get_connection_provider
from app.services.consolidation_service import ConsolidationError, resolve_consolidation_group


class LedgerError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise LedgerError("invalid_date") from err


def _normalize_code(value: str) -> str:
    return str(value or "").strip().rstrip(".")


def _find_parent_by_prefix(code: str, existing_codes: set) -> str:
    c = _normalize_code(code)
    if len(c) <= 4:
        return ""
    if "." in c:
        parts = [p for p in c.split(".") if p]
        while len(parts) > 1:
            parts = parts[:-1]
            p = ".".join(parts)
            if p in existing_codes:
                return p
    for cut in range(len(c) - 2, 3, -2):
        p = c[:cut]
        if p in existing_codes:
            return p
    return ""


def get_subject_ledger(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    consolidation_group_id_raw = (params.get("consolidation_group_id") or "").strip()
    subject_code = _normalize_code(params.get("subject_code") or "")
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()
    summary_kw = (params.get("summary") or "").strip()
    direction = (params.get("direction") or "").strip().upper()

    if not subject_code or not start_raw or not end_raw:
        raise LedgerError("subject_code/start_date/end_date required")
    if not book_id_raw and not consolidation_group_id_raw:
        raise LedgerError("book_id or consolidation_group_id required")

    book_id = None
    if book_id_raw:
        try:
            book_id = int(book_id_raw)
        except Exception as err:
            raise LedgerError("book_id must be integer") from err

    consolidation_group_id = None
    if consolidation_group_id_raw:
        try:
            consolidation_group_id = int(consolidation_group_id_raw)
        except Exception as err:
            raise LedgerError("consolidation_group_id must be integer") from err

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    if direction and direction not in ("DEBIT", "CREDIT"):
        raise LedgerError("direction must be DEBIT or CREDIT")

    tenant_id = (params.get("tenant_id") or "").strip() or None
    provider = get_connection_provider()
    with provider.connect(tenant_id=tenant_id, book_id=book_id) as conn:
        consolidation = None
        scope_book_ids: List[int] = []
        query_mode = "single_book"
        query_mode_label = "单账套模式"
        if consolidation_group_id is not None:
            try:
                consolidation = resolve_consolidation_group(conn, consolidation_group_id)
            except ConsolidationError as err:
                raise LedgerError(str(err)) from err
            scope_book_ids = list(consolidation["member_book_ids"])
            query_mode = "consolidation_group"
            query_mode_label = "合并组模式（成员汇总）"
        else:
            scope_book_ids = [book_id]

        subject_rows = conn.execute(
            text(
                """
                SELECT id, code, name, parent_code
                FROM subjects
                WHERE book_id IN :book_ids
                """
            ).bindparams(bindparam("book_ids", expanding=True)),
            {"book_ids": scope_book_ids},
        ).fetchall()

        subject = None
        by_parent: Dict[str, List[str]] = {}
        existing_codes = {_normalize_code(r.code) for r in subject_rows if _normalize_code(r.code)}
        for row in subject_rows:
            code = _normalize_code(row.code)
            if not code:
                continue
            if code == subject_code:
                subject = row
            parent_code = _normalize_code(row.parent_code)
            if (not parent_code) or (parent_code not in existing_codes):
                parent_code = _find_parent_by_prefix(code, existing_codes)
            if parent_code:
                if parent_code not in by_parent:
                    by_parent[parent_code] = []
                by_parent[parent_code].append(code)
        if not subject:
            raise LedgerError("subject_not_found")

        scope_codes: List[str] = [subject_code]
        stack: List[str] = [subject_code]
        seen = {subject_code}
        while stack:
            parent_code = stack.pop()
            children = by_parent.get(parent_code, [])
            for code in children:
                if code in seen:
                    continue
                seen.add(code)
                scope_codes.append(code)
                stack.append(code)

        include_children = len(scope_codes) > 1
        sql = """
            SELECT v.id AS voucher_id,
                   v.voucher_date,
                   v.voucher_word,
                   v.voucher_no,
                   vl.line_no,
                   vl.summary,
                   vl.debit,
                   vl.credit,
                   vl.note
            FROM voucher_lines vl
            JOIN vouchers v ON v.id = vl.voucher_id
            WHERE v.book_id IN :book_ids
              AND v.status = 'posted'
              AND vl.subject_code IN :subject_codes
              AND v.voucher_date BETWEEN :start_date AND :end_date
        """
        params = {
            "book_ids": scope_book_ids,
            "subject_codes": scope_codes,
            "start_date": start_date,
            "end_date": end_date,
        }
        if summary_kw:
            sql += " AND vl.summary LIKE :summary"
            params["summary"] = f"%{summary_kw}%"
        if direction == "DEBIT":
            sql += " AND vl.debit > 0"
        if direction == "CREDIT":
            sql += " AND vl.credit > 0"
        sql += " ORDER BY v.voucher_date ASC, v.id ASC, vl.line_no ASC"

        rows = conn.execute(
            text(sql).bindparams(
                bindparam("book_ids", expanding=True),
                bindparam("subject_codes", expanding=True),
            ),
            params,
        ).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        items.append(
            {
                "voucher_id": r.voucher_id,
                "voucher_date": r.voucher_date.isoformat(),
                "voucher_word": r.voucher_word or "",
                "voucher_no": r.voucher_no or "",
                "line_no": r.line_no,
                "summary": r.summary or "",
                "debit": float(r.debit),
                "credit": float(r.credit),
                "note": r.note or "",
            }
        )

    rule_hint = "父级科目按“含下级明细”查询；末级科目按本级查询"
    if summary_kw or direction:
        no_data_hint = (
            "未命中明细：请检查期间、摘要过滤或借贷方向条件"
            if include_children
            else "未命中明细：请检查期间、摘要过滤或借贷方向条件"
        )
    else:
        no_data_hint = (
            "当前按父级科目口径（含下级）查询，本期间无已过账明细"
            if include_children
            else "当前科目在所选期间无已过账明细"
        )

    return {
        "book_id": book_id,
        "scope_book_ids": scope_book_ids,
        "subject_code": _normalize_code(subject.code),
        "subject_name": subject.name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "query_mode": query_mode,
        "query_mode_label": query_mode_label,
        "consolidation_group_id": (consolidation or {}).get("consolidation_group_id"),
        "consolidation_group_name": (consolidation or {}).get("consolidation_group_name", ""),
        "consolidation_group_code": (consolidation or {}).get("consolidation_group_code", ""),
        "is_eliminated": False if query_mode == "consolidation_group" else None,
        "scope_notice": (
            "当前为合并组汇总口径（仅汇总未抵销）"
            if query_mode == "consolidation_group"
            else "当前为单账套口径"
        ),
        "query_scope": "parent_with_children" if include_children else "single_subject",
        "query_subject_codes": scope_codes,
        "query_rule_hint": rule_hint,
        "no_data_hint": no_data_hint,
        "items": items,
    }


def get_voucher_detail(voucher_id: int) -> Dict[str, object]:
    provider = get_connection_provider()
    with provider.connect() as conn:
        header = conn.execute(
            text(
                """
                SELECT id, book_id, voucher_date, voucher_word, voucher_no, attachments, maker, status
                FROM vouchers
                WHERE id=:id
                """
            ),
            {"id": voucher_id},
        ).fetchone()
        if not header:
            raise LedgerError("voucher_not_found")

        lines = conn.execute(
            text(
                """
                SELECT id, line_no, summary, subject_code, subject_name, debit, credit, due_date, note,
                       aux_display, aux_type, aux_id, aux_code, aux_name
                FROM voucher_lines
                WHERE voucher_id=:id
                ORDER BY line_no ASC
                """
            ),
            {"id": voucher_id},
        ).fetchall()

        line_ids = [int(r.id) for r in lines if r.id is not None]
        aux_by_line: Dict[int, List[Dict[str, object]]] = {}
        if line_ids:
            try:
                aux_rows = conn.execute(
                    text(
                        """
                        SELECT voucher_line_id, aux_type, aux_id, aux_code, aux_name, aux_display, sort_order
                        FROM voucher_line_aux_items
                        WHERE voucher_id=:voucher_id
                          AND voucher_line_id IN :line_ids
                        ORDER BY voucher_line_id ASC, sort_order ASC, id ASC
                        """
                    ).bindparams(bindparam("line_ids", expanding=True)),
                    {"voucher_id": voucher_id, "line_ids": line_ids},
                ).fetchall()
            except Exception:
                aux_rows = []
            for aux in aux_rows:
                line_id = int(aux.voucher_line_id)
                if line_id not in aux_by_line:
                    aux_by_line[line_id] = []
                aux_by_line[line_id].append(
                    {
                        "aux_type": aux.aux_type or "",
                        "aux_id": aux.aux_id,
                        "aux_code": aux.aux_code or "",
                        "aux_name": aux.aux_name or "",
                        "aux_display": aux.aux_display or "",
                        "sort_order": int(aux.sort_order or 0),
                    }
                )

    return {
        "id": header.id,
        "book_id": header.book_id,
        "voucher_date": header.voucher_date.isoformat(),
        "voucher_word": header.voucher_word or "",
        "voucher_no": header.voucher_no or "",
        "attachments": header.attachments,
        "maker": header.maker or "",
        "status": header.status,
        "lines": [
            {
                "line_no": r.line_no,
                "summary": r.summary or "",
                "subject_code": r.subject_code,
                "subject_name": r.subject_name,
                "debit": float(r.debit),
                "credit": float(r.credit),
                "due_date": r.due_date.isoformat() if r.due_date else "",
                "note": r.note or "",
                "aux_display": r.aux_display or "",
                "aux_type": r.aux_type or "",
                "aux_id": r.aux_id,
                "aux_code": r.aux_code or "",
                "aux_name": r.aux_name or "",
                "aux_items": (
                    aux_by_line.get(int(r.id), [])
                    if aux_by_line.get(int(r.id))
                    else (
                        [
                            {
                                "aux_type": r.aux_type or "",
                                "aux_id": r.aux_id,
                                "aux_code": r.aux_code or "",
                                "aux_name": r.aux_name or "",
                                "aux_display": r.aux_display or "",
                                "sort_order": 1,
                            }
                        ]
                        if (r.aux_type or r.aux_code or r.aux_name or r.aux_display)
                        else []
                    )
                ),
            }
            for r in lines
        ],
    }
