from __future__ import annotations

import json
import io
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class PayrollError(RuntimeError):
    def __init__(self, message: str, errors: List[Dict[str, object]] | None = None):
        super().__init__(message)
        self.errors = errors or []


def _as_decimal(value, field: str) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PayrollError("validation_error", [{"field": field, "message": "金额格式非法"}])


def _db_value(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _db_params(params: Dict[str, object]) -> Dict[str, object]:
    return {k: _db_value(v) for k, v in params.items()}


def _as_int(value, field: str) -> int:
    try:
        return int(value)
    except Exception:
        raise PayrollError("validation_error", [{"field": field, "message": "必须为整数"}])


def _parse_int_safe(value) -> int | None:
    try:
        x = int(value)
        return x if x > 0 else None
    except Exception:
        return None


def _table_columns(conn, table_name: str) -> set[str]:
    try:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()
        return {str(r.column_name or "").strip().lower() for r in rows}
    except Exception:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {str(getattr(r, "name", r[1]) or "").strip().lower() for r in rows}


def _month_tax(taxable_base: Decimal) -> Decimal:
    x = max(Decimal("0"), taxable_base)
    if x <= Decimal("3000"):
        return x * Decimal("0.03")
    if x <= Decimal("12000"):
        return x * Decimal("0.10") - Decimal("210")
    if x <= Decimal("25000"):
        return x * Decimal("0.20") - Decimal("1410")
    if x <= Decimal("35000"):
        return x * Decimal("0.25") - Decimal("2660")
    if x <= Decimal("55000"):
        return x * Decimal("0.30") - Decimal("4410")
    if x <= Decimal("80000"):
        return x * Decimal("0.35") - Decimal("7160")
    return x * Decimal("0.45") - Decimal("15160")


def _annual_cumulative_tax(taxable_ytd: Decimal) -> Decimal:
    x = max(Decimal("0"), taxable_ytd)
    if x <= Decimal("36000"):
        return x * Decimal("0.03")
    if x <= Decimal("144000"):
        return x * Decimal("0.10") - Decimal("2520")
    if x <= Decimal("300000"):
        return x * Decimal("0.20") - Decimal("16920")
    if x <= Decimal("420000"):
        return x * Decimal("0.25") - Decimal("31920")
    if x <= Decimal("660000"):
        return x * Decimal("0.30") - Decimal("52920")
    if x <= Decimal("960000"):
        return x * Decimal("0.35") - Decimal("85920")
    return x * Decimal("0.45") - Decimal("181920")


def _calc_slip_amounts(gross: Decimal, deduction: Decimal, social_insurance: Decimal, housing_fund: Decimal) -> Dict[str, Decimal]:
    taxable_base = gross - deduction - social_insurance - housing_fund - Decimal("5000")
    taxable_base = max(Decimal("0"), taxable_base)
    tax_amount = max(Decimal("0"), _month_tax(taxable_base)).quantize(Decimal("0.01"))
    net_amount = (gross - deduction - social_insurance - housing_fund - tax_amount).quantize(Decimal("0.01"))
    return {
        "taxable_base": taxable_base.quantize(Decimal("0.01")),
        "tax_amount": tax_amount,
        "net_amount": net_amount,
    }


def _calc_cumulative_tax(conn, book_id: int, employee_id: int, period: str, taxable_base_current: Decimal) -> Dict[str, Decimal]:
    year_prefix = f"{period[0:4]}-%"
    prev = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(taxable_base), 0) AS taxable_ytd_prev,
                   COALESCE(SUM(tax_amount), 0) AS withheld_ytd_prev
            FROM payroll_slips
            WHERE book_id=:book_id
              AND employee_id=:employee_id
              AND period LIKE :year_prefix
              AND period < :period
              AND status='confirmed'
            """
        ),
        {"book_id": book_id, "employee_id": employee_id, "year_prefix": year_prefix, "period": period},
    ).fetchone()
    taxable_prev = _as_decimal(getattr(prev, "taxable_ytd_prev", 0), "taxable_ytd_prev")
    withheld_prev = _as_decimal(getattr(prev, "withheld_ytd_prev", 0), "withheld_ytd_prev")
    taxable_ytd = taxable_prev + taxable_base_current
    tax_ytd = max(Decimal("0"), _annual_cumulative_tax(taxable_ytd)).quantize(Decimal("0.01"))
    tax_current = max(Decimal("0"), (tax_ytd - withheld_prev)).quantize(Decimal("0.01"))
    return {
        "taxable_ytd": taxable_ytd.quantize(Decimal("0.01")),
        "withheld_ytd_prev": withheld_prev.quantize(Decimal("0.01")),
        "tax_amount": tax_current,
    }


def _apply_region_policy(
    conn,
    book_id: int,
    city: str,
    gross_total: Decimal,
    social_insurance_raw,
    housing_fund_raw,
) -> tuple[Decimal, Decimal]:
    # If input explicitly provided, keep caller values; otherwise use city policy.
    social_input_given = social_insurance_raw not in (None, "")
    housing_input_given = housing_fund_raw not in (None, "")
    social_insurance = _as_decimal(social_insurance_raw, "social_insurance")
    housing_fund = _as_decimal(housing_fund_raw, "housing_fund")
    if social_input_given and housing_input_given:
        return social_insurance, housing_fund

    if not city:
        return social_insurance, housing_fund

    try:
        row = conn.execute(
            text(
                """
                SELECT social_rate, housing_rate, social_base_min, social_base_max, housing_base_min, housing_base_max
                FROM payroll_region_policies
                WHERE book_id=:book_id AND city=:city AND status='active'
                LIMIT 1
                """
            ),
            {"book_id": book_id, "city": city},
        ).fetchone()
    except Exception:
        return social_insurance, housing_fund
    if not row:
        return social_insurance, housing_fund

    social_rate = _as_decimal(getattr(row, "social_rate", 0), "social_rate")
    housing_rate = _as_decimal(getattr(row, "housing_rate", 0), "housing_rate")
    social_base_min = _as_decimal(getattr(row, "social_base_min", 0), "social_base_min")
    social_base_max = _as_decimal(getattr(row, "social_base_max", 0), "social_base_max")
    housing_base_min = _as_decimal(getattr(row, "housing_base_min", 0), "housing_base_min")
    housing_base_max = _as_decimal(getattr(row, "housing_base_max", 0), "housing_base_max")

    social_base = gross_total
    housing_base = gross_total
    if social_base_min > 0:
        social_base = max(social_base, social_base_min)
    if social_base_max > 0:
        social_base = min(social_base, social_base_max)
    if housing_base_min > 0:
        housing_base = max(housing_base, housing_base_min)
    if housing_base_max > 0:
        housing_base = min(housing_base, housing_base_max)

    if not social_input_given:
        social_insurance = (social_base * social_rate).quantize(Decimal("0.01"))
    if not housing_input_given:
        housing_fund = (housing_base * housing_rate).quantize(Decimal("0.01"))
    return social_insurance, housing_fund


def _mask_name(name: str) -> str:
    s = str(name or "")
    if len(s) <= 1:
        return "*"
    if len(s) == 2:
        return s[0] + "*"
    return s[0] + "*" * (len(s) - 2) + s[-1]


def upsert_payroll_period(payload: Dict[str, object]) -> Dict[str, object]:
    book_id = _as_int(payload.get("book_id"), "book_id")
    period = str(payload.get("period") or "").strip()
    status = str(payload.get("status") or "open").strip().lower()
    if len(period) != 7 or period[4] != "-":
        raise PayrollError("validation_error", [{"field": "period", "message": "期间格式应为YYYY-MM"}])
    if status not in ("open", "closed"):
        raise PayrollError("validation_error", [{"field": "status", "message": "status非法"}])

    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM payroll_periods WHERE book_id=:book_id AND period=:period"),
            {"book_id": book_id, "period": period},
        ).fetchone()
        if row:
            conn.execute(
                text(
                    """
                    UPDATE payroll_periods
                    SET status=:status, updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                _db_params({"id": int(row.id), "status": status, "updated_at": now}),
            )
            period_id = int(row.id)
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO payroll_periods (book_id, period, status, created_at, updated_at)
                    VALUES (:book_id, :period, :status, :created_at, :updated_at)
                    """
                ),
                _db_params({"book_id": book_id, "period": period, "status": status, "created_at": now, "updated_at": now}),
            )
            period_id = int(result.lastrowid)
    return {"id": period_id, "book_id": book_id, "period": period, "status": status}


def list_payroll_periods(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _as_int(params.get("book_id"), "book_id")
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, book_id, period, status, locked_by, locked_at
                FROM payroll_periods
                WHERE book_id=:book_id
                ORDER BY period DESC
                """
            ),
            {"book_id": book_id},
        ).fetchall()
    return {
        "items": [
            {
                "id": int(r.id),
                "book_id": int(r.book_id),
                "period": str(r.period),
                "status": str(r.status),
                "locked_by": int(r.locked_by or 0) if getattr(r, "locked_by", None) is not None else None,
                "locked_at": str(r.locked_at or ""),
            }
            for r in rows
        ]
    }


