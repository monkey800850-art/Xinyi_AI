from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class AssetError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


def _parse_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid_decimal")


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def _parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def create_category(payload: Dict[str, object]) -> Dict[str, object]:
    book_id = payload.get("book_id")
    code = (payload.get("code") or "").strip()
    name = (payload.get("name") or "").strip()
    depreciation_method = (payload.get("depreciation_method") or "STRAIGHT_LINE").strip()
    default_useful_life_months = payload.get("default_useful_life_months", 0)
    default_residual_rate = payload.get("default_residual_rate", 0)
    expense_subject_code = (payload.get("expense_subject_code") or "").strip() or None
    accumulated_depr_subject_code = (payload.get("accumulated_depr_subject_code") or "").strip() or None

    if not book_id or not code or not name:
        raise AssetError("validation_error", [{"field": "book_id/code/name", "message": "必填"}])

    try:
        book_id = int(book_id)
        default_useful_life_months = int(default_useful_life_months or 0)
        default_residual_rate = _parse_decimal(default_residual_rate)
    except Exception:
        raise AssetError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    if default_useful_life_months <= 0:
        raise AssetError("validation_error", [{"field": "default_useful_life_months", "message": "使用年限必须>0"}])
    if default_residual_rate < 0 or default_residual_rate > 100:
        raise AssetError("validation_error", [{"field": "default_residual_rate", "message": "残值率范围0~100"}])

    engine = get_engine()
    with engine.begin() as conn:
        dup = conn.execute(
            text("SELECT id FROM asset_categories WHERE book_id=:book_id AND code=:code"),
            {"book_id": book_id, "code": code},
        ).fetchone()
        if dup:
            raise AssetError("validation_error", [{"field": "code", "message": "类别编码已存在"}])
        result = conn.execute(
            text(
                """
                INSERT INTO asset_categories (
                    book_id, code, name, depreciation_method, default_useful_life_months,
                    default_residual_rate, expense_subject_code, accumulated_depr_subject_code, is_enabled
                ) VALUES (
                    :book_id, :code, :name, :depreciation_method, :default_useful_life_months,
                    :default_residual_rate, :expense_subject_code, :accumulated_depr_subject_code, 1
                )
                """
            ),
            {
                "book_id": book_id,
                "code": code,
                "name": name,
                "depreciation_method": depreciation_method,
                "default_useful_life_months": default_useful_life_months,
                "default_residual_rate": default_residual_rate,
                "expense_subject_code": expense_subject_code,
                "accumulated_depr_subject_code": accumulated_depr_subject_code,
            },
        )
        category_id = result.lastrowid

    # audit hook placeholder
    return {"id": category_id}


