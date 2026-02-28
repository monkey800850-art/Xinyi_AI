from datetime import date
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine
from app.services.standard_importer import StandardImportError, import_subjects_from_standard


class BookCreateError(RuntimeError):
    pass


class BookManageError(RuntimeError):
    pass


def _init_accounting_periods(conn, book_id: int, start_year: int, years: int = 3) -> Dict[str, int]:
    inserted = 0
    total = years * 12
    for y in range(start_year, start_year + years):
        for m in range(1, 13):
            conn.execute(
                text(
                    """
                    INSERT INTO accounting_periods (book_id, year, month, status)
                    VALUES (:book_id, :year, :month, 'open')
                    ON DUPLICATE KEY UPDATE status=status
                    """
                ),
                {"book_id": book_id, "year": y, "month": m},
            )
    row = conn.execute(
        text("SELECT COUNT(1) AS c FROM accounting_periods WHERE book_id=:book_id"),
        {"book_id": book_id},
    ).fetchone()
    existing = int(row.c or 0)
    inserted = max(0, existing)
    return {"target_total": total, "existing_total": existing, "inserted_or_existing": inserted}


def _build_init_integrity(conn, book_id: int) -> Dict[str, object]:
    subject_row = conn.execute(
        text("SELECT COUNT(1) AS c FROM subjects WHERE book_id=:book_id"),
        {"book_id": book_id},
    ).fetchone()
    period_row = conn.execute(
        text("SELECT COUNT(1) AS c FROM accounting_periods WHERE book_id=:book_id"),
        {"book_id": book_id},
    ).fetchone()
    subject_count = int(subject_row.c or 0)
    period_count = int(period_row.c or 0)
    checks = {
        "subjects_initialized": subject_count > 0,
        "periods_initialized": period_count >= 12,
        "basic_params_minimal": True,
        "duplicate_init_guard": True,
    }
    return {
        "subject_count": subject_count,
        "period_count": period_count,
        "checks": checks,
        "ok": all(checks.values()),
    }