def upsert_payroll_slip(payload: Dict[str, object]) -> Dict[str, object]:
    slip_id = payload.get("id")
    book_id = _as_int(payload.get("book_id"), "book_id")
    period = str(payload.get("period") or "").strip()
    employee_id = _as_int(payload.get("employee_id"), "employee_id")
    employee_name = str(payload.get("employee_name") or "").strip()
    department = str(payload.get("department") or "").strip()
    city = str(payload.get("city") or "").strip()
    bank_account = str(payload.get("bank_account") or "").strip()
    attendance_ref = str(payload.get("attendance_ref") or "").strip() or None
    attendance_days = _as_int(payload.get("attendance_days", 0), "attendance_days")
    absent_days = _as_int(payload.get("absent_days", 0), "absent_days")
    gross_amount = _as_decimal(payload.get("gross_amount"), "gross_amount")
    deduction_amount = _as_decimal(payload.get("deduction_amount"), "deduction_amount")
    social_insurance_raw = payload.get("social_insurance")
    housing_fund_raw = payload.get("housing_fund")
    bonus_amount = _as_decimal(payload.get("bonus_amount"), "bonus_amount")
    overtime_amount = _as_decimal(payload.get("overtime_amount"), "overtime_amount")
    tax_method = str(payload.get("tax_method") or "cumulative").strip().lower()
    if tax_method not in ("monthly", "cumulative"):
        raise PayrollError("validation_error", [{"field": "tax_method", "message": "仅支持 monthly/cumulative"}])
    if len(period) != 7 or period[4] != "-":
        raise PayrollError("validation_error", [{"field": "period", "message": "期间格式应为YYYY-MM"}])

    gross_total = gross_amount + bonus_amount + overtime_amount
    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        p = conn.execute(
            text("SELECT id, status FROM payroll_periods WHERE book_id=:book_id AND period=:period"),
            {"book_id": book_id, "period": period},
        ).fetchone()
        if not p:
            raise PayrollError("period_not_found")
        if str(p.status or "").lower() == "closed":
            raise PayrollError("period_closed")

        social_insurance, housing_fund = _apply_region_policy(
            conn,
            book_id=book_id,
            city=city,
            gross_total=gross_total,
            social_insurance_raw=social_insurance_raw,
            housing_fund_raw=housing_fund_raw,
        )
        calc = _calc_slip_amounts(gross_total, deduction_amount, social_insurance, housing_fund)
        cumulative = _calc_cumulative_tax(conn, book_id, employee_id, period, calc["taxable_base"])
        tax_amount = calc["tax_amount"] if tax_method == "monthly" else cumulative["tax_amount"]
        net_amount = (gross_total - deduction_amount - social_insurance - housing_fund - tax_amount).quantize(Decimal("0.01"))

        params = {
            "book_id": book_id,
            "period": period,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "department": department,
            "city": city,
            "bank_account": bank_account,
            "attendance_ref": attendance_ref,
            "attendance_days": attendance_days,
            "absent_days": absent_days,
            "gross_amount": gross_total,
            "deduction_amount": deduction_amount,
            "social_insurance": social_insurance,
            "housing_fund": housing_fund,
            "taxable_base": calc["taxable_base"],
            "tax_amount": tax_amount,
            "net_amount": net_amount,
            "bonus_amount": bonus_amount,
            "overtime_amount": overtime_amount,
            "tax_method": tax_method,
            "ytd_taxable_base": cumulative["taxable_ytd"],
            "ytd_tax_withheld": cumulative["withheld_ytd_prev"] + tax_amount,
            "updated_at": now,
        }

        if slip_id:
            row = conn.execute(
                text("SELECT id, status FROM payroll_slips WHERE id=:id AND book_id=:book_id"),
                {"id": int(slip_id), "book_id": book_id},
            ).fetchone()
            if not row:
                raise PayrollError("not_found")
            if str(row.status or "").lower() == "confirmed":
                raise PayrollError("slip_confirmed_blocked")

            conn.execute(
                text(
                    """
                    UPDATE payroll_slips
                    SET period=:period,
                        employee_id=:employee_id,
                        employee_name=:employee_name,
                        department=:department,
                        city=:city,
                        bank_account=:bank_account,
                        attendance_ref=:attendance_ref,
                        attendance_days=:attendance_days,
                        absent_days=:absent_days,
                        gross_amount=:gross_amount,
                        deduction_amount=:deduction_amount,
                        social_insurance=:social_insurance,
                        housing_fund=:housing_fund,
                        taxable_base=:taxable_base,
                        tax_amount=:tax_amount,
                        net_amount=:net_amount,
                        bonus_amount=:bonus_amount,
                        overtime_amount=:overtime_amount,
                        tax_method=:tax_method,
                        ytd_taxable_base=:ytd_taxable_base,
                        ytd_tax_withheld=:ytd_tax_withheld,
                        updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                _db_params({**params, "id": int(slip_id)}),
            )
            final_id = int(slip_id)
            status = str(row.status or "draft")
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO payroll_slips (
                        book_id, period, employee_id, employee_name, department,
                        city, bank_account,
                        attendance_ref, attendance_days, absent_days,
                        gross_amount, deduction_amount, social_insurance, housing_fund,
                        taxable_base, tax_amount, net_amount, status, bonus_amount, overtime_amount, tax_method, ytd_taxable_base, ytd_tax_withheld,
                        created_at, updated_at
                    ) VALUES (
                        :book_id, :period, :employee_id, :employee_name, :department, :city, :bank_account,
                        :attendance_ref, :attendance_days, :absent_days,
                        :gross_amount, :deduction_amount, :social_insurance, :housing_fund,
                        :taxable_base, :tax_amount, :net_amount, 'draft', :bonus_amount, :overtime_amount, :tax_method, :ytd_taxable_base, :ytd_tax_withheld,
                        :updated_at, :updated_at
                    )
                    """
                ),
                _db_params(params),
            )
            final_id = int(result.lastrowid)
            status = "draft"
    return {
        "id": final_id,
        "status": status,
        "tax_method": tax_method,
        "taxable_base": float(calc["taxable_base"]),
        "tax_amount": float(tax_amount),
        "net_amount": float(net_amount),
        "ytd_taxable_base": float(cumulative["taxable_ytd"]),
        "ytd_tax_withheld": float((cumulative["withheld_ytd_prev"] + tax_amount).quantize(Decimal("0.01"))),
    }


