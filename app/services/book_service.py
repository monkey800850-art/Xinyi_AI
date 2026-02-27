from typing import Dict

from sqlalchemy import text

from app.db import get_engine
from app.services.standard_importer import StandardImportError, import_subjects_from_standard


class BookCreateError(RuntimeError):
    pass


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

    return {
        "book_id": book_id,
        "accounting_standard": accounting_standard,
        "subject_init_result": init_result,
    }
