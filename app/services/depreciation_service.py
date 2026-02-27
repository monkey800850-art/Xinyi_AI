from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Tuple

from sqlalchemy import bindparam, text

from app.db import get_engine
from app.services.voucher_service import VoucherValidationError, save_voucher


class DepreciationError(RuntimeError):
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


def _period_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    next_month = date(year, month + 1, 1)
    return next_month.replace(day=1) - date.resolution


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _load_assets(conn, book_id: int) -> List[Dict[str, object]]:
    rows = conn.execute(
        text(
            """
            SELECT fa.id, fa.book_id, fa.asset_code, fa.asset_name, fa.category_id,
                   fa.status, fa.is_enabled, fa.original_value, fa.residual_rate,
                   fa.residual_value, fa.useful_life_months, fa.depreciation_method,
                   fa.start_use_date, fa.capitalization_date,
                   ac.depreciation_method AS cat_method,
                   ac.expense_subject_code, ac.accumulated_depr_subject_code
            FROM fixed_assets fa
            JOIN asset_categories ac ON ac.id = fa.category_id
            WHERE fa.book_id=:book_id
              AND fa.is_enabled=1
              AND fa.status='ACTIVE'
            ORDER BY fa.asset_code ASC
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
                "asset_code": r.asset_code,
                "asset_name": r.asset_name,
                "category_id": r.category_id,
                "status": r.status,
                "is_enabled": r.is_enabled,
                "original_value": _parse_decimal(r.original_value),
                "residual_rate": _parse_decimal(r.residual_rate),
                "residual_value": _parse_decimal(r.residual_value),
                "useful_life_months": int(r.useful_life_months or 0),
                "depreciation_method": (r.depreciation_method or r.cat_method or "STRAIGHT_LINE"),
                "start_use_date": r.start_use_date,
                "capitalization_date": r.capitalization_date,
                "expense_subject_code": (r.expense_subject_code or "").strip(),
                "accumulated_depr_subject_code": (r.accumulated_depr_subject_code or "").strip(),
            }
        )

    return items


def _already_depreciated_months(conn, book_id: int, asset_id: int, year: int, month: int) -> int:
    row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM depreciation_lines dl
            JOIN depreciation_batches db ON db.id = dl.batch_id
            WHERE dl.asset_id=:asset_id
              AND db.book_id=:book_id
              AND dl.status='SUCCESS'
              AND (db.period_year < :year OR (db.period_year = :year AND db.period_month < :month))
            """
        ),
        {"asset_id": asset_id, "book_id": book_id, "year": year, "month": month},
    ).fetchone()
    return int(row.cnt or 0)