def list_payroll_slips(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _as_int(params.get("book_id"), "book_id")
    period = str(params.get("period") or "").strip()
    viewer_role = str(params.get("viewer_role") or "").strip().lower()
    viewer_employee_id = _parse_int_safe(params.get("viewer_employee_id"))
    args = {"book_id": book_id}
    if period:
        args["period"] = period
    if viewer_role in ("employee", "staff", "self") and viewer_employee_id:
        args["viewer_employee_id"] = viewer_employee_id
    engine = get_engine()
    with engine.connect() as conn:
        cols = _table_columns(conn, "payroll_slips")
        optional_select_cols = []
        if "payment_status" in cols:
            optional_select_cols.append("payment_status")
        if "payment_request_id" in cols:
            optional_select_cols.append("payment_request_id")
        if "paid_at" in cols:
            optional_select_cols.append("paid_at")
        if "city" in cols:
            optional_select_cols.append("city")
        if "bank_account" in cols:
            optional_select_cols.append("bank_account")
        if "tax_method" in cols:
            optional_select_cols.append("tax_method")
        if "ytd_taxable_base" in cols:
            optional_select_cols.append("ytd_taxable_base")
        if "ytd_tax_withheld" in cols:
            optional_select_cols.append("ytd_tax_withheld")
        optional_sql = f", {', '.join(optional_select_cols)}" if optional_select_cols else ""
        sql = f"""
        SELECT id, book_id, period, employee_id, employee_name, department,
               attendance_ref, attendance_days, absent_days,
               gross_amount, deduction_amount, social_insurance, housing_fund,
               taxable_base, tax_amount, net_amount, status, bonus_amount, overtime_amount
               {optional_sql}
        FROM payroll_slips
        WHERE book_id=:book_id
        """
        if period:
            sql += " AND period=:period"
        if viewer_role in ("employee", "staff", "self") and viewer_employee_id:
            sql += " AND employee_id=:viewer_employee_id"
        sql += " ORDER BY id DESC"
        rows = conn.execute(text(sql), args).fetchall()
    items = []
    for r in rows:
        item = {
            "id": int(r.id),
            "book_id": int(r.book_id),
            "period": str(r.period),
            "employee_id": int(r.employee_id),
            "employee_name": str(r.employee_name or ""),
            "department": str(r.department or ""),
            "attendance_ref": str(r.attendance_ref or ""),
            "attendance_days": int(r.attendance_days or 0),
            "absent_days": int(r.absent_days or 0),
            "gross_amount": float(r.gross_amount or 0),
            "deduction_amount": float(r.deduction_amount or 0),
            "social_insurance": float(r.social_insurance or 0),
            "housing_fund": float(r.housing_fund or 0),
            "taxable_base": float(r.taxable_base or 0),
            "tax_amount": float(r.tax_amount or 0),
            "net_amount": float(r.net_amount or 0),
            "status": str(r.status or ""),
            "bonus_amount": float(r.bonus_amount or 0),
            "overtime_amount": float(r.overtime_amount or 0),
        }
        if hasattr(r, "payment_status"):
            item["payment_status"] = str(r.payment_status or "")
        if hasattr(r, "payment_request_id"):
            item["payment_request_id"] = int(r.payment_request_id or 0) if r.payment_request_id is not None else None
        if hasattr(r, "paid_at"):
            item["paid_at"] = str(r.paid_at or "")
        if hasattr(r, "city"):
            item["city"] = str(r.city or "")
        if hasattr(r, "bank_account"):
            item["bank_account"] = str(r.bank_account or "")
        if hasattr(r, "tax_method"):
            item["tax_method"] = str(r.tax_method or "")
        if hasattr(r, "ytd_taxable_base"):
            item["ytd_taxable_base"] = float(r.ytd_taxable_base or 0)
        if hasattr(r, "ytd_tax_withheld"):
            item["ytd_tax_withheld"] = float(r.ytd_tax_withheld or 0)

        # Role-based desensitization and visibility levels.
        if viewer_role in ("employee", "staff", "self"):
            item["employee_name"] = _mask_name(item["employee_name"])
            item.pop("taxable_base", None)
            item.pop("tax_amount", None)
            item.pop("ytd_taxable_base", None)
            item.pop("ytd_tax_withheld", None)
            if item.get("bank_account"):
                acct = str(item["bank_account"])
                item["bank_account"] = ("*" * max(0, len(acct) - 4)) + acct[-4:]
        elif viewer_role == "cashier":
            item["employee_name"] = _mask_name(item["employee_name"])
            item.pop("taxable_base", None)
            item.pop("tax_amount", None)
            item.pop("ytd_taxable_base", None)
            item.pop("ytd_tax_withheld", None)

        items.append(item)
    return {"items": items}


def set_payroll_period_status(period_id: int, action: str, operator_id: int | None = None) -> Dict[str, object]:
    pid = int(period_id)
    action = str(action or "").strip().lower()
    if action not in ("close", "reopen"):
        raise PayrollError("validation_error", [{"field": "action", "message": "仅支持 close/reopen"}])
    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, status FROM payroll_periods WHERE id=:id"),
            {"id": pid},
        ).fetchone()
        if not row:
            raise PayrollError("period_not_found")
        cur = str(row.status or "").lower()
        if action == "close":
            if cur == "closed":
                return {"id": pid, "status": "closed", "already_closed": True}
            cnt = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS c
                    FROM payroll_slips
                    WHERE period=(SELECT period FROM payroll_periods WHERE id=:id)
                      AND book_id=(SELECT book_id FROM payroll_periods WHERE id=:id)
                      AND status<>'confirmed'
                    """
                ),
                {"id": pid},
            ).fetchone()
            if int(getattr(cnt, "c", 0) or 0) > 0:
                raise PayrollError("period_close_blocked_unconfirmed_slips")
            conn.execute(
                text(
                    """
                    UPDATE payroll_periods
                    SET status='closed', locked_by=:locked_by, locked_at=:locked_at, updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                _db_params({"id": pid, "locked_by": operator_id, "locked_at": now, "updated_at": now}),
            )
            return {"id": pid, "status": "closed"}

        if cur == "open":
            return {"id": pid, "status": "open", "already_open": True}
        conn.execute(
            text(
                """
                UPDATE payroll_periods
                SET status='open', locked_by=NULL, locked_at=NULL, updated_at=:updated_at
                WHERE id=:id
                """
            ),
            _db_params({"id": pid, "updated_at": now}),
        )
    return {"id": pid, "status": "open"}


