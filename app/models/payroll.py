"""
Payroll MVP domain models (PAYROLL-BIZ-01)
- payroll_employees
- payroll_runs
- payroll_run_lines

Safe-import dummy db fallback to keep structural tools usable even if runtime db wiring differs.
"""

class _DummyDB:
    def Column(self, *a, **k): return None
    Integer = String = Date = DateTime = Boolean = Numeric = Text = JSON = Float = object()

try:
    from app import db  # type: ignore
except Exception:
    db = _DummyDB()

class PayrollEmployee(getattr(db, 'Model', object)):
    __tablename__ = "payroll_employees"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))

    employee_no = db.Column(db.String(64))
    employee_name = db.Column(db.String(255))
    department_id = db.Column(db.Integer)          # later link to aux departments
    status = db.Column(db.String(32))              # active/inactive
    bank_account_id = db.Column(db.Integer)        # later link to aux bank accounts

    # MVP payroll inputs
    base_salary = db.Column(db.Numeric)            # 应发基础
    allowance_total = db.Column(db.Numeric)        # 津补贴合计
    deduction_total = db.Column(db.Numeric)        # 扣款合计（先简化）
    remarks = db.Column(db.Text)

class PayrollRun(getattr(db, 'Model', object)):
    __tablename__ = "payroll_runs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))

    period_yyyymm = db.Column(db.String(7))        # '2026-03'
    status = db.Column(db.String(32))              # draft/generated/posted
    generated_at = db.Column(getattr(db,'DateTime',object))
    remarks = db.Column(db.Text)

class PayrollRunLine(getattr(db, 'Model', object)):
    __tablename__ = "payroll_run_lines"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(getattr(db,'DateTime',object))
    updated_at = db.Column(getattr(db,'DateTime',object))

    run_id = db.Column(db.Integer)
    employee_id = db.Column(db.Integer)

    gross_pay = db.Column(db.Numeric)              # 应发=base+allowance
    total_deductions = db.Column(db.Numeric)       # 扣款
    net_pay = db.Column(db.Numeric)                # 实发

    note = db.Column(db.Text)
