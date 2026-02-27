from datetime import date
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class AssetChangeError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    if not value:
        raise ValueError("invalid_date")
    return date.fromisoformat(str(value))


def create_change(asset_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    change_type = (payload.get("change_type") or "").strip().upper()
    change_date_raw = payload.get("change_date")
    to_department_id = payload.get("to_department_id")
    to_person_id = payload.get("to_person_id")
    note = (payload.get("note") or "").strip()
    operator = (payload.get("operator") or "").strip() or "system"

    _require(change_type in ("DISPOSAL", "SCRAP", "TRANSFER"), errors, "change_type", "非法")
    _require(change_date_raw, errors, "change_date", "必填")

    if errors:
        raise AssetChangeError("validation_error", errors)

    try:
        change_date = _parse_date(change_date_raw)
        to_department_id = int(to_department_id) if to_department_id not in (None, "") else None
        to_person_id = int(to_person_id) if to_person_id not in (None, "") else None
    except Exception:
        raise AssetChangeError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        asset = conn.execute(
            text(
                """
                SELECT id, book_id, asset_code, status, department_id, person_id
                FROM fixed_assets
                WHERE id=:id
                """
            ),
            {"id": asset_id},
        ).fetchone()

        if not asset:
            raise AssetChangeError("not_found")

        if asset.status != "ACTIVE":
            raise AssetChangeError("validation_error", [{"field": "status", "message": "仅ACTIVE资产可变动"}])

        from_department_id = asset.department_id
        from_person_id = asset.person_id

        if change_type == "TRANSFER":
            if to_department_id is None and to_person_id is None:
                raise AssetChangeError("validation_error", [{"field": "to_department_id", "message": "转移目标不能为空"}])
            conn.execute(
                text(
                    """
                    UPDATE fixed_assets
                    SET department_id=:to_department_id,
                        person_id=:to_person_id,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": asset_id,
                    "to_department_id": to_department_id,
                    "to_person_id": to_person_id,
                },
            )
        elif change_type == "DISPOSAL":
            conn.execute(
                text("UPDATE fixed_assets SET status='DISPOSED', updated_at=NOW() WHERE id=:id"),
                {"id": asset_id},
            )
        elif change_type == "SCRAP":
            conn.execute(
                text("UPDATE fixed_assets SET status='SCRAPPED', updated_at=NOW() WHERE id=:id"),
                {"id": asset_id},
            )

        result = conn.execute(
            text(
                """
                INSERT INTO asset_changes (
                    book_id, asset_id, asset_code, change_type, change_date,
                    from_department_id, to_department_id, from_person_id, to_person_id,
                    note, operator
                ) VALUES (
                    :book_id, :asset_id, :asset_code, :change_type, :change_date,
                    :from_department_id, :to_department_id, :from_person_id, :to_person_id,
                    :note, :operator
                )
                """
            ),
            {
                "book_id": asset.book_id,
                "asset_id": asset.id,
                "asset_code": asset.asset_code,
                "change_type": change_type,
                "change_date": change_date,
                "from_department_id": from_department_id,
                "to_department_id": to_department_id,
                "from_person_id": from_person_id,
                "to_person_id": to_person_id,
                "note": note,
                "operator": operator,
            },
        )
        change_id = result.lastrowid

    # audit hook placeholder
    return {"id": change_id, "asset_id": asset_id, "change_type": change_type}


def list_changes(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise AssetChangeError("validation_error", [{"field": "book_id", "message": "必填"}])

    change_type = (params.get("change_type") or "").strip().upper()
    start_date_raw = (params.get("start_date") or "").strip()
    end_date_raw = (params.get("end_date") or "").strip()

    try:
        book_id = int(book_id_raw)
        start_date = _parse_date(start_date_raw) if start_date_raw else None
        end_date = _parse_date(end_date_raw) if end_date_raw else None
    except Exception:
        raise AssetChangeError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    sql = (
        "SELECT id, asset_id, asset_code, change_type, change_date, "
        "from_department_id, to_department_id, from_person_id, to_person_id, note, operator "
        "FROM asset_changes WHERE book_id=:book_id"
    )
    params_sql = {"book_id": book_id}

    if change_type:
        sql += " AND change_type=:change_type"
        params_sql["change_type"] = change_type
    if start_date:
        sql += " AND change_date >= :start_date"
        params_sql["start_date"] = start_date
    if end_date:
        sql += " AND change_date <= :end_date"
        params_sql["end_date"] = end_date

    sql += " ORDER BY change_date DESC, id DESC"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "asset_id": r.asset_id,
                "asset_code": r.asset_code,
                "change_type": r.change_type,
                "change_date": r.change_date.isoformat() if r.change_date else "",
                "from_department_id": r.from_department_id or "",
                "to_department_id": r.to_department_id or "",
                "from_person_id": r.from_person_id or "",
                "to_person_id": r.to_person_id or "",
                "note": r.note or "",
                "operator": r.operator or "",
            }
        )

    return {"book_id": book_id, "items": items}