def update_category(category_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    name = (payload.get("name") or "").strip()
    depreciation_method = (payload.get("depreciation_method") or "STRAIGHT_LINE").strip()
    default_useful_life_months = payload.get("default_useful_life_months", 0)
    default_residual_rate = payload.get("default_residual_rate", 0)
    expense_subject_code = (payload.get("expense_subject_code") or "").strip() or None
    accumulated_depr_subject_code = (payload.get("accumulated_depr_subject_code") or "").strip() or None

    if not name:
        raise AssetError("validation_error", [{"field": "name", "message": "必填"}])

    try:
        default_useful_life_months = int(default_useful_life_months or 0)
        default_residual_rate = _parse_decimal(default_residual_rate)
    except Exception:
        raise AssetError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    if default_useful_life_months <= 0:
        raise AssetError("validation_error", [{"field": "default_useful_life_months", "message": "使用年限必须>0"}])
    if default_residual_rate < 0 or default_residual_rate > 100:
        raise AssetError("validation_error", [{"field": "default_residual_rate", "message": "残值率范围0~100"}])

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE asset_categories
                SET name=:name, depreciation_method=:depreciation_method,
                    default_useful_life_months=:default_useful_life_months,
                    default_residual_rate=:default_residual_rate,
                    expense_subject_code=:expense_subject_code,
                    accumulated_depr_subject_code=:accumulated_depr_subject_code,
                    updated_at=NOW()
                WHERE id=:id
                """
            ),
            {
                "id": category_id,
                "name": name,
                "depreciation_method": depreciation_method,
                "default_useful_life_months": default_useful_life_months,
                "default_residual_rate": default_residual_rate,
                "expense_subject_code": expense_subject_code,
                "accumulated_depr_subject_code": accumulated_depr_subject_code,
            },
        )

    # audit hook placeholder
    return {"id": category_id}


def set_category_enabled(category_id: int, is_enabled: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE asset_categories SET is_enabled=:v WHERE id=:id"),
            {"id": category_id, "v": 1 if is_enabled else 0},
        )

    # audit hook placeholder
    return {"id": category_id, "is_enabled": 1 if is_enabled else 0}


def list_categories(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise AssetError("validation_error", [{"field": "book_id", "message": "必填"}])
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise AssetError("validation_error", [{"field": "book_id", "message": "格式非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, book_id, code, name, depreciation_method,
                       default_useful_life_months, default_residual_rate,
                       expense_subject_code, accumulated_depr_subject_code, is_enabled
                FROM asset_categories
                WHERE book_id=:book_id
                ORDER BY code ASC
                """
            ),
            {"book_id": book_id},
        ).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "book_id": r.book_id,
                "code": r.code,
                "name": r.name,
                "depreciation_method": r.depreciation_method,
                "default_useful_life_months": r.default_useful_life_months,
                "default_residual_rate": float(r.default_residual_rate),
                "expense_subject_code": r.expense_subject_code or "",
                "accumulated_depr_subject_code": r.accumulated_depr_subject_code or "",
                "is_enabled": int(r.is_enabled),
            }
        )

    return {"book_id": book_id, "items": items}


