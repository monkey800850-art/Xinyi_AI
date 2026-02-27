import csv
import os
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db import get_engine


class StandardImportError(RuntimeError):
    pass


def _resolve_csv_path(standard: str) -> str:
    filename_map = {
        "small_enterprise": "small_enterprise.csv",
        "enterprise": "enterprise.csv",
    }
    if standard not in filename_map:
        raise StandardImportError(
            "Unknown standard. Use 'small_enterprise' or 'enterprise'."
        )

    base_dir = os.getenv("TEMPLATES_DIR", "templates/standards")
    return os.path.join(base_dir, filename_map[standard])


def _is_valid_code(code: str) -> bool:
    if not code:
        return False
    return any(ch.isdigit() for ch in code)


def _calc_level(code: str) -> int:
    length = len(code)
    if length <= 4:
        return 1
    return 1 + max(0, (length - 4) // 2)


def _calc_parent_code(code: str) -> Optional[str]:
    if len(code) <= 4:
        return None
    return code[:-2]


def _map_balance_direction(value: str) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if value == "借":
        return "DEBIT"
    if value == "贷":
        return "CREDIT"
    return None


def _infer_balance_direction(code: str, category: str, name: str) -> Optional[str]:
    c0 = (code or "").strip()[:1]
    if c0 == "1":
        return "DEBIT"
    if c0 in ("2", "3"):
        return "CREDIT"
    if c0 == "4":
        return "DEBIT"
    if c0 in ("5", "6"):
        text_name = (name or "").strip()
        if any(k in text_name for k in ("收入", "收益")):
            return "CREDIT"
        if any(k in text_name for k in ("成本", "费用", "损失", "税金", "支出", "减值")):
            return "DEBIT"
        return "DEBIT"

    text_cat = (category or "").strip()
    if "资产" in text_cat or "成本" in text_cat:
        return "DEBIT"
    if "负债" in text_cat or "权益" in text_cat:
        return "CREDIT"
    return None


def _derive_flags(note: str) -> Dict[str, int]:
    note = note or ""
    return {
        "requires_auxiliary": 1 if "辅助核算" in note else 0,
        "requires_bank_account_aux": 1
        if ("银行账户" in note or "银行" in note)
        else 0,
        "supports_foreign_currency": 1 if "外币" in note else 0,
    }


def _import_with_connection(
    conn, book_id: int, standard: str, csv_path: str
) -> Dict[str, object]:
    template_type = standard

    total = 0
    skipped = 0
    inserted = 0
    failed = 0
    errors: List[str] = []

    existing = conn.execute(
        text(
            "SELECT 1 FROM subjects WHERE book_id=:book_id AND template_type=:tt LIMIT 1"
        ),
        {"book_id": book_id, "tt": template_type},
    ).fetchone()
    if existing:
        raise StandardImportError(
            "Subjects already initialized for this book_id and template_type"
        )

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            code = (row.get("科目编码") or "").strip()
            name = (row.get("科目名称") or "").strip()
            category = (row.get("类别") or "").strip()
            balance_direction = _map_balance_direction((row.get("余额方向") or "").strip())
            if not balance_direction:
                balance_direction = _infer_balance_direction(code, category, name)
            note = (row.get("说明") or "").strip()

            if not _is_valid_code(code):
                skipped += 1
                continue

            if not name:
                skipped += 1
                continue

            flags = _derive_flags(note)

            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO subjects (
                            book_id, code, name, is_enabled,
                            category, balance_direction, note, template_type,
                            level, parent_code,
                            requires_auxiliary, requires_bank_account_aux, supports_foreign_currency
                        ) VALUES (
                            :book_id, :code, :name, 1,
                            :category, :balance_direction, :note, :template_type,
                            :level, :parent_code,
                            :requires_auxiliary, :requires_bank_account_aux, :supports_foreign_currency
                        )
                        """
                    ),
                    {
                        "book_id": book_id,
                        "code": code,
                        "name": name,
                        "category": category,
                        "balance_direction": balance_direction,
                        "note": note,
                        "template_type": template_type,
                        "level": _calc_level(code),
                        "parent_code": _calc_parent_code(code),
                        "requires_auxiliary": flags["requires_auxiliary"],
                        "requires_bank_account_aux": flags[
                            "requires_bank_account_aux"
                        ],
                        "supports_foreign_currency": flags[
                            "supports_foreign_currency"
                        ],
                    },
                )
                inserted += 1
            except Exception as err:
                failed += 1
                errors.append(f"code={code} name={name} error={err}")

    return {
        "standard": standard,
        "book_id": book_id,
        "total": total,
        "skipped": skipped,
        "inserted": inserted,
        "failed": failed,
        "errors": errors,
    }


def import_subjects_from_standard(
    book_id: int, standard: str, connection=None
) -> Dict[str, object]:
    if not isinstance(book_id, int) or book_id <= 0:
        raise StandardImportError("book_id must be a positive integer")

    csv_path = _resolve_csv_path(standard)
    if not os.path.exists(csv_path):
        raise StandardImportError(f"CSV not found: {csv_path}")

    if connection is not None:
        return _import_with_connection(connection, book_id, standard, csv_path)

    engine = get_engine()
    with engine.begin() as conn:
        return _import_with_connection(conn, book_id, standard, csv_path)
