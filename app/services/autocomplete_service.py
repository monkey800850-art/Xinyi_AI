from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class AutocompleteError(RuntimeError):
    pass


TYPE_TABLES = {
    "subject": "subjects",
    "entity": "entities",
    "project": "projects",
    "person": "persons",
    "department": "departments",
}


def _validate_params(params: Dict[str, str]) -> Dict[str, object]:
    ac_type = (params.get("type") or "").strip()
    q = (params.get("q") or "").strip()
    book_id_raw = (params.get("book_id") or "").strip()

    missing = []
    if not ac_type:
        missing.append("type")
    if not q:
        missing.append("q")
    if not book_id_raw:
        missing.append("book_id")

    if missing:
        raise AutocompleteError("Missing required fields: " + ", ".join(missing))

    if ac_type not in TYPE_TABLES:
        raise AutocompleteError("unsupported autocomplete type")

    try:
        book_id = int(book_id_raw)
    except ValueError as err:
        raise AutocompleteError("book_id must be integer") from err

    limit_raw = (params.get("limit") or "").strip()
    if not limit_raw:
        limit = 20
    else:
        try:
            limit = int(limit_raw)
        except ValueError as err:
            raise AutocompleteError("limit must be integer") from err

    if limit > 50:
        limit = 50
    if limit <= 0:
        limit = 20

    return {"type": ac_type, "q": q, "book_id": book_id, "limit": limit}


def autocomplete(params: Dict[str, str]) -> List[Dict[str, object]]:
    validated = _validate_params(params)
    ac_type = validated["type"]
    q = validated["q"]
    book_id = validated["book_id"]
    limit = validated["limit"]

    if not q:
        return []

    table = TYPE_TABLES[ac_type]

    # Priority: code prefix -> code contains -> name contains
    sql = f"""
        SELECT id, code, name,
               CASE
                 WHEN code LIKE :prefix THEN 1
                 WHEN code LIKE :contains THEN 2
                 WHEN name LIKE :contains THEN 3
                 ELSE 4
               END AS match_rank
        FROM {table}
        WHERE book_id = :book_id
          AND is_enabled = 1
          AND (
            code LIKE :prefix
            OR code LIKE :contains
            OR name LIKE :contains
          )
        ORDER BY match_rank ASC, code ASC
        LIMIT :limit
    """

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(sql),
            {
                "book_id": book_id,
                "prefix": f"{q}%",
                "contains": f"%{q}%",
                "limit": limit,
            },
        ).fetchall()

    result = []
    for row in rows:
        result.append(
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "display_text": f"{row.code} {row.name}",
                "type": ac_type,
            }
        )

    return result