def _build_depreciation_lines(
    conn, book_id: int, year: int, month: int
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Decimal]:
    period_end = _period_end(year, month)
    assets = _load_assets(conn, book_id)

    items: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []
    total = Decimal("0")

    for asset in assets:
        if asset["depreciation_method"] != "STRAIGHT_LINE":
            errors.append(
                {
                    "asset_code": asset["asset_code"],
                    "message": "仅支持直线法",
                }
            )
            continue

        if not asset["expense_subject_code"] or not asset["accumulated_depr_subject_code"]:
            errors.append(
                {
                    "asset_code": asset["asset_code"],
                    "message": "缺少折旧费用科目或累计折旧科目",
                }
            )
            continue

        base_start_date = asset["capitalization_date"] or asset["start_use_date"]
        if not base_start_date:
            errors.append(
                {
                    "asset_code": asset["asset_code"],
                    "message": "缺少开始使用日期/入账日期",
                }
            )
            continue
        if base_start_date > period_end:
            continue

        original_value = asset["original_value"]
        residual_value = asset["residual_value"]
        residual_rate = asset["residual_rate"]
        useful_life_months = asset["useful_life_months"]

        if useful_life_months <= 0:
            errors.append(
                {
                    "asset_code": asset["asset_code"],
                    "message": "使用年限非法",
                }
            )
            continue

        if residual_value <= 0 and residual_rate > 0:
            residual_value = (original_value * residual_rate) / Decimal("100")
        if residual_value < 0:
            residual_value = Decimal("0")

        base_value = original_value - residual_value
        if base_value <= 0:
            errors.append(
                {
                    "asset_code": asset["asset_code"],
                    "message": "可折旧金额不足",
                }
            )
            continue

        already = _already_depreciated_months(conn, book_id, asset["id"], year, month)
        remaining = useful_life_months - already
        if remaining <= 0:
            continue

        monthly_raw = base_value / Decimal(str(useful_life_months))
        monthly = _quantize_amount(monthly_raw)
        if remaining == 1:
            amount = _quantize_amount(base_value - monthly * Decimal(already))
        else:
            amount = monthly

        if amount <= 0:
            continue

        total += amount
        items.append(
            {
                "asset_id": asset["id"],
                "asset_code": asset["asset_code"],
                "asset_name": asset["asset_name"],
                "category_id": asset["category_id"],
                "depreciation_method": asset["depreciation_method"],
                "original_value": original_value,
                "residual_rate": residual_rate,
                "residual_value": residual_value,
                "useful_life_months": useful_life_months,
                "monthly_amount": amount,
                "expense_subject_code": asset["expense_subject_code"],
                "accumulated_depr_subject_code": asset["accumulated_depr_subject_code"],
                "start_use_date": asset["start_use_date"],
                "capitalization_date": asset["capitalization_date"],
            }
        )

    return items, errors, total


