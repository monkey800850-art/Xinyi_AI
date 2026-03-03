from __future__ import annotations

import json
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
    attendance_ref = str(payload.get("attendance_ref") or "").strip() or None
    attendance_days = _as_int(payload.get("attendance_days", 0), "attendance_days")
    absent_days = _as_int(payload.get("absent_days", 0), "absent_days")
    gross_amount = _as_decimal(payload.get("gross_amount"), "gross_amount")
    deduction_amount = _as_decimal(payload.get("deduction_amount"), "deduction_amount")
    social_insurance = _as_decimal(payload.get("social_insurance"), "social_insurance")
    housing_fund = _as_decimal(payload.get("housing_fund"), "housing_fund")
    bonus_amount = _as_decimal(payload.get("bonus_amount"), "bonus_amount")
    overtime_amount = _as_decimal(payload.get("overtime_amount"), "overtime_amount")
    if len(period) != 7 or period[4] != "-":
        raise PayrollError("validation_error", [{"field": "period", "message": "期间格式应为YYYY-MM"}])

    gross_total = gross_amount + bonus_amount + overtime_amount
    calc = _calc_slip_amounts(gross_total, deduction_amount, social_insurance, housing_fund)
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

        params = {
            "book_id": book_id,
            "period": period,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "department": department,
            "attendance_ref": attendance_ref,
            "attendance_days": attendance_days,
            "absent_days": absent_days,
            "gross_amount": gross_total,
            "deduction_amount": deduction_amount,
            "social_insurance": social_insurance,
            "housing_fund": housing_fund,
            "taxable_base": calc["taxable_base"],
            "tax_amount": calc["tax_amount"],
            "net_amount": calc["net_amount"],
            "bonus_amount": bonus_amount,
            "overtime_amount": overtime_amount,
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
                        attendance_ref, attendance_days, absent_days,
                        gross_amount, deduction_amount, social_insurance, housing_fund,
                        taxable_base, tax_amount, net_amount, status, bonus_amount, overtime_amount,
                        created_at, updated_at
                    ) VALUES (
                        :book_id, :period, :employee_id, :employee_name, :department,
                        :attendance_ref, :attendance_days, :absent_days,
                        :gross_amount, :deduction_amount, :social_insurance, :housing_fund,
                        :taxable_base, :tax_amount, :net_amount, 'draft', :bonus_amount, :overtime_amount,
                        :updated_at, :updated_at
                    )
                    """
                ),
                _db_params(params),
            )
            final_id = int(result.lastrowid)
            status = "draft"
    return {"id": final_id, "status": status, **{k: float(v) if isinstance(v, Decimal) else v for k, v in calc.items()}}


def list_payroll_slips(params: Dict[str, str]) -> Dict[str, object]:
    book_id = _as_int(params.get("book_id"), "book_id")
    period = str(params.get("period") or "").strip()
    sql = """
        SELECT id, book_id, period, employee_id, employee_name, department,
               attendance_ref, attendance_days, absent_days,
               gross_amount, deduction_amount, social_insurance, housing_fund,
               taxable_base, tax_amount, net_amount, status, bonus_amount, overtime_amount
        FROM payroll_slips
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
    items = []
    for r in rows:
        items.append(
            {
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
        )
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