def get_payroll_voucher_suggestion(slip_id: int) -> Dict[str, object]:
    sid = int(slip_id)
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM payroll_slips WHERE id=:id"), {"id": sid}).fetchone()
        if not row:
            raise PayrollError("not_found")
        if str(row.status or "").lower() != "confirmed":
            raise PayrollError("slip_not_confirmed")

    gross = _as_decimal(getattr(row, "gross_amount", 0), "gross_amount")
    social = _as_decimal(getattr(row, "social_insurance", 0), "social_insurance")
    fund = _as_decimal(getattr(row, "housing_fund", 0), "housing_fund")
    tax = _as_decimal(getattr(row, "tax_amount", 0), "tax_amount")
    net = _as_decimal(getattr(row, "net_amount", 0), "net_amount")

    # Small listed-company practical mapping (can be overridden by subject master rules later)
    # debit 6602.01 职工薪酬; credit 2211.01 工资, 2211.04 公积金, 2241.03 个税
    lines = [
        {"subject_code": "6602.01", "debit": float(gross), "credit": 0.0, "summary": "计提工资薪酬"},
        {"subject_code": "2211.01", "debit": 0.0, "credit": float(net), "summary": "应付职工薪酬-工资"},
    ]
    if social > 0:
        lines.append({"subject_code": "2211.02", "debit": 0.0, "credit": float(social), "summary": "应付职工薪酬-社保"})
    if fund > 0:
        lines.append({"subject_code": "2211.04", "debit": 0.0, "credit": float(fund), "summary": "应付职工薪酬-公积金"})
    if tax > 0:
        lines.append({"subject_code": "2241.03", "debit": 0.0, "credit": float(tax), "summary": "代扣个税"})

    return {
        "slip_id": sid,
        "book_id": int(row.book_id),
        "period": str(row.period),
        "employee_id": int(row.employee_id),
        "status": "confirmed",
        "voucher_draft": {
            "voucher_word": "记",
            "summary": f"工资计提 {row.period}",
            "lines": lines,
        },
    }