def create_asset(payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id = payload.get("book_id")
    asset_code = (payload.get("asset_code") or "").strip()
    asset_name = (payload.get("asset_name") or "").strip()
    category_id = payload.get("category_id")
    specification_model = (payload.get("specification_model") or "").strip()
    unit = (payload.get("unit") or "").strip()
    quantity = payload.get("quantity", 1)
    location = (payload.get("location") or "").strip()
    purchase_date = payload.get("purchase_date")
    original_value = payload.get("original_value")
    residual_rate = payload.get("residual_rate", 0)
    residual_value = payload.get("residual_value", 0)
    useful_life_months = payload.get("useful_life_months")
    depreciation_method = (payload.get("depreciation_method") or "STRAIGHT_LINE").strip()
    start_use_date = payload.get("start_use_date")
    capitalization_date = payload.get("capitalization_date")
    is_depreciable = payload.get("is_depreciable", 1)
    department_id = payload.get("department_id")
    person_id = payload.get("person_id")
    note = (payload.get("note") or "").strip()
    status = (payload.get("status") or "DRAFT").strip()
    is_enabled = payload.get("is_enabled", 1)

    _require(book_id is not None, errors, "book_id", "必填")
    _require(asset_code, errors, "asset_code", "必填")
    _require(asset_name, errors, "asset_name", "必填")
    _require(category_id is not None, errors, "category_id", "必填")
    _require(original_value is not None, errors, "original_value", "必填")
    if is_depreciable in (1, "1", True):
        _require(useful_life_months is not None, errors, "useful_life_months", "必填")

    if errors:
        raise AssetError("validation_error", errors)

    try:
        book_id = int(book_id)
        category_id = int(category_id)
        original_value = _parse_decimal(original_value)
        residual_rate = _parse_decimal(residual_rate)
        residual_value = _parse_decimal(residual_value)
        useful_life_months = int(useful_life_months or 0)
        quantity = _parse_decimal(quantity)
        is_depreciable = 1 if int(is_depreciable) == 1 else 0
        is_enabled = 1 if int(is_enabled) == 1 else 0
        department_id = int(department_id) if department_id not in (None, "") else None
        person_id = int(person_id) if person_id not in (None, "") else None
        purchase_date = _parse_date(purchase_date)
        start_use_date = _parse_date(start_use_date)
        capitalization_date = _parse_date(capitalization_date)
    except Exception:
        raise AssetError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    if original_value < 0:
        raise AssetError("validation_error", [{"field": "original_value", "message": "原值必须>=0"}])
    if quantity <= 0:
        raise AssetError("validation_error", [{"field": "quantity", "message": "数量必须>0"}])
    if is_depreciable == 1 and useful_life_months <= 0:
        raise AssetError("validation_error", [{"field": "useful_life_months", "message": "使用年限必须>0"}])
    if residual_rate < 0 or residual_rate > 100:
        raise AssetError("validation_error", [{"field": "residual_rate", "message": "残值率范围0~100"}])
    if status not in ("DRAFT", "ACTIVE", "IDLE", "PENDING_SCRAP", "DISPOSED", "SCRAPPED"):
        raise AssetError("validation_error", [{"field": "status", "message": "状态非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        dup = conn.execute(
            text("SELECT id FROM fixed_assets WHERE book_id=:book_id AND asset_code=:code"),
            {"book_id": book_id, "code": asset_code},
        ).fetchone()
        if dup:
            raise AssetError("validation_error", [{"field": "asset_code", "message": "资产编号已存在"}])

        cat = conn.execute(
            text(
                """
                SELECT id, is_enabled, depreciation_method,
                       default_useful_life_months, default_residual_rate
                FROM asset_categories WHERE id=:id AND book_id=:book_id
                """
            ),
            {"id": category_id, "book_id": book_id},
        ).fetchone()
        if not cat:
            raise AssetError("validation_error", [{"field": "category_id", "message": "类别不存在"}])
        if cat.is_enabled != 1:
            raise AssetError("validation_error", [{"field": "category_id", "message": "类别已停用"}])

        if is_depreciable == 1:
            if not depreciation_method:
                depreciation_method = cat.depreciation_method or "STRAIGHT_LINE"
            if useful_life_months <= 0:
                useful_life_months = int(cat.default_useful_life_months or 0)
            if residual_rate == 0:
                residual_rate = _parse_decimal(cat.default_residual_rate)

        if purchase_date and capitalization_date and capitalization_date < purchase_date:
            raise AssetError("validation_error", [{"field": "capitalization_date", "message": "入账日期不能早于购置日期"}])
        if purchase_date and start_use_date and start_use_date < purchase_date:
            raise AssetError("validation_error", [{"field": "start_use_date", "message": "启用日期不能早于购置日期"}])

        result = conn.execute(
            text(
                """
                INSERT INTO fixed_assets (
                    book_id, asset_code, asset_name, category_id, status,
                    original_value, residual_rate, residual_value, useful_life_months,
                    depreciation_method, start_use_date, capitalization_date,
                    department_id, person_id, note, is_enabled,
                    specification_model, unit, quantity, location, purchase_date, is_depreciable
                ) VALUES (
                    :book_id, :asset_code, :asset_name, :category_id, :status,
                    :original_value, :residual_rate, :residual_value, :useful_life_months,
                    :depreciation_method, :start_use_date, :capitalization_date,
                    :department_id, :person_id, :note, :is_enabled,
                    :specification_model, :unit, :quantity, :location, :purchase_date, :is_depreciable
                )
                """
            ),
            {
                "book_id": book_id,
                "asset_code": asset_code,
                "asset_name": asset_name,
                "category_id": category_id,
                "status": status or "DRAFT",
                "original_value": original_value,
                "residual_rate": residual_rate,
                "residual_value": residual_value,
                "useful_life_months": useful_life_months,
                "depreciation_method": depreciation_method,
                "start_use_date": start_use_date or None,
                "capitalization_date": capitalization_date or None,
                "department_id": department_id,
                "person_id": person_id,
                "note": note,
                "is_enabled": is_enabled,
                "specification_model": specification_model or None,
                "unit": unit or None,
                "quantity": quantity,
                "location": location or None,
                "purchase_date": purchase_date or None,
                "is_depreciable": is_depreciable,
            },
        )
        asset_id = result.lastrowid

    # audit hook placeholder
    return {"id": asset_id}


def update_asset(asset_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    asset_name = (payload.get("asset_name") or "").strip()
    category_id = payload.get("category_id")
    specification_model = (payload.get("specification_model") or "").strip()
    unit = (payload.get("unit") or "").strip()
    quantity = payload.get("quantity", 1)
    location = (payload.get("location") or "").strip()
    purchase_date = payload.get("purchase_date")
    original_value = payload.get("original_value")
    residual_rate = payload.get("residual_rate", 0)
    residual_value = payload.get("residual_value", 0)
    useful_life_months = payload.get("useful_life_months")
    depreciation_method = (payload.get("depreciation_method") or "STRAIGHT_LINE").strip()
    start_use_date = payload.get("start_use_date")
    capitalization_date = payload.get("capitalization_date")
    is_depreciable = payload.get("is_depreciable", 1)
    department_id = payload.get("department_id")
    person_id = payload.get("person_id")
    note = (payload.get("note") or "").strip()
    status = (payload.get("status") or "DRAFT").strip()
    is_enabled = payload.get("is_enabled")

    _require(asset_name, errors, "asset_name", "必填")
    _require(category_id is not None, errors, "category_id", "必填")
    _require(original_value is not None, errors, "original_value", "必填")
    if is_depreciable in (1, "1", True):
        _require(useful_life_months is not None, errors, "useful_life_months", "必填")

    if errors:
        raise AssetError("validation_error", errors)

    try:
        category_id = int(category_id)
        original_value = _parse_decimal(original_value)
        residual_rate = _parse_decimal(residual_rate)
        residual_value = _parse_decimal(residual_value)
        useful_life_months = int(useful_life_months or 0)
        quantity = _parse_decimal(quantity)
        is_depreciable = 1 if int(is_depreciable) == 1 else 0
        if is_enabled is not None:
            is_enabled = 1 if int(is_enabled) == 1 else 0
        department_id = int(department_id) if department_id not in (None, "") else None
        person_id = int(person_id) if person_id not in (None, "") else None
        purchase_date = _parse_date(purchase_date)
        start_use_date = _parse_date(start_use_date)
        capitalization_date = _parse_date(capitalization_date)
    except Exception:
        raise AssetError("validation_error", [{"field": "fields", "message": "字段格式非法"}])

    if original_value < 0:
        raise AssetError("validation_error", [{"field": "original_value", "message": "原值必须>=0"}])
    if quantity <= 0:
        raise AssetError("validation_error", [{"field": "quantity", "message": "数量必须>0"}])
    if is_depreciable == 1 and useful_life_months <= 0:
        raise AssetError("validation_error", [{"field": "useful_life_months", "message": "使用年限必须>0"}])
    if residual_rate < 0 or residual_rate > 100:
        raise AssetError("validation_error", [{"field": "residual_rate", "message": "残值率范围0~100"}])
    if status not in ("DRAFT", "ACTIVE", "IDLE", "PENDING_SCRAP", "DISPOSED", "SCRAPPED"):
        raise AssetError("validation_error", [{"field": "status", "message": "状态非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT id FROM fixed_assets WHERE id=:id"),
            {"id": asset_id},
        ).fetchone()
        if not exists:
            raise AssetError("not_found")

        cat = conn.execute(
            text(
                """
                SELECT id, is_enabled, depreciation_method,
                       default_useful_life_months, default_residual_rate
                FROM asset_categories WHERE id=:id
                """
            ),
            {"id": category_id},
        ).fetchone()
        if not cat:
            raise AssetError("validation_error", [{"field": "category_id", "message": "类别不存在"}])
        if cat.is_enabled != 1:
            raise AssetError("validation_error", [{"field": "category_id", "message": "类别已停用"}])

        if is_depreciable == 1:
            if not depreciation_method:
                depreciation_method = cat.depreciation_method or "STRAIGHT_LINE"
            if useful_life_months <= 0:
                useful_life_months = int(cat.default_useful_life_months or 0)
            if residual_rate == 0:
                residual_rate = _parse_decimal(cat.default_residual_rate)

        if purchase_date and capitalization_date and capitalization_date < purchase_date:
            raise AssetError("validation_error", [{"field": "capitalization_date", "message": "入账日期不能早于购置日期"}])
        if purchase_date and start_use_date and start_use_date < purchase_date:
            raise AssetError("validation_error", [{"field": "start_use_date", "message": "启用日期不能早于购置日期"}])

        conn.execute(
            text(
                """
                UPDATE fixed_assets
                SET asset_name=:asset_name, category_id=:category_id, status=:status,
                    original_value=:original_value, residual_rate=:residual_rate,
                    residual_value=:residual_value, useful_life_months=:useful_life_months,
                    depreciation_method=:depreciation_method, start_use_date=:start_use_date,
                    capitalization_date=:capitalization_date, department_id=:department_id,
                    person_id=:person_id, note=:note,
                    specification_model=:specification_model, unit=:unit,
                    quantity=:quantity, location=:location, purchase_date=:purchase_date,
                    is_depreciable=:is_depreciable,
                    is_enabled=COALESCE(:is_enabled, is_enabled),
                    updated_at=NOW()
                WHERE id=:id
                """
            ),
            {
                "id": asset_id,
                "asset_name": asset_name,
                "category_id": category_id,
                "status": status or "DRAFT",
                "original_value": original_value,
                "residual_rate": residual_rate,
                "residual_value": residual_value,
                "useful_life_months": useful_life_months,
                "depreciation_method": depreciation_method,
                "start_use_date": start_use_date or None,
                "capitalization_date": capitalization_date or None,
                "department_id": department_id,
                "person_id": person_id,
                "note": note,
                "specification_model": specification_model or None,
                "unit": unit or None,
                "quantity": quantity,
                "location": location or None,
                "purchase_date": purchase_date or None,
                "is_depreciable": is_depreciable,
                "is_enabled": is_enabled,
            },
        )

    # audit hook placeholder
    return {"id": asset_id}


def set_asset_enabled(asset_id: int, is_enabled: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE fixed_assets SET is_enabled=:v WHERE id=:id"),
            {"id": asset_id, "v": 1 if is_enabled else 0},
        )

    # audit hook placeholder
    return {"id": asset_id, "is_enabled": 1 if is_enabled else 0}


def list_assets(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    keyword = (params.get("keyword") or "").strip()
    status = (params.get("status") or "").strip().upper()
    category_id_raw = (params.get("category_id") or "").strip()
    if not book_id_raw:
        raise AssetError("validation_error", [{"field": "book_id", "message": "必填"}])
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise AssetError("validation_error", [{"field": "book_id", "message": "格式非法"}])

    category_id = None
    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except Exception:
            raise AssetError("validation_error", [{"field": "category_id", "message": "格式非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT fa.id, fa.asset_code, fa.asset_name, fa.original_value,
                       fa.status, fa.is_enabled, ac.name AS category_name
                FROM fixed_assets fa
                JOIN asset_categories ac ON ac.id = fa.category_id
                WHERE fa.book_id=:book_id
                """
                + (" AND fa.category_id=:category_id" if category_id else "")
                + (" AND fa.status=:status" if status else "")
                + (" AND (fa.asset_code LIKE :kw OR fa.asset_name LIKE :kw)" if keyword else "")
                + " ORDER BY fa.asset_code ASC"
            ),
            {
                "book_id": book_id,
                "category_id": category_id,
                "status": status,
                "kw": f"%{keyword}%" if keyword else None,
            },
        ).fetchall()

    items: List[Dict[str, object]] = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "asset_code": r.asset_code,
                "asset_name": r.asset_name,
                "category_name": r.category_name,
                "original_value": float(r.original_value),
                "status": r.status,
                "is_enabled": int(r.is_enabled),
            }
        )

    return {"book_id": book_id, "items": items}


def get_asset_detail(asset_id: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT fa.*, ac.name AS category_name
                FROM fixed_assets fa
                JOIN asset_categories ac ON ac.id = fa.category_id
                WHERE fa.id=:id
                """
            ),
            {"id": asset_id},
        ).fetchone()

    if not row:
        raise AssetError("not_found")

    return {
        "id": row.id,
        "book_id": row.book_id,
        "asset_code": row.asset_code,
        "asset_name": row.asset_name,
        "category_id": row.category_id,
        "category_name": row.category_name,
        "status": row.status,
        "specification_model": row.specification_model or "",
        "unit": row.unit or "",
        "quantity": float(row.quantity) if row.quantity is not None else 1,
        "location": row.location or "",
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else "",
        "original_value": float(row.original_value),
        "residual_rate": float(row.residual_rate),
        "residual_value": float(row.residual_value),
        "useful_life_months": row.useful_life_months,
        "depreciation_method": row.depreciation_method,
        "start_use_date": row.start_use_date.isoformat() if row.start_use_date else "",
        "capitalization_date": row.capitalization_date.isoformat() if row.capitalization_date else "",
        "department_id": row.department_id or "",
        "person_id": row.person_id or "",
        "note": row.note or "",
        "is_enabled": int(row.is_enabled),
        "is_depreciable": int(row.is_depreciable) if row.is_depreciable is not None else 1,
    }


def _as_decimal(value) -> Decimal:
    return _parse_decimal(value if value is not None else "0")


def _as_iso_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value)


def _db_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _db_params(values: Dict[str, object]) -> Dict[str, object]:
    return {k: _db_value(v) for k, v in values.items()}


def _load_asset_row(conn, asset_id: int):
    return conn.execute(
        text(
            """
            SELECT id, book_id, asset_code, asset_name, status, original_value, residual_value
            FROM fixed_assets
            WHERE id=:id
            """
        ),
        {"id": asset_id},
    ).fetchone()


def check_asset_impairment(asset_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    current_value = payload.get("current_value")
    reason = (payload.get("reason") or "").strip() or None
    evidence_ref = (payload.get("evidence_ref") or "").strip() or None

    if current_value in (None, ""):
        raise AssetError("validation_error", [{"field": "current_value", "message": "必填"}])
    try:
        current_value = _as_decimal(current_value)
    except Exception:
        raise AssetError("validation_error", [{"field": "current_value", "message": "格式非法"}])
    if current_value < 0:
        raise AssetError("validation_error", [{"field": "current_value", "message": "必须>=0"}])

    engine = get_engine()
    with engine.begin() as conn:
        asset = _load_asset_row(conn, asset_id)
        if not asset:
            raise AssetError("not_found")

        book_value = _as_decimal(asset.original_value) - _as_decimal(asset.residual_value)
        impairment_amount = book_value - current_value
        if impairment_amount < 0:
            impairment_amount = Decimal("0")

        row = conn.execute(
            text(
                """
                INSERT INTO asset_impairments (
                    asset_id, book_id, impairment_date, book_value, current_value, impairment_amount, reason, evidence_ref
                ) VALUES (
                    :asset_id, :book_id, :impairment_date, :book_value, :current_value, :impairment_amount, :reason, :evidence_ref
                )
                """
            ),
            _db_params(
                {
                "asset_id": asset_id,
                "book_id": int(asset.book_id),
                "impairment_date": _parse_date(payload.get("impairment_date")) or date.today(),
                "book_value": book_value,
                "current_value": current_value,
                "impairment_amount": impairment_amount,
                "reason": reason,
                "evidence_ref": evidence_ref,
                }
            ),
        )

    return {
        "id": int(row.lastrowid),
        "asset_id": int(asset_id),
        "book_id": int(asset.book_id),
        "book_value": float(book_value),
        "current_value": float(current_value),
        "impairment_amount": float(impairment_amount),
        "reason": reason or "",
        "evidence_ref": evidence_ref or "",
    }


def dispose_asset(asset_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    disposal_method = (payload.get("disposal_method") or "").strip().lower()
    if disposal_method not in ("sell", "scrap", "transfer"):
        raise AssetError("validation_error", [{"field": "disposal_method", "message": "仅支持 sell/scrap/transfer"}])

    disposal_income = _as_decimal(payload.get("disposal_income"))
    disposal_cost = _as_decimal(payload.get("disposal_cost"))
    note = (payload.get("note") or "").strip() or None

    engine = get_engine()
    with engine.begin() as conn:
        asset = _load_asset_row(conn, asset_id)
        if not asset:
            raise AssetError("not_found")

        book_value = _as_decimal(asset.original_value) - _as_decimal(asset.residual_value)
        gain_loss = disposal_income - disposal_cost - book_value
        post_status = "DISPOSED" if disposal_method in ("sell", "transfer") else "SCRAPPED"

        row = conn.execute(
            text(
                """
                INSERT INTO asset_disposals (
                    asset_id, book_id, disposal_date, disposal_method, disposal_income,
                    disposal_cost, book_value, gain_loss, note
                ) VALUES (
                    :asset_id, :book_id, :disposal_date, :disposal_method, :disposal_income,
                    :disposal_cost, :book_value, :gain_loss, :note
                )
                """
            ),
            _db_params(
                {
                "asset_id": int(asset_id),
                "book_id": int(asset.book_id),
                "disposal_date": _parse_date(payload.get("disposal_date")) or date.today(),
                "disposal_method": disposal_method,
                "disposal_income": disposal_income,
                "disposal_cost": disposal_cost,
                "book_value": book_value,
                "gain_loss": gain_loss,
                "note": note,
                }
            ),
        )

        conn.execute(
            text("UPDATE fixed_assets SET status=:status, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
            {"id": int(asset_id), "status": post_status},
        )

    return {
        "id": int(row.lastrowid),
        "asset_id": int(asset_id),
        "book_id": int(asset.book_id),
        "disposal_method": disposal_method,
        "disposal_income": float(disposal_income),
        "disposal_cost": float(disposal_cost),
        "book_value": float(book_value),
        "gain_loss": float(gain_loss),
        "status": post_status,
    }


def perform_inventory_check(payload: Dict[str, object]) -> Dict[str, object]:
    book_id = payload.get("book_id")
    asset_checks = payload.get("asset_checks")
    check_date = _parse_date(payload.get("check_date")) or date.today()
    note = (payload.get("note") or "").strip() or None

    if book_id in (None, ""):
        raise AssetError("validation_error", [{"field": "book_id", "message": "必填"}])
    if not isinstance(asset_checks, list) or not asset_checks:
        raise AssetError("validation_error", [{"field": "asset_checks", "message": "至少包含1条"}])
    try:
        book_id = int(book_id)
    except Exception:
        raise AssetError("validation_error", [{"field": "book_id", "message": "格式非法"}])

    engine = get_engine()
    with engine.begin() as conn:
        header = conn.execute(
            text(
                """
                INSERT INTO asset_inventory_checks (book_id, check_date, note)
                VALUES (:book_id, :check_date, :note)
                """
            ),
            _db_params({"book_id": book_id, "check_date": check_date, "note": note}),
        )
        check_id = int(header.lastrowid)
        discrepancies: List[Dict[str, object]] = []
        checked_count = 0

        for item in asset_checks:
            asset_id = item.get("asset_id")
            if asset_id in (None, ""):
                continue
            try:
                asset_id = int(asset_id)
                found = 1 if int(item.get("is_found", 1)) == 1 else 0
            except Exception:
                continue

            asset = _load_asset_row(conn, asset_id)
            if not asset or int(asset.book_id) != book_id:
                continue

            checked_count += 1
            discrepancy_reason = (item.get("discrepancy_reason") or "").strip() or None
            conn.execute(
                text(
                    """
                    INSERT INTO asset_inventory_check_lines (
                        check_id, asset_id, is_found, discrepancy_reason
                    ) VALUES (
                        :check_id, :asset_id, :is_found, :discrepancy_reason
                    )
                    """
                ),
                {
                    "check_id": check_id,
                    "asset_id": asset_id,
                    "is_found": found,
                    "discrepancy_reason": discrepancy_reason,
                },
            )
            if found == 0:
                discrepancies.append(
                    {
                        "asset_id": asset_id,
                        "asset_code": asset.asset_code,
                        "asset_name": asset.asset_name,
                        "reason": discrepancy_reason or "missing",
                    }
                )

    return {
        "check_id": check_id,
        "book_id": book_id,
        "check_date": _as_iso_date(check_date),
        "checked_count": checked_count,
        "discrepancy_count": len(discrepancies),
        "discrepancies": discrepancies,
    }


def revalue_asset(asset_id: int, payload: Dict[str, object]) -> Dict[str, object]:
    if payload.get("new_value") in (None, ""):
        raise AssetError("validation_error", [{"field": "new_value", "message": "必填"}])
    try:
        new_value = _as_decimal(payload.get("new_value"))
    except Exception:
        raise AssetError("validation_error", [{"field": "new_value", "message": "格式非法"}])
    if new_value < 0:
        raise AssetError("validation_error", [{"field": "new_value", "message": "必须>=0"}])
    reason = (payload.get("reason") or "").strip() or None

    engine = get_engine()
    with engine.begin() as conn:
        asset = _load_asset_row(conn, asset_id)
        if not asset:
            raise AssetError("not_found")

        old_value = _as_decimal(asset.original_value)
        delta = new_value - old_value
        row = conn.execute(
            text(
                """
                INSERT INTO asset_revaluations (
                    asset_id, book_id, revaluation_date, old_value, new_value, delta_amount, reason
                ) VALUES (
                    :asset_id, :book_id, :revaluation_date, :old_value, :new_value, :delta_amount, :reason
                )
                """
            ),
            _db_params(
                {
                "asset_id": int(asset_id),
                "book_id": int(asset.book_id),
                "revaluation_date": _parse_date(payload.get("revaluation_date")) or date.today(),
                "old_value": old_value,
                "new_value": new_value,
                "delta_amount": delta,
                "reason": reason,
                }
            ),
        )
        conn.execute(
            text("UPDATE fixed_assets SET original_value=:new_value, updated_at=CURRENT_TIMESTAMP WHERE id=:id"),
            _db_params({"id": int(asset_id), "new_value": new_value}),
        )

    return {
        "id": int(row.lastrowid),
        "asset_id": int(asset_id),
        "book_id": int(asset.book_id),
        "old_value": float(old_value),
        "new_value": float(new_value),
        "delta_amount": float(delta),
        "reason": reason or "",
    }


def generate_journal_entry(asset_id: int, action: str, payload: Dict[str, object]) -> Dict[str, object]:
    action = str(action or "").strip().lower()
    rule_code_map = {
        "impairment": "ASSET_IMPAIRMENT",
        "disposal": "ASSET_DISPOSAL",
        "inventory_check": "ASSET_INVENTORY_CHECK",
        "revaluation": "ASSET_REVALUATION",
    }
    if action not in rule_code_map:
        raise AssetError("validation_error", [{"field": "action", "message": "仅支持 impairment/disposal/inventory_check/revaluation"}])

    amount = _as_decimal(payload.get("amount"))
    if amount <= 0:
        amount = _as_decimal(payload.get("delta_amount"))
    if amount <= 0:
        amount = _as_decimal(payload.get("impairment_amount"))
    if amount <= 0:
        raise AssetError("validation_error", [{"field": "amount", "message": "必须>0"}])

    debit_subject_code = (payload.get("debit_subject_code") or "").strip()
    credit_subject_code = (payload.get("credit_subject_code") or "").strip()
    if not debit_subject_code or not credit_subject_code:
        raise AssetError("validation_error", [{"field": "subject_code", "message": "借贷科目必填"}])

    engine = get_engine()
    with engine.begin() as conn:
        asset = _load_asset_row(conn, asset_id)
        if not asset:
            raise AssetError("not_found")

        row = conn.execute(
            text(
                """
                INSERT INTO asset_journal_drafts (
                    asset_id, book_id, action, rule_code, reference_id, debit_subject_code,
                    credit_subject_code, amount, note
                ) VALUES (
                    :asset_id, :book_id, :action, :rule_code, :reference_id, :debit_subject_code,
                    :credit_subject_code, :amount, :note
                )
                """
            ),
            _db_params(
                {
                "asset_id": int(asset_id),
                "book_id": int(asset.book_id),
                "action": action,
                "rule_code": rule_code_map[action],
                "reference_id": payload.get("reference_id"),
                "debit_subject_code": debit_subject_code,
                "credit_subject_code": credit_subject_code,
                "amount": amount,
                "note": (payload.get("note") or "").strip() or None,
                }
            ),
        )

    return {
        "id": int(row.lastrowid),
        "asset_id": int(asset_id),
        "book_id": int(asset.book_id),
        "action": action,
        "rule_code": rule_code_map[action],
        "lines": [
            {"direction": "debit", "subject_code": debit_subject_code, "amount": float(amount)},
            {"direction": "credit", "subject_code": credit_subject_code, "amount": float(amount)},
        ],
    }