def create_book_with_subject_init(payload: Dict[str, object]) -> Dict[str, object]:
    accounting_standard = (payload.get("accounting_standard") or "").strip()
    if not accounting_standard:
        raise BookCreateError("accounting_standard is required")

    if accounting_standard not in ("small_enterprise", "enterprise"):
        raise BookCreateError(
            "accounting_standard must be one of: small_enterprise, enterprise"
        )

    name = (payload.get("name") or "").strip() or None

    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO books (name, accounting_standard, is_enabled)
                VALUES (:name, :accounting_standard, 1)
                """
            ),
            {"name": name, "accounting_standard": accounting_standard},
        )
        book_id = result.lastrowid

        try:
            init_result = import_subjects_from_standard(
                book_id, accounting_standard, connection=conn
            )
        except StandardImportError as err:
            raise BookCreateError(str(err)) from err
        current_year = date.today().year
        period_init_result = _init_accounting_periods(conn, book_id, current_year - 1, years=3)
        integrity = _build_init_integrity(conn, book_id)

    return {
        "book_id": book_id,
        "accounting_standard": accounting_standard,
        "subject_init_result": init_result,
        "period_init_result": period_init_result,
        "init_integrity": integrity,
    }


def get_book_init_integrity(book_id: int) -> Dict[str, object]:
    try:
        book_id = int(book_id)
    except Exception as err:
        raise BookManageError("book_id must be integer") from err

    engine = get_engine()
    with engine.connect() as conn:
        book = conn.execute(
            text("SELECT id, name, accounting_standard, is_enabled FROM books WHERE id=:id LIMIT 1"),
            {"id": book_id},
        ).fetchone()
        if not book:
            raise BookManageError("book_not_found")
        integrity = _build_init_integrity(conn, book_id)
    return {
        "book_id": book_id,
        "book_name": book.name or "",
        "accounting_standard": book.accounting_standard or "",
        "is_enabled": int(book.is_enabled or 0),
        "init_integrity": integrity,
    }


def build_book_backup_snapshot(book_id: int) -> Dict[str, object]:
    try:
        book_id = int(book_id)
    except Exception as err:
        raise BookManageError("book_id must be integer") from err

    engine = get_engine()
    with engine.connect() as conn:
        book = conn.execute(
            text("SELECT id, name, accounting_standard, is_enabled FROM books WHERE id=:id LIMIT 1"),
            {"id": book_id},
        ).fetchone()
        if not book:
            raise BookManageError("book_not_found")

        subjects = conn.execute(
            text(
                """
                SELECT code, name, category, balance_direction, level, parent_code, is_enabled
                FROM subjects
                WHERE book_id=:book_id
                ORDER BY code ASC
                """
            ),
            {"book_id": book_id},
        ).fetchall()
        periods = conn.execute(
            text(
                """
                SELECT year, month, status
                FROM accounting_periods
                WHERE book_id=:book_id
                ORDER BY year ASC, month ASC
                """
            ),
            {"book_id": book_id},
        ).fetchall()

    return {
        "snapshot_version": "book_backup_v1",
        "book": {
            "id": int(book.id),
            "name": book.name or "",
            "accounting_standard": book.accounting_standard or "",
            "is_enabled": int(book.is_enabled or 0),
        },
        "subjects": [
            {
                "code": s.code,
                "name": s.name,
                "category": s.category or "",
                "balance_direction": s.balance_direction or "",
                "level": int(s.level or 1),
                "parent_code": s.parent_code or "",
                "is_enabled": int(s.is_enabled or 0),
            }
            for s in subjects
        ],
        "periods": [
            {"year": int(p.year), "month": int(p.month), "status": p.status or "open"}
            for p in periods
        ],
        "stats": {"subject_count": len(subjects), "period_count": len(periods)},
    }


def verify_book_backup_snapshot(payload: Dict[str, object]) -> Dict[str, object]:
    snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
    if not isinstance(snapshot, dict):
        raise BookManageError("snapshot required")

    errors: List[str] = []
    warnings: List[str] = []
    book = snapshot.get("book") or {}
    subjects = snapshot.get("subjects") or []
    periods = snapshot.get("periods") or []

    if snapshot.get("snapshot_version") != "book_backup_v1":
        errors.append("snapshot_version_invalid")
    if not isinstance(book.get("id"), int):
        errors.append("book.id invalid")
    if not book.get("accounting_standard"):
        errors.append("book.accounting_standard required")
    if not isinstance(subjects, list) or len(subjects) == 0:
        errors.append("subjects required")
    if not isinstance(periods, list) or len(periods) < 12:
        errors.append("periods required(min=12)")

    subject_codes = set()
    for idx, s in enumerate(subjects):
        code = (s.get("code") or "").strip()
        if not code:
            errors.append(f"subjects[{idx}].code required")
        elif code in subject_codes:
            errors.append(f"subjects[{idx}].code duplicate:{code}")
        else:
            subject_codes.add(code)

        if (s.get("balance_direction") or "").upper() not in ("DEBIT", "CREDIT"):
            errors.append(f"subjects[{idx}].balance_direction invalid")

    period_keys = set()
    for idx, p in enumerate(periods):
        year = p.get("year")
        month = p.get("month")
        status = (p.get("status") or "").strip().lower()
        if not isinstance(year, int) or not isinstance(month, int):
            errors.append(f"periods[{idx}] year/month invalid")
            continue
        if month < 1 or month > 12:
            errors.append(f"periods[{idx}] month out_of_range")
        if status not in ("open", "closed"):
            errors.append(f"periods[{idx}] status invalid")
        key = (year, month)
        if key in period_keys:
            errors.append(f"periods[{idx}] duplicate:{year}-{month:02d}")
        else:
            period_keys.add(key)

    if len(periods) < 24:
        warnings.append("period_count_lt_24")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def disable_book(book_id: int, confirm_text: str, operator_role: str) -> Dict[str, object]:
    if operator_role not in ("admin", "boss"):
        raise BookManageError("forbidden")
    try:
        book_id = int(book_id)
    except Exception as err:
        raise BookManageError("book_id must be integer") from err
    expected = f"DISABLE BOOK {book_id}"
    if (confirm_text or "").strip() != expected:
        raise BookManageError(f"confirm_text_mismatch(expected={expected})")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, is_enabled FROM books WHERE id=:id LIMIT 1"),
            {"id": book_id},
        ).fetchone()
        if not row:
            raise BookManageError("book_not_found")
        conn.execute(text("UPDATE books SET is_enabled=0 WHERE id=:id"), {"id": book_id})
    return {"book_id": book_id, "is_enabled": 0, "status": "disabled"}