def create_payroll_payment_request(slip_id: int, operator: str, role: str) -> Dict[str, object]:
    sid = int(slip_id)
    if not operator:
        raise PayrollError("operator_required")
    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        slip = conn.execute(text("SELECT * FROM payroll_slips WHERE id=:id"), {"id": sid}).fetchone()
        if not slip:
            raise PayrollError("not_found")
        if str(slip.status or "").lower() != "confirmed":
            raise PayrollError("slip_not_confirmed")

        slip_cols = _table_columns(conn, "payroll_slips")
        has_payment_status = "payment_status" in slip_cols
        has_payment_request_id = "payment_request_id" in slip_cols
        has_paid_at = "paid_at" in slip_cols

        existing = conn.execute(
            text(
                """
                SELECT id, status
                FROM payment_requests
                WHERE related_type='payroll'
                  AND related_id=:sid
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"sid": sid},
        ).fetchone()
        if existing:
            if has_payment_status or has_payment_request_id or has_paid_at:
                sets = []
                params = {"id": sid}
                if has_payment_status:
                    sets.append("payment_status='pending'")
                if has_payment_request_id:
                    sets.append("payment_request_id=:payment_request_id")
                    params["payment_request_id"] = int(existing.id)
                if has_paid_at:
                    sets.append("paid_at=NULL")
                if sets:
                    conn.execute(text(f"UPDATE payroll_slips SET {', '.join(sets)}, updated_at=:updated_at WHERE id=:id"), _db_params({**params, "updated_at": now}))
            return {"payment_id": int(existing.id), "status": str(existing.status), "already_exists": True}

        result = conn.execute(
            text(
                """
                INSERT INTO payment_requests (
                    book_id, title, payee_name, payee_account, pay_method, amount,
                    status, related_type, related_id, reimbursement_id, created_at, updated_at
                ) VALUES (
                    :book_id, :title, :payee_name, :payee_account, :pay_method, :amount,
                    'pending', 'payroll', :related_id, NULL, :created_at, :updated_at
                )
                """
            ),
            _db_params(
                {
                    "book_id": int(slip.book_id),
                    "title": f"工资发放 {slip.period}",
                    "payee_name": str(slip.employee_name or f"EMP-{slip.employee_id}"),
                    "payee_account": "",
                    "pay_method": "bank_transfer",
                    "amount": _as_decimal(getattr(slip, "net_amount", 0), "net_amount"),
                    "related_id": sid,
                    "created_at": now,
                    "updated_at": now,
                }
            ),
        )
        payment_id = int(result.lastrowid)

        if has_payment_status or has_payment_request_id:
            sets = []
            params = {"id": sid, "updated_at": now}
            if has_payment_status:
                sets.append("payment_status='pending'")
            if has_payment_request_id:
                sets.append("payment_request_id=:payment_request_id")
                params["payment_request_id"] = payment_id
            if has_paid_at:
                sets.append("paid_at=NULL")
            if sets:
                conn.execute(text(f"UPDATE payroll_slips SET {', '.join(sets)}, updated_at=:updated_at WHERE id=:id"), _db_params(params))

        cols = _table_columns(conn, "payroll_tax_ledger")
        if "snapshot_json" in cols:
            conn.execute(
                text(
                    """
                    INSERT INTO payroll_tax_ledger (
                        book_id, employee_id, period, tax_type, taxable_base, tax_amount, calc_version, snapshot_json, created_at
                    ) VALUES (
                        :book_id, :employee_id, :period, 'payment_link', 0, 0, 'v1-link',
                        :snapshot_json, :created_at
                    )
                    """
                ),
                _db_params(
                    {
                        "book_id": int(slip.book_id),
                        "employee_id": int(slip.employee_id),
                        "period": str(slip.period),
                        "snapshot_json": json.dumps(
                            {"slip_id": sid, "payment_id": payment_id, "operator": operator, "role": role},
                            ensure_ascii=False,
                        ),
                        "created_at": now,
                    }
                ),
            )

    return {"payment_id": payment_id, "status": "pending", "related_type": "payroll", "related_id": sid}


def get_payroll_payment_status(slip_id: int) -> Dict[str, object]:
    sid = int(slip_id)
    engine = get_engine()
    with engine.connect() as conn:
        cols = _table_columns(conn, "payroll_slips")
        optional = []
        if "payment_status" in cols:
            optional.append("payment_status")
        if "payment_request_id" in cols:
            optional.append("payment_request_id")
        if "paid_at" in cols:
            optional.append("paid_at")
        optional_sql = f", {', '.join(optional)}" if optional else ""
        slip = conn.execute(text(f"SELECT id, book_id, period, employee_id, status, net_amount {optional_sql} FROM payroll_slips WHERE id=:id"), {"id": sid}).fetchone()
        if not slip:
            raise PayrollError("not_found")

        payment = conn.execute(
            text(
                """
                SELECT id, status, pay_at
                FROM payment_requests
                WHERE related_type='payroll' AND related_id=:sid
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"sid": sid},
        ).fetchone()

    return {
        "slip_id": sid,
        "book_id": int(slip.book_id),
        "period": str(slip.period),
        "employee_id": int(slip.employee_id),
        "slip_status": str(slip.status or ""),
        "net_amount": float(slip.net_amount or 0),
        "payment_status": str(getattr(slip, "payment_status", "") or (payment.status if payment else "unpaid")),
        "payment_request_id": int(getattr(slip, "payment_request_id", 0) or (payment.id if payment else 0)) or None,
        "paid_at": str(getattr(slip, "paid_at", "") or (payment.pay_at if payment else "")),
        "payment_request_status": str(payment.status or "") if payment else "",
    }


