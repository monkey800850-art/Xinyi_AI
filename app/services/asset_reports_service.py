from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import text

from app.db import get_engine


class AssetReportError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] = None):
        super().__init__(message)
        self.errors = errors or []


def _require(cond: bool, errors: List[Dict[str, object]], field: str, msg: str):
    if not cond:
        errors.append({"field": field, "message": msg})


def _parse_int(value, field: str):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        raise AssetReportError("validation_error", [{"field": field, "message": "格式非法"}])


def _parse_date(value, field: str) -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        raise AssetReportError("validation_error", [{"field": field, "message": "格式非法"}])


def _period_to_date(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - date.resolution


def get_asset_ledger(params: Dict[str, str]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    book_id_raw = (params.get("book_id") or "").strip()

    _require(book_id_raw, errors, "book_id", "必填")
    if errors:
        raise AssetReportError("validation_error", errors)

    book_id = _parse_int(book_id_raw, "book_id")
    asset_code = (params.get("asset_code") or "").strip()
    asset_name = (params.get("asset_name") or "").strip()
    category_id = _parse_int(params.get("category_id"), "category_id")
    status = (params.get("status") or "").strip().upper()
    department_id = _parse_int(params.get("department_id"), "department_id")
    start_use_from = _parse_date(params.get("start_use_from"), "start_use_from")
    start_use_to = _parse_date(params.get("start_use_to"), "start_use_to")
    dep_year = _parse_int(params.get("dep_year"), "dep_year")
    dep_month = _parse_int(params.get("dep_month"), "dep_month")

    dep_end_date = None
    if dep_year and dep_month:
        if dep_month < 1 or dep_month > 12:
            raise AssetReportError("validation_error", [{"field": "dep_month", "message": "月份非法"}])
        dep_end_date = _period_to_date(dep_year, dep_month)

    sql = (
        "SELECT fa.id, fa.asset_code, fa.asset_name, fa.original_value, fa.status, "
        "fa.start_use_date, fa.department_id, ac.name AS category_name, d.name AS department_name, "
        "COALESCE(SUM(dl.monthly_amount), 0) AS accum_depr "
        "FROM fixed_assets fa "
        "JOIN asset_categories ac ON ac.id = fa.category_id "
        "LEFT JOIN departments d ON d.id = fa.department_id "
        "LEFT JOIN depreciation_lines dl ON dl.asset_id = fa.id "
        "LEFT JOIN depreciation_batches db ON db.id = dl.batch_id "
        "WHERE fa.book_id=:book_id"
    )
    params_sql: Dict[str, object] = {"book_id": book_id}

    if asset_code:
        sql += " AND fa.asset_code LIKE :asset_code"
        params_sql["asset_code"] = f"%{asset_code}%"
    if asset_name:
        sql += " AND fa.asset_name LIKE :asset_name"
        params_sql["asset_name"] = f"%{asset_name}%"
    if category_id:
        sql += " AND fa.category_id=:category_id"
        params_sql["category_id"] = category_id
    if status:
        sql += " AND fa.status=:status"
        params_sql["status"] = status
    if department_id:
        sql += " AND fa.department_id=:department_id"
        params_sql["department_id"] = department_id
    if start_use_from:
        sql += " AND fa.start_use_date >= :start_use_from"
        params_sql["start_use_from"] = start_use_from
    if start_use_to:
        sql += " AND fa.start_use_date <= :start_use_to"
        params_sql["start_use_to"] = start_use_to
    if dep_end_date:
        sql += " AND (db.period_year < :dep_year OR (db.period_year = :dep_year AND db.period_month <= :dep_month))"
        params_sql["dep_year"] = dep_year
        params_sql["dep_month"] = dep_month

    sql += " GROUP BY fa.id ORDER BY fa.asset_code ASC"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items = []
    for r in rows:
        accum = float(r.accum_depr or 0)
        original = float(r.original_value or 0)
        items.append(
            {
                "asset_code": r.asset_code,
                "asset_name": r.asset_name,
                "category_name": r.category_name,
                "original_value": original,
                "accumulated_depr": accum,
                "net_value": original - accum,
                "status": r.status,
                "department_name": r.department_name or "",
                "start_use_date": r.start_use_date.isoformat() if r.start_use_date else "",
            }
        )

    return {"book_id": book_id, "items": items}


def get_depreciation_detail(params: Dict[str, str]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    book_id_raw = (params.get("book_id") or "").strip()
    year_raw = (params.get("year") or "").strip()
    month_raw = (params.get("month") or "").strip()

    _require(book_id_raw, errors, "book_id", "必填")
    _require(year_raw, errors, "year", "必填")
    _require(month_raw, errors, "month", "必填")
    if errors:
        raise AssetReportError("validation_error", errors)

    book_id = _parse_int(book_id_raw, "book_id")
    year = _parse_int(year_raw, "year")
    month = _parse_int(month_raw, "month")
    if month < 1 or month > 12:
        raise AssetReportError("validation_error", [{"field": "month", "message": "月份非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT dl.asset_code, dl.asset_name, dl.monthly_amount,
                       db.period_year, db.period_month, db.id AS batch_id, db.voucher_id
                FROM depreciation_lines dl
                JOIN depreciation_batches db ON db.id = dl.batch_id
                WHERE db.book_id=:book_id
                  AND db.period_year=:year AND db.period_month=:month
                ORDER BY dl.asset_code ASC
                """
            ),
            {"book_id": book_id, "year": year, "month": month},
        ).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "asset_code": r.asset_code,
                "asset_name": r.asset_name,
                "period": f"{r.period_year:04d}-{r.period_month:02d}",
                "amount": float(r.monthly_amount),
                "batch_id": r.batch_id,
                "voucher_id": r.voucher_id or "",
            }
        )

    return {"book_id": book_id, "period_year": year, "period_month": month, "items": items}


def get_depreciation_summary(params: Dict[str, str]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []
    book_id_raw = (params.get("book_id") or "").strip()
    year_raw = (params.get("year") or "").strip()
    month_raw = (params.get("month") or "").strip()

    _require(book_id_raw, errors, "book_id", "必填")
    _require(year_raw, errors, "year", "必填")
    _require(month_raw, errors, "month", "必填")
    if errors:
        raise AssetReportError("validation_error", errors)

    book_id = _parse_int(book_id_raw, "book_id")
    year = _parse_int(year_raw, "year")
    month = _parse_int(month_raw, "month")
    if month < 1 or month > 12:
        raise AssetReportError("validation_error", [{"field": "month", "message": "月份非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        by_category = conn.execute(
            text(
                """
                SELECT ac.name AS category_name, SUM(dl.monthly_amount) AS total_amount
                FROM depreciation_lines dl
                JOIN depreciation_batches db ON db.id = dl.batch_id
                JOIN asset_categories ac ON ac.id = dl.category_id
                WHERE db.book_id=:book_id AND db.period_year=:year AND db.period_month=:month
                GROUP BY ac.name
                ORDER BY ac.name ASC
                """
            ),
            {"book_id": book_id, "year": year, "month": month},
        ).fetchall()

        by_department = conn.execute(
            text(
                """
                SELECT d.name AS department_name, SUM(dl.monthly_amount) AS total_amount
                FROM depreciation_lines dl
                JOIN depreciation_batches db ON db.id = dl.batch_id
                JOIN fixed_assets fa ON fa.id = dl.asset_id
                LEFT JOIN departments d ON d.id = fa.department_id
                WHERE db.book_id=:book_id AND db.period_year=:year AND db.period_month=:month
                GROUP BY d.name
                ORDER BY d.name ASC
                """
            ),
            {"book_id": book_id, "year": year, "month": month},
        ).fetchall()

    category_items = [
        {"category_name": r.category_name, "total_amount": float(r.total_amount)} for r in by_category
    ]
    department_items = [
        {"department_name": r.department_name or "未分配", "total_amount": float(r.total_amount)}
        for r in by_department
    ]

    return {
        "book_id": book_id,
        "period_year": year,
        "period_month": month,
        "by_category": category_items,
        "by_department": department_items,
    }
