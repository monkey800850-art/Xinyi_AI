import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text

from app.db import get_engine
from app.services.voucher_service import (
    AXIS_LABEL_MAP,
    _check_period_open,
    _fetch_aux_master,
    _normalize_aux_type,
    _parse_decimal,
    _resolve_line_aux_items,
    _subject_aux_requirements,
    _subject_requires_due_date,
    _ensure_voucher_line_aux_items_table,
)


class VoucherImportError(RuntimeError):
    pass


REQUIRED_HEADERS = [
    "voucher_date",
    "voucher_no",
    "summary",
    "subject_code",
    "debit_amount",
    "credit_amount",
]

OPTIONAL_HEADERS = [
    "line_no",
    "subject_name",
    "aux_department_code",
    "aux_person_code",
    "aux_entity_code",
    "aux_project_code",
    "aux_bank_account_code",
]

AUX_COLUMN_MAP = {
    "aux_department_code": "department",
    "aux_person_code": "person",
    "aux_entity_code": "entity",
    "aux_project_code": "project",
    "aux_bank_account_code": "bank_account",
}


def _aux_column_by_type(aux_type: str) -> str:
    mapping = {
        "department": "aux_department_code",
        "person": "aux_person_code",
        "entity": "aux_entity_code",
        "project": "aux_project_code",
        "bank_account": "aux_bank_account_code",
    }
    return mapping.get(aux_type, "aux_code")


def _error(
    errors: List[Dict[str, object]],
    row_no: int,
    voucher_no: str,
    field: str,
    message: str,
    voucher_key: str = "",
):
    errors.append(
        {
            "row_no": int(row_no or 0),
            "voucher_no": str(voucher_no or "").strip(),
            "field": field,
            "message": message,
            "level": "error",
            "voucher_key": voucher_key or "",
        }
    )


def _decode_csv_bytes(content: bytes) -> str:
    if not content:
        return ""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return content.decode(enc)
        except Exception:
            continue
    raise VoucherImportError("文件编码不支持，请使用 UTF-8/UTF-8-BOM/GBK 的 CSV 文件")


def _parse_book_id(value) -> int:
    raw = str(value or "").strip()
    if not raw:
        raise VoucherImportError("book_id required")
    try:
        book_id = int(raw)
    except Exception as err:
        raise VoucherImportError("book_id must be integer") from err
    if book_id <= 0:
        raise VoucherImportError("book_id must be positive")
    return book_id


def _parse_iso_date(value: str) -> Optional[date]:
    text_value = str(value or "").strip()
    if not text_value:
        return None
    try:
        return date.fromisoformat(text_value)
    except Exception:
        return None


def _make_aux_items_from_row(row: Dict[str, str]) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    sort_order = 1
    for column, aux_type in AUX_COLUMN_MAP.items():
        code = str(row.get(column) or "").strip()
        if not code:
            continue
        items.append(
            {
                "aux_type": aux_type,
                "aux_code": code,
                "aux_name": "",
                "aux_display": "",
                "sort_order": sort_order,
            }
        )
        sort_order += 1
    return items