def upsert_payroll_region_policy(payload: Dict[str, object]) -> Dict[str, object]:
    book_id = _as_int(payload.get("book_id"), "book_id")
    city = str(payload.get("city") or "").strip()
    if not city:
        raise PayrollError("validation_error", [{"field": "city", "message": "city不能为空"}])
    status = str(payload.get("status") or "active").strip().lower()
    if status not in ("active", "inactive"):
        raise PayrollError("validation_error", [{"field": "status", "message": "status非法"}])
    social_rate = _as_decimal(payload.get("social_rate", 0), "social_rate")
    housing_rate = _as_decimal(payload.get("housing_rate", 0), "housing_rate")
    social_base_min = _as_decimal(payload.get("social_base_min", 0), "social_base_min")
    social_base_max = _as_decimal(payload.get("social_base_max", 0), "social_base_max")
    housing_base_min = _as_decimal(payload.get("housing_base_min", 0), "housing_base_min")
    housing_base_max = _as_decimal(payload.get("housing_base_max", 0), "housing_base_max")

    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM payroll_region_policies WHERE book_id=:book_id AND city=:city"),
            {"book_id": book_id, "city": city},
        ).fetchone()
        if row:
            conn.execute(
                text(
                    """
                    UPDATE payroll_region_policies
                    SET social_rate=:social_rate, housing_rate=:housing_rate,
                        social_base_min=:social_base_min, social_base_max=:social_base_max,
                        housing_base_min=:housing_base_min, housing_base_max=:housing_base_max,
                        status=:status, updated_at=:updated_at
                    WHERE id=:id
                    """
                ),
                _db_params(
                    {
                        "id": int(row.id),
                        "social_rate": social_rate,
                        "housing_rate": housing_rate,
                        "social_base_min": social_base_min,
                        "social_base_max": social_base_max,
                        "housing_base_min": housing_base_min,
                        "housing_base_max": housing_base_max,
                        "status": status,
                        "updated_at": now,
                    }
                ),
            )
            policy_id = int(row.id)
        else:
            result = conn.execute(
                text(
                    """
                    INSERT INTO payroll_region_policies (
                        book_id, city, social_rate, housing_rate,
                        social_base_min, social_base_max, housing_base_min, housing_base_max,
                        status, created_at, updated_at
                    ) VALUES (
                        :book_id, :city, :social_rate, :housing_rate,
                        :social_base_min, :social_base_max, :housing_base_min, :housing_base_max,
                        :status, :created_at, :updated_at
                    )
                    """
                ),
                _db_params(
                    {
                        "book_id": book_id,
                        "city": city,
                        "social_rate": social_rate,
                        "housing_rate": housing_rate,
                        "social_base_min": social_base_min,
                        "social_base_max": social_base_max,
                        "housing_base_min": housing_base_min,
                        "housing_base_max": housing_base_max,
                        "status": status,
                        "created_at": now,
                        "updated_at": now,
                    }
                ),
            )
            policy_id = int(result.lastrowid)

    return {"id": policy_id, "book_id": book_id, "city": city, "status": status}