def preview_depreciation(params: Dict[str, str]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id_raw = (params.get("book_id") or "").strip()
    year_raw = (params.get("year") or "").strip()
    month_raw = (params.get("month") or "").strip()

    _require(book_id_raw, errors, "book_id", "必填")
    _require(year_raw, errors, "year", "必填")
    _require(month_raw, errors, "month", "必填")

    if errors:
        raise DepreciationError("validation_error", errors)

    try:
        book_id = int(book_id_raw)
        year = int(year_raw)
        month = int(month_raw)
    except Exception:
        raise DepreciationError("validation_error", [{"field": "fields", "message": "格式非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        items, asset_errors, total = _build_depreciation_lines(conn, book_id, year, month)

    output_items = []
    for item in items:
        output_items.append(
            {
                "asset_id": item["asset_id"],
                "asset_code": item["asset_code"],
                "asset_name": item["asset_name"],
                "amount": float(_quantize_amount(item["monthly_amount"])),
                "status": "READY",
            }
        )

    return {
        "book_id": book_id,
        "period_year": year,
        "period_month": month,
        "method": "STRAIGHT_LINE",
        "total_amount": float(_quantize_amount(total)),
        "items": output_items,
        "errors": asset_errors,
    }


def run_depreciation(payload: Dict[str, object]) -> Dict[str, object]:
    errors: List[Dict[str, object]] = []

    book_id = payload.get("book_id")
    year = payload.get("year")
    month = payload.get("month")
    generate_status = (payload.get("voucher_status") or "draft").strip()

    _require(book_id is not None, errors, "book_id", "必填")
    _require(year is not None, errors, "year", "必填")
    _require(month is not None, errors, "month", "必填")

    if errors:
        raise DepreciationError("validation_error", errors)

    try:
        book_id = int(book_id)
        year = int(year)
        month = int(month)
    except Exception:
        raise DepreciationError("validation_error", [{"field": "fields", "message": "格式非法"}])

    if month < 1 or month > 12:
        raise DepreciationError("validation_error", [{"field": "month", "message": "月份非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        dup = conn.execute(
            text(
                "SELECT id FROM depreciation_batches WHERE book_id=:book_id AND period_year=:year AND period_month=:month"
            ),
            {"book_id": book_id, "year": year, "month": month},
        ).fetchone()
        if dup:
            raise DepreciationError("本期已计提")

    with engine.connect() as conn:
        items, asset_errors, total = _build_depreciation_lines(conn, book_id, year, month)

    if asset_errors:
        raise DepreciationError("资产计提校验失败", asset_errors)

    if not items:
        raise DepreciationError("本期无可计提资产")

    subject_codes = set()
    for item in items:
        subject_codes.add(item["expense_subject_code"])
        subject_codes.add(item["accumulated_depr_subject_code"])

    subject_map: Dict[str, Dict[str, object]] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT code, name, is_enabled FROM subjects WHERE book_id=:book_id AND code IN :codes"
            ).bindparams(bindparam("codes", expanding=True)),
            {"book_id": book_id, "codes": list(subject_codes)},
        ).fetchall()

        for r in rows:
            subject_map[r.code] = {"name": r.name, "is_enabled": r.is_enabled}

    for item in items:
        exp = item["expense_subject_code"]
        acc = item["accumulated_depr_subject_code"]
        exp_subject = subject_map.get(exp)
        acc_subject = subject_map.get(acc)
        if not exp_subject:
            asset_errors.append({"asset_code": item["asset_code"], "message": "折旧费用科目不存在"})
        elif exp_subject["is_enabled"] != 1:
            asset_errors.append({"asset_code": item["asset_code"], "message": "折旧费用科目已停用"})
        if not acc_subject:
            asset_errors.append({"asset_code": item["asset_code"], "message": "累计折旧科目不存在"})
        elif acc_subject["is_enabled"] != 1:
            asset_errors.append({"asset_code": item["asset_code"], "message": "累计折旧科目已停用"})

    if asset_errors:
        raise DepreciationError("资产计提校验失败", asset_errors)

    summary = f"固定资产折旧{year:04d}-{month:02d}"
    voucher_lines = []
    grouped: Dict[Tuple[str, str], Decimal] = {}
    for item in items:
        key = (item["expense_subject_code"], item["accumulated_depr_subject_code"])
        grouped[key] = grouped.get(key, Decimal("0")) + item["monthly_amount"]

    for (expense_code, accum_code), amount in grouped.items():
        amount = _quantize_amount(amount)
        voucher_lines.append(
            {
                "summary": summary,
                "subject_code": expense_code,
                "subject_name": subject_map.get(expense_code, {}).get("name", ""),
                "debit": str(amount),
                "credit": "0",
            }
        )
        voucher_lines.append(
            {
                "summary": summary,
                "subject_code": accum_code,
                "subject_name": subject_map.get(accum_code, {}).get("name", ""),
                "debit": "0",
                "credit": str(amount),
            }
        )

    period_end = _period_end(year, month)
    voucher_payload = {
        "book_id": book_id,
        "voucher_date": period_end.isoformat(),
        "voucher_word": "记",
        "voucher_no": "",
        "attachments": 0,
        "maker": "system",
        "status": generate_status,
        "lines": voucher_lines,
    }

    batch_id = None
    voucher_id = None
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO depreciation_batches (
                        book_id, period_year, period_month, method, status, total_amount
                    ) VALUES (
                        :book_id, :year, :month, 'STRAIGHT_LINE', 'DRAFT', :total_amount
                    )
                    """
                ),
                {
                    "book_id": book_id,
                    "year": year,
                    "month": month,
                    "total_amount": _quantize_amount(total),
                },
            )
            batch_id = result.lastrowid

            for item in items:
                conn.execute(
                    text(
                        """
                        INSERT INTO depreciation_lines (
                            batch_id, book_id, asset_id, asset_code, asset_name, category_id,
                            depreciation_method, original_value, residual_rate, residual_value,
                            useful_life_months, monthly_amount, expense_subject_code,
                            accumulated_depr_subject_code, start_use_date, capitalization_date,
                            status, error_message
                        ) VALUES (
                            :batch_id, :book_id, :asset_id, :asset_code, :asset_name, :category_id,
                            :method, :original_value, :residual_rate, :residual_value,
                            :useful_life_months, :monthly_amount, :expense_subject_code,
                            :accumulated_depr_subject_code, :start_use_date, :capitalization_date,
                            'SUCCESS', NULL
                        )
                        """
                    ),
                    {
                        "batch_id": batch_id,
                        "book_id": book_id,
                        "asset_id": item["asset_id"],
                        "asset_code": item["asset_code"],
                        "asset_name": item["asset_name"],
                        "category_id": item["category_id"],
                        "method": item["depreciation_method"],
                        "original_value": item["original_value"],
                        "residual_rate": item["residual_rate"],
                        "residual_value": item["residual_value"],
                        "useful_life_months": item["useful_life_months"],
                        "monthly_amount": _quantize_amount(item["monthly_amount"]),
                        "expense_subject_code": item["expense_subject_code"],
                        "accumulated_depr_subject_code": item["accumulated_depr_subject_code"],
                        "start_use_date": item["start_use_date"],
                        "capitalization_date": item["capitalization_date"],
                    },
                )

        # audit hook placeholder: depreciation batch created
        voucher_result = save_voucher(voucher_payload)
        voucher_id = voucher_result.get("voucher_id")

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE depreciation_batches SET voucher_id=:vid WHERE id=:id"),
                {"vid": voucher_id, "id": batch_id},
            )

        # audit hook placeholder: voucher generated
    except VoucherValidationError as err:
        if batch_id:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM depreciation_lines WHERE batch_id=:id"), {"id": batch_id})
                conn.execute(text("DELETE FROM depreciation_batches WHERE id=:id"), {"id": batch_id})
        raise DepreciationError("凭证生成失败", err.errors)
    except Exception:
        if batch_id:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM depreciation_lines WHERE batch_id=:id"), {"id": batch_id})
                conn.execute(text("DELETE FROM depreciation_batches WHERE id=:id"), {"id": batch_id})
        raise

    return {
        "batch_id": batch_id,
        "voucher_id": voucher_id,
        "book_id": book_id,
        "period_year": year,
        "period_month": month,
        "total_amount": float(_quantize_amount(total)),
        "status": "DRAFT",
    }


def list_batches(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise DepreciationError("validation_error", [{"field": "book_id", "message": "必填"}])
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise DepreciationError("validation_error", [{"field": "book_id", "message": "格式非法"}])

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, book_id, period_year, period_month, method, status,
                       total_amount, voucher_id, created_at
                FROM depreciation_batches
                WHERE book_id=:book_id
                ORDER BY period_year DESC, period_month DESC, id DESC
                """
            ),
            {"book_id": book_id},
        ).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "book_id": r.book_id,
                "period_year": r.period_year,
                "period_month": r.period_month,
                "method": r.method,
                "status": r.status,
                "total_amount": float(r.total_amount),
                "voucher_id": r.voucher_id or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
        )

    return {"book_id": book_id, "items": items}


def get_batch_detail(batch_id: int) -> Dict[str, object]:
    engine = get_engine()
    with engine.connect() as conn:
        header = conn.execute(
            text(
                """
                SELECT id, book_id, period_year, period_month, method, status,
                       total_amount, voucher_id, created_at
                FROM depreciation_batches
                WHERE id=:id
                """
            ),
            {"id": batch_id},
        ).fetchone()
        if not header:
            raise DepreciationError("not_found")

        rows = conn.execute(
            text(
                """
                SELECT asset_code, asset_name, monthly_amount, status
                FROM depreciation_lines
                WHERE batch_id=:batch_id
                ORDER BY asset_code ASC
                """
            ),
            {"batch_id": batch_id},
        ).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "asset_code": r.asset_code,
                "asset_name": r.asset_name,
                "amount": float(r.monthly_amount),
                "status": r.status,
            }
        )

    return {
        "id": header.id,
        "book_id": header.book_id,
        "period_year": header.period_year,
        "period_month": header.period_month,
        "method": header.method,
        "status": header.status,
        "total_amount": float(header.total_amount),
        "voucher_id": header.voucher_id or "",
        "created_at": header.created_at.isoformat() if header.created_at else "",
        "items": items,
    }