def _build_template_csv_bytes() -> bytes:
    headers = REQUIRED_HEADERS + OPTIONAL_HEADERS
    sample_lines = [
        {
            "voucher_date": "2026-01-15",
            "voucher_no": "JZ0001",
            "summary": "采购材料入库",
            "line_no": "1",
            "subject_code": "1405",
            "subject_name": "库存商品",
            "debit_amount": "1000.00",
            "credit_amount": "0.00",
            "aux_department_code": "D001",
            "aux_person_code": "",
            "aux_entity_code": "E001",
            "aux_project_code": "",
            "aux_bank_account_code": "",
        },
        {
            "voucher_date": "2026-01-15",
            "voucher_no": "JZ0001",
            "summary": "采购材料入库",
            "line_no": "2",
            "subject_code": "2202",
            "subject_name": "应付账款",
            "debit_amount": "0.00",
            "credit_amount": "1000.00",
            "aux_department_code": "",
            "aux_person_code": "",
            "aux_entity_code": "E001",
            "aux_project_code": "",
            "aux_bank_account_code": "",
        },
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for line in sample_lines:
        writer.writerow(line)
    return output.getvalue().encode("utf-8-sig")


def get_voucher_import_template() -> Tuple[str, bytes]:
    filename = f"voucher_import_template_{datetime.now().strftime('%Y%m%d')}.csv"
    return filename, _build_template_csv_bytes()


def _parse_csv_rows(filename: str, content: bytes) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    if not filename.lower().endswith(".csv"):
        raise VoucherImportError("当前MVP仅支持CSV文件")
    text_content = _decode_csv_bytes(content)
    reader = csv.DictReader(io.StringIO(text_content))
    headers = [str(h or "").strip() for h in (reader.fieldnames or [])]
    missing_headers = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing_headers:
        raise VoucherImportError("模板缺少字段: " + ",".join(missing_headers))

    rows: List[Dict[str, object]] = []
    file_total_rows = 0
    for idx, raw in enumerate(reader, start=2):
        file_total_rows += 1
        row = {str(k or "").strip(): str(v or "").strip() for k, v in (raw or {}).items()}
        if not any(row.values()):
            continue
        rows.append(
            {
                "file_row_no": idx,
                "voucher_date": row.get("voucher_date", ""),
                "voucher_no": row.get("voucher_no", ""),
                "summary": row.get("summary", ""),
                "line_no": row.get("line_no", ""),
                "subject_code": row.get("subject_code", ""),
                "subject_name": row.get("subject_name", ""),
                "debit_amount": row.get("debit_amount", ""),
                "credit_amount": row.get("credit_amount", ""),
                "aux_department_code": row.get("aux_department_code", ""),
                "aux_person_code": row.get("aux_person_code", ""),
                "aux_entity_code": row.get("aux_entity_code", ""),
                "aux_project_code": row.get("aux_project_code", ""),
                "aux_bank_account_code": row.get("aux_bank_account_code", ""),
            }
        )
    return rows, {"file_total_rows": file_total_rows, "headers": headers}


def _book_context(conn, book_id: int) -> Dict[str, object]:
    row = conn.execute(
        text(
            """
            SELECT b.id, b.name, b.is_enabled,
                   COALESCE(rc.rule_value, CONCAT('BOOK-', LPAD(b.id, 4, '0'))) AS book_code
            FROM books b
            LEFT JOIN sys_rules rc ON rc.rule_key=CONCAT('book_meta:code:', b.id)
            WHERE b.id=:book_id
            LIMIT 1
            """
        ),
        {"book_id": book_id},
    ).fetchone()
    if not row:
        raise VoucherImportError("book_not_found")
    if int(row.is_enabled or 0) != 1:
        raise VoucherImportError("book_disabled")
    return {
        "book_id": int(row.id),
        "book_name": str(row.name or ""),
        "book_code": str(row.book_code or f"BOOK-{int(row.id):04d}"),
    }


def _book_start_date(conn, book_id: int) -> Optional[date]:
    sp = conn.execute(
        text("SELECT rule_value FROM sys_rules WHERE rule_key=:key LIMIT 1"),
        {"key": f"book_meta:start_period:{book_id}"},
    ).fetchone()
    if sp and str(sp.rule_value or "").strip():
        period = str(sp.rule_value or "").strip()
        d = _parse_iso_date(period + "-01")
        if d:
            return d
    min_row = conn.execute(
        text("SELECT MIN(year * 100 + month) AS ym FROM accounting_periods WHERE book_id=:book_id"),
        {"book_id": book_id},
    ).fetchone()
    if not min_row or min_row.ym is None:
        return None
    try:
        ym = int(min_row.ym)
        y = ym // 100
        m = ym % 100
        return date(y, m, 1)
    except Exception:
        return None


def _subject_row(conn, book_id: int, subject_code: str):
    return conn.execute(
        text(
            """
            SELECT s.id, s.name, s.is_enabled, s.requires_auxiliary, s.requires_bank_account_aux,
                   COALESCE(r.rule_value, '') AS aux_type,
                   COALESCE(rm.rule_value, '') AS aux_types,
                   s.note, s.category,
                   CASE WHEN EXISTS (
                     SELECT 1 FROM subjects c
                     WHERE c.book_id = s.book_id
                       AND c.is_enabled = 1
                       AND c.code <> s.code
                       AND (c.parent_code = s.code OR c.code LIKE :desc_prefix)
                     LIMIT 1
                   ) THEN 0 ELSE 1 END AS is_leaf
            FROM subjects s
            LEFT JOIN sys_rules r ON r.rule_key = CONCAT('subject_aux_type:', s.code)
            LEFT JOIN sys_rules rm ON rm.rule_key = CONCAT('subject_aux_types:', s.code)
            WHERE s.book_id=:book_id AND s.code=:code
            LIMIT 1
            """
        ),
        {"book_id": book_id, "code": subject_code, "desc_prefix": f"{subject_code}.%"},
    ).fetchone()


def _validate_rows_and_build_vouchers(
    conn,
    book_id: int,
    parsed_rows: List[Dict[str, object]],
) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    grouped: Dict[str, Dict[str, object]] = {}
    valid_line_rows = 0
    start_date = _book_start_date(conn, book_id)

    for raw in parsed_rows:
        file_row_no = int(raw.get("file_row_no") or 0)
        voucher_no = str(raw.get("voucher_no") or "").strip()
        voucher_date_text = str(raw.get("voucher_date") or "").strip()
        voucher_date = _parse_iso_date(voucher_date_text)
        voucher_key = f"{voucher_date_text}#{voucher_no}"

        if not voucher_date:
            _error(errors, file_row_no, voucher_no, "voucher_date", "凭证日期格式错误，需 YYYY-MM-DD", voucher_key)
        if not voucher_no:
            _error(errors, file_row_no, voucher_no, "voucher_no", "凭证号必填", voucher_key)
        if not str(raw.get("subject_code") or "").strip():
            _error(errors, file_row_no, voucher_no, "subject_code", "科目编码必填", voucher_key)
        if start_date and voucher_date and voucher_date < start_date:
            _error(
                errors,
                file_row_no,
                voucher_no,
                "voucher_date",
                f"凭证日期早于账套启用期间({start_date.isoformat()})",
                voucher_key,
            )

        try:
            debit = _parse_decimal(raw.get("debit_amount"))
            credit = _parse_decimal(raw.get("credit_amount"))
        except Exception:
            _error(errors, file_row_no, voucher_no, "amount", "借贷金额格式错误", voucher_key)
            debit = Decimal("0")
            credit = Decimal("0")

        if debit == 0 and credit == 0:
            _error(errors, file_row_no, voucher_no, "amount", "借贷金额不能同时为0", voucher_key)
        if debit > 0 and credit > 0:
            _error(errors, file_row_no, voucher_no, "amount", "借贷金额不能同时大于0", voucher_key)
        if debit < 0 or credit < 0:
            _error(errors, file_row_no, voucher_no, "amount", "借贷金额不能为负数", voucher_key)

        if voucher_no and voucher_date:
            grouped.setdefault(
                voucher_key,
                {"voucher_no": voucher_no, "voucher_date": voucher_date, "raw_lines": []},
            )["raw_lines"].append(
                {
                    "file_row_no": file_row_no,
                    "voucher_no": voucher_no,
                    "voucher_date": voucher_date,
                    "summary": str(raw.get("summary") or "").strip(),
                    "line_no": str(raw.get("line_no") or "").strip(),
                    "subject_code": str(raw.get("subject_code") or "").strip(),
                    "subject_name": str(raw.get("subject_name") or "").strip(),
                    "debit": str(raw.get("debit_amount") or "").strip(),
                    "credit": str(raw.get("credit_amount") or "").strip(),
                    "aux_items": _make_aux_items_from_row(raw),
                }
            )
            valid_line_rows += 1

    normalized_vouchers: List[Dict[str, object]] = []
    existing_dup_keys = set()
    for key, group in grouped.items():
        voucher_no = str(group.get("voucher_no") or "")
        voucher_date = group.get("voucher_date")
        file_lines = list(group.get("raw_lines") or [])
        file_lines.sort(key=lambda x: (int(x.get("line_no") or "0") if str(x.get("line_no") or "").isdigit() else 999999, int(x.get("file_row_no") or 0)))

        if len(file_lines) < 2:
            _error(errors, int(file_lines[0].get("file_row_no") or 0), voucher_no, "voucher_no", "同一凭证至少需要两条分录", key)

        row = conn.execute(
            text(
                """
                SELECT id FROM vouchers
                WHERE book_id=:book_id AND voucher_date=:voucher_date AND voucher_no=:voucher_no
                LIMIT 1
                """
            ),
            {"book_id": book_id, "voucher_date": voucher_date, "voucher_no": voucher_no},
        ).fetchone()
        if row:
            existing_dup_keys.add(key)
            _error(errors, int(file_lines[0].get("file_row_no") or 0), voucher_no, "voucher_no", "凭证已存在（重复导入禁止）", key)

        ok, msg = _check_period_open(conn, book_id, voucher_date)
        if not ok:
            _error(errors, int(file_lines[0].get("file_row_no") or 0), voucher_no, "voucher_date", msg or "会计期间已结账", key)

        total_debit = Decimal("0")
        total_credit = Decimal("0")
        normalized_lines: List[Dict[str, object]] = []
        for idx, line in enumerate(file_lines, start=1):
            file_row_no = int(line.get("file_row_no") or 0)
            subject_code = str(line.get("subject_code") or "").strip()
            debit = Decimal("0")
            credit = Decimal("0")
            try:
                debit = _parse_decimal(line.get("debit"))
                credit = _parse_decimal(line.get("credit"))
            except Exception:
                _error(errors, file_row_no, voucher_no, "amount", "借贷金额格式错误", key)
                continue
            total_debit += debit
            total_credit += credit

            subject = _subject_row(conn, book_id, subject_code)
            if not subject:
                _error(errors, file_row_no, voucher_no, "subject_code", "科目不存在", key)
                continue
            if int(subject.is_enabled or 0) != 1:
                _error(errors, file_row_no, voucher_no, "subject_code", "科目已停用", key)
                continue
            if (debit != 0 or credit != 0) and int(subject.is_leaf or 0) != 1:
                _error(errors, file_row_no, voucher_no, "subject_code", "该科目非末级，禁止录入金额", key)
                continue

            required_types, allowed_types = _subject_aux_requirements(subject)
            aux_items = _resolve_line_aux_items(line)
            if int(subject.requires_auxiliary or 0) == 1 and not required_types:
                _error(errors, file_row_no, voucher_no, "aux_items", "该科目要求辅助核算，但未配置辅助维度", key)

            normalized_aux_items: List[Dict[str, object]] = []
            line_types_seen: List[str] = []
            for aux_idx, raw_aux in enumerate(aux_items):
                aux_type = _normalize_aux_type(raw_aux.get("aux_type"))
                aux_code = str(raw_aux.get("aux_code") or "").strip()
                if not aux_type:
                    _error(errors, file_row_no, voucher_no, "aux_items", "辅助维度类型非法", key)
                    continue
                if aux_type in line_types_seen:
                    _error(errors, file_row_no, voucher_no, "aux_items", f"辅助维度重复：{aux_type}", key)
                    continue
                line_types_seen.append(aux_type)

                if allowed_types and aux_type not in allowed_types:
                    _error(errors, file_row_no, voucher_no, "aux_items", f"该科目未挂接辅助维度：{aux_type}", key)
                    continue
                if not allowed_types and aux_code:
                    _error(errors, file_row_no, voucher_no, "aux_items", "该科目未启用辅助核算，禁止录入辅助项", key)
                    continue
                if not aux_code:
                    _error(errors, file_row_no, voucher_no, "aux_items", "辅助项目编码必填", key)
                    continue

                aux_row = _fetch_aux_master(conn, book_id, aux_type, aux_code)
                if not aux_row:
                    axis = AXIS_LABEL_MAP.get(aux_type, aux_type or "辅助维度")
                    _error(errors, file_row_no, voucher_no, _aux_column_by_type(aux_type), f"{axis}编码不存在：{aux_code}", key)
                    continue
                if int(aux_row.is_enabled or 0) != 1:
                    axis = AXIS_LABEL_MAP.get(aux_type, aux_type or "辅助维度")
                    _error(errors, file_row_no, voucher_no, "aux_code", f"{axis}已停用：{aux_code}", key)
                    continue

                normalized_aux_items.append(
                    {
                        "aux_type": aux_type,
                        "aux_id": aux_row.id,
                        "aux_code": aux_row.code,
                        "aux_name": aux_row.name or "",
                        "aux_display": f"{aux_row.code} {aux_row.name}",
                        "sort_order": aux_idx + 1,
                    }
                )

            for required_type in required_types:
                if required_type not in line_types_seen:
                    _error(errors, file_row_no, voucher_no, "aux_items", f"缺少必填辅助维度：{required_type}", key)

            if _subject_requires_due_date(subject.name, subject.note, subject.category):
                _error(errors, file_row_no, voucher_no, "due_date", "往来类科目需填写到期日（导入模板暂未支持）", key)

            normalized_lines.append(
                {
                    "line_no": idx,
                    "file_row_no": file_row_no,
                    "summary": line.get("summary") or "",
                    "subject_code": subject_code,
                    "subject_name": (line.get("subject_name") or "").strip() or (subject.name or ""),
                    "debit": debit,
                    "credit": credit,
                    "aux_items": normalized_aux_items,
                }
            )

        if total_debit != total_credit:
            _error(errors, int(file_lines[0].get("file_row_no") or 0), voucher_no, "balance", f"凭证借贷不平衡，差额：{(total_debit-total_credit):.2f}", key)

        normalized_vouchers.append(
            {
                "voucher_key": key,
                "voucher_no": voucher_no,
                "voucher_date": voucher_date,
                "lines": normalized_lines,
            }
        )

    error_keys = set([str(e.get("voucher_key") or "") for e in errors if str(e.get("voucher_key") or "")])
    passed_vouchers = 0
    failed_vouchers = 0
    for v in normalized_vouchers:
        if str(v.get("voucher_key") or "") in error_keys:
            failed_vouchers += 1
        else:
            passed_vouchers += 1

    for e in errors:
        e.pop("voucher_key", None)

    return {
        "vouchers": normalized_vouchers,
        "errors": errors,
        "summary": {
            "file_total_rows": len(parsed_rows),
            "valid_line_rows": valid_line_rows,
            "voucher_groups": len(grouped),
            "passed_voucher_count": passed_vouchers,
            "failed_voucher_count": failed_vouchers,
            "duplicated_voucher_count": len(existing_dup_keys),
        },
    }


def _insert_vouchers(conn, book_id: int, vouchers: List[Dict[str, object]], maker: str) -> Dict[str, int]:
    imported_voucher_count = 0
    imported_line_count = 0
    _ensure_voucher_line_aux_items_table(conn)
    for voucher in vouchers:
        result = conn.execute(
            text(
                """
                INSERT INTO vouchers (book_id, voucher_date, voucher_word, voucher_no, attachments, maker, status)
                VALUES (:book_id, :voucher_date, :voucher_word, :voucher_no, 0, :maker, 'draft')
                """
            ),
            {
                "book_id": book_id,
                "voucher_date": voucher.get("voucher_date"),
                "voucher_word": "记",
                "voucher_no": voucher.get("voucher_no"),
                "maker": maker or "importer",
            },
        )
        voucher_id = int(result.lastrowid)
        imported_voucher_count += 1
        for line in voucher.get("lines") or []:
            subject = conn.execute(
                text("SELECT id, name FROM subjects WHERE book_id=:book_id AND code=:code LIMIT 1"),
                {"book_id": book_id, "code": line.get("subject_code")},
            ).fetchone()
            if not subject:
                raise VoucherImportError(f"subject_not_found_during_commit:{line.get('subject_code')}")
            first_aux = (line.get("aux_items") or [{}])[0] if (line.get("aux_items") or []) else {}
            line_res = conn.execute(
                text(
                    """
                    INSERT INTO voucher_lines (
                        voucher_id, line_no, summary,
                        subject_id, subject_code, subject_name,
                        aux_display, aux_type, aux_id, aux_code, aux_name,
                        debit, credit, due_date, note
                    ) VALUES (
                        :voucher_id, :line_no, :summary,
                        :subject_id, :subject_code, :subject_name,
                        :aux_display, :aux_type, :aux_id, :aux_code, :aux_name,
                        :debit, :credit, NULL, NULL
                    )
                    """
                ),
                {
                    "voucher_id": voucher_id,
                    "line_no": int(line.get("line_no") or 0),
                    "summary": line.get("summary") or "",
                    "subject_id": int(subject.id),
                    "subject_code": line.get("subject_code"),
                    "subject_name": line.get("subject_name") or subject.name or "",
                    "aux_display": first_aux.get("aux_display"),
                    "aux_type": first_aux.get("aux_type"),
                    "aux_id": first_aux.get("aux_id"),
                    "aux_code": first_aux.get("aux_code"),
                    "aux_name": first_aux.get("aux_name"),
                    "debit": line.get("debit"),
                    "credit": line.get("credit"),
                },
            )
            voucher_line_id = int(line_res.lastrowid)
            imported_line_count += 1
            for aux in line.get("aux_items") or []:
                conn.execute(
                    text(
                        """
                        INSERT INTO voucher_line_aux_items (
                            voucher_id, voucher_line_id, line_no,
                            aux_type, aux_id, aux_code, aux_name, aux_display, sort_order
                        ) VALUES (
                            :voucher_id, :voucher_line_id, :line_no,
                            :aux_type, :aux_id, :aux_code, :aux_name, :aux_display, :sort_order
                        )
                        """
                    ),
                    {
                        "voucher_id": voucher_id,
                        "voucher_line_id": voucher_line_id,
                        "line_no": int(line.get("line_no") or 0),
                        "aux_type": aux.get("aux_type"),
                        "aux_id": aux.get("aux_id"),
                        "aux_code": aux.get("aux_code"),
                        "aux_name": aux.get("aux_name"),
                        "aux_display": aux.get("aux_display"),
                        "sort_order": int(aux.get("sort_order") or 1),
                    },
                )
    return {"imported_voucher_count": imported_voucher_count, "imported_line_count": imported_line_count}


def _run_import(
    *,
    book_id: int,
    filename: str,
    content: bytes,
    mode: str,
    maker: str,
) -> Dict[str, object]:
    if mode not in ("preview", "commit"):
        raise VoucherImportError("mode must be preview or commit")

    parsed_rows, file_meta = _parse_csv_rows(filename, content)
    if not parsed_rows:
        raise VoucherImportError("空文件或无有效数据行")
    batch_id = "VCH-IMP-" + uuid.uuid4().hex[:12]
    engine = get_engine()

    with engine.begin() as conn:
        book = _book_context(conn, book_id)
        validated = _validate_rows_and_build_vouchers(conn, book_id, parsed_rows)
        errors = validated.get("errors") or []
        summary = validated.get("summary") or {}

        result = {
            "mode": mode,
            "import_batch_id": batch_id,
            "book": book,
            "strategy": {"duplicate_policy": "strict_reject", "transaction_mode": "all_or_nothing"},
            "summary": {
                "file_total_rows": int(file_meta.get("file_total_rows") or 0),
                "effective_rows": int(summary.get("valid_line_rows") or 0),
                "voucher_groups": int(summary.get("voucher_groups") or 0),
                "passed_voucher_count": int(summary.get("passed_voucher_count") or 0),
                "failed_voucher_count": int(summary.get("failed_voucher_count") or 0),
                "duplicated_voucher_count": int(summary.get("duplicated_voucher_count") or 0),
                "imported_voucher_count": 0,
                "imported_line_count": 0,
            },
            "error_count": len(errors),
            "errors": errors,
        }

        if errors:
            return result
        if mode == "preview":
            return result

        inserted = _insert_vouchers(conn, book_id, validated.get("vouchers") or [], maker=maker)
        result["summary"]["imported_voucher_count"] = int(inserted.get("imported_voucher_count") or 0)
        result["summary"]["imported_line_count"] = int(inserted.get("imported_line_count") or 0)
        return result


def preview_vouchers_import(payload: Dict[str, object], file_name: str, file_bytes: bytes) -> Dict[str, object]:
    book_id = _parse_book_id(payload.get("book_id"))
    maker = str(payload.get("maker") or "").strip()
    return _run_import(book_id=book_id, filename=file_name, content=file_bytes, mode="preview", maker=maker)


def commit_vouchers_import(payload: Dict[str, object], file_name: str, file_bytes: bytes) -> Dict[str, object]:
    book_id = _parse_book_id(payload.get("book_id"))
    maker = str(payload.get("maker") or "").strip()
    return _run_import(book_id=book_id, filename=file_name, content=file_bytes, mode="commit", maker=maker)