def list_payroll_region_policies(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _as_int(params.get("book_id"), "book_id")
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, book_id, city, social_rate, housing_rate, social_base_min, social_base_max,
                       housing_base_min, housing_base_max, status
                FROM payroll_region_policies
                WHERE book_id=:book_id
                ORDER BY city ASC
                """
            ),
            {"book_id": book_id},
        ).fetchall()
    return {
        "items": [
            {
                "id": int(r.id),
                "book_id": int(r.book_id),
                "city": str(r.city),
                "social_rate": float(r.social_rate or 0),
                "housing_rate": float(r.housing_rate or 0),
                "social_base_min": float(r.social_base_min or 0),
                "social_base_max": float(r.social_base_max or 0),
                "housing_base_min": float(r.housing_base_min or 0),
                "housing_base_max": float(r.housing_base_max or 0),
                "status": str(r.status or ""),
            }
            for r in rows
        ]
    }


def create_payroll_disbursement_batch(payload: Dict[str, object], operator: str, role: str) -> Dict[str, object]:
    if role not in ("payroll", "cashier", "admin"):
        raise PayrollError("permission_denied")
    book_id = _as_int(payload.get("book_id"), "book_id")
    period = str(payload.get("period") or "").strip()
    if len(period) != 7 or period[4] != "-":
        raise PayrollError("validation_error", [{"field": "period", "message": "期间格式应为YYYY-MM"}])
    raw_slip_ids = payload.get("slip_ids")
    slip_ids: List[int] = []
    if isinstance(raw_slip_ids, list):
        for x in raw_slip_ids:
            sid = _parse_int_safe(x)
            if sid:
                slip_ids.append(sid)

    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        slip_cols = _table_columns(conn, "payroll_slips")
        if "bank_account" not in slip_cols:
            raise PayrollError("bank_account_column_missing")
        sql = """
            SELECT id, employee_id, employee_name, net_amount, bank_account
            FROM payroll_slips
            WHERE book_id=:book_id AND period=:period AND status='confirmed'
        """
        args = {"book_id": book_id, "period": period}
        if slip_ids:
            placeholders = ", ".join([f":sid_{i}" for i in range(len(slip_ids))])
            sql += f" AND id IN ({placeholders})"
            for i, sid in enumerate(slip_ids):
                args[f"sid_{i}"] = sid
        if "payment_status" in slip_cols:
            sql += " AND COALESCE(payment_status,'unpaid') IN ('unpaid','pending')"
        rows = conn.execute(text(sql), args).fetchall()
        if not rows:
            raise PayrollError("no_eligible_slips")

        total_amount = Decimal("0")
        for r in rows:
            if not str(getattr(r, "bank_account", "") or "").strip():
                raise PayrollError("bank_account_required")
            total_amount += _as_decimal(getattr(r, "net_amount", 0), "net_amount")

        batch_no = f"PAY{period.replace('-', '')}{now.strftime('%H%M%S')}"
        result = conn.execute(
            text(
                """
                INSERT INTO payroll_disbursement_batches (
                    book_id, period, batch_no, status, total_count, total_amount, created_by, created_at, updated_at
                ) VALUES (
                    :book_id, :period, :batch_no, 'draft', :total_count, :total_amount, :created_by, :created_at, :updated_at
                )
                """
            ),
            _db_params(
                {
                    "book_id": book_id,
                    "period": period,
                    "batch_no": batch_no,
                    "total_count": len(rows),
                    "total_amount": total_amount,
                    "created_by": operator or "",
                    "created_at": now,
                    "updated_at": now,
                }
            ),
        )
        batch_id = int(result.lastrowid)

        for r in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO payroll_disbursement_batch_items (
                        batch_id, slip_id, employee_id, employee_name, bank_account, pay_amount, created_at
                    ) VALUES (
                        :batch_id, :slip_id, :employee_id, :employee_name, :bank_account, :pay_amount, :created_at
                    )
                    """
                ),
                _db_params(
                    {
                        "batch_id": batch_id,
                        "slip_id": int(r.id),
                        "employee_id": int(r.employee_id),
                        "employee_name": str(r.employee_name or ""),
                        "bank_account": str(r.bank_account or ""),
                        "pay_amount": _as_decimal(getattr(r, "net_amount", 0), "pay_amount"),
                        "created_at": now,
                    }
                ),
            )
            if "payment_status" in slip_cols:
                conn.execute(
                    text("UPDATE payroll_slips SET payment_status='batched', updated_at=:updated_at WHERE id=:id"),
                    _db_params({"id": int(r.id), "updated_at": now}),
                )

    return {
        "batch_id": batch_id,
        "batch_no": batch_no,
        "book_id": book_id,
        "period": period,
        "total_count": len(rows),
        "total_amount": float(total_amount.quantize(Decimal("0.01"))),
    }


def list_payroll_disbursement_batches(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _as_int(params.get("book_id"), "book_id")
    period = str(params.get("period") or "").strip()
    sql = """
        SELECT id, book_id, period, batch_no, status, total_count, total_amount, file_name, created_by, created_at
        FROM payroll_disbursement_batches
        WHERE book_id=:book_id
    """
    args = {"book_id": book_id}
    if period:
        sql += " AND period=:period"
        args["period"] = period
    sql += " ORDER BY id DESC"
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), args).fetchall()
    return {
        "items": [
            {
                "id": int(r.id),
                "book_id": int(r.book_id),
                "period": str(r.period),
                "batch_no": str(r.batch_no or ""),
                "status": str(r.status or ""),
                "total_count": int(r.total_count or 0),
                "total_amount": float(r.total_amount or 0),
                "file_name": str(r.file_name or ""),
                "created_by": str(r.created_by or ""),
                "created_at": str(r.created_at or ""),
            }
            for r in rows
        ]
    }


def export_payroll_bank_file(batch_id: int, operator: str, role: str) -> Dict[str, object]:
    if role not in ("payroll", "cashier", "admin", "auditor"):
        raise PayrollError("permission_denied")
    bid = int(batch_id)
    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        head = conn.execute(
            text("SELECT id, book_id, period, batch_no FROM payroll_disbursement_batches WHERE id=:id"),
            {"id": bid},
        ).fetchone()
        if not head:
            raise PayrollError("batch_not_found")
        rows = conn.execute(
            text(
                """
                SELECT employee_id, employee_name, bank_account, pay_amount
                FROM payroll_disbursement_batch_items
                WHERE batch_id=:batch_id
                ORDER BY id ASC
                """
            ),
            {"batch_id": bid},
        ).fetchall()
        if not rows:
            raise PayrollError("batch_empty")

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["employee_id", "employee_name", "bank_account", "amount", "remark"])
        for r in rows:
            writer.writerow([int(r.employee_id), str(r.employee_name or ""), str(r.bank_account or ""), f"{Decimal(str(r.pay_amount or 0)).quantize(Decimal('0.01'))}", f"工资发放 {head.period}"])
        content = buf.getvalue().encode("utf-8-sig")
        file_name = f"payroll_batch_{head.batch_no or bid}.csv"
        conn.execute(
            text(
                """
                UPDATE payroll_disbursement_batches
                SET status='exported', file_name=:file_name, updated_at=:updated_at
                WHERE id=:id
                """
            ),
            _db_params({"id": bid, "file_name": file_name, "updated_at": now}),
        )

    return {"batch_id": bid, "file_name": file_name, "content": content}


def confirm_payroll_slip(slip_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise PayrollError("operator_required")
    engine = get_engine()
    now = datetime.now()
    with engine.begin() as conn:
        slip = conn.execute(
            text("SELECT * FROM payroll_slips WHERE id=:id"),
            {"id": int(slip_id)},
        ).fetchone()
        if not slip:
            raise PayrollError("not_found")
        if str(slip.status or "").lower() == "confirmed":
            return {"id": int(slip_id), "status": "confirmed", "already_confirmed": True}

        p = conn.execute(
            text("SELECT status FROM payroll_periods WHERE book_id=:book_id AND period=:period"),
            {"book_id": int(slip.book_id), "period": str(slip.period)},
        ).fetchone()
        if not p:
            raise PayrollError("period_not_found")
        if str(p.status or "").lower() == "closed":
            raise PayrollError("period_closed")

        conn.execute(
            text("UPDATE payroll_slips SET status='confirmed', updated_at=:updated_at WHERE id=:id"),
            _db_params({"id": int(slip_id), "updated_at": now}),
        )

        cols = _table_columns(conn, "payroll_tax_ledger")
        has_snapshot = "snapshot_json" in cols
        has_calc_version = "calc_version" in cols
        insert_cols = [
            "book_id",
            "employee_id",
            "period",
            "tax_type",
            "taxable_base",
            "tax_amount",
            "created_at",
        ]
        insert_vals = [
            ":book_id",
            ":employee_id",
            ":period",
            "'salary_monthly'",
            ":taxable_base",
            ":tax_amount",
            ":created_at",
        ]
        params = {
            "book_id": int(slip.book_id),
            "employee_id": int(slip.employee_id),
            "period": str(slip.period),
            "taxable_base": slip.taxable_base,
            "tax_amount": slip.tax_amount,
            "created_at": now,
        }
        if has_calc_version:
            insert_cols.append("calc_version")
            insert_vals.append(":calc_version")
            params["calc_version"] = "v1-monthly"
        if has_snapshot:
            insert_cols.append("snapshot_json")
            insert_vals.append(":snapshot_json")
            params["snapshot_json"] = json.dumps(
                {
                    "slip_id": int(slip.id),
                    "operator": operator,
                    "role": role,
                    "taxable_base": str(slip.taxable_base),
                    "tax_amount": str(slip.tax_amount),
                },
                ensure_ascii=False,
            )
        conn.execute(
            text(
                f"""
                INSERT INTO payroll_tax_ledger ({", ".join(insert_cols)})
                VALUES ({", ".join(insert_vals)})
                """
            ),
            _db_params(params),
        )

    return {"id": int(slip_id), "status": "confirmed"}


def sync_attendance_interface(payload: Dict[str, object]) -> Dict[str, object]:
    # Keep attendance interface stable: accept external attendance payload and return normalized summary.
    period = str(payload.get("period") or "").strip()
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    normalized = []
    for r in records:
        if not isinstance(r, dict):
            continue
        employee_id = int(r.get("employee_id") or 0)
        attendance_days = int(r.get("attendance_days") or 0)
        absent_days = int(r.get("absent_days") or 0)
        normalized.append(
            {
                "employee_id": employee_id,
                "attendance_days": max(0, attendance_days),
                "absent_days": max(0, absent_days),
                "attendance_ref": str(r.get("attendance_ref") or ""),
            }
        )
    return {
        "status": "ok",
        "period": period,
        "count": len(normalized),
        "items": normalized,
        "message": "attendance_interface_preserved",
    }
