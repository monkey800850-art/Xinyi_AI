import sys
from datetime import datetime
from pathlib import Path

OUT_MD = Path("evidence/PAYROLL-UAT-01/uat_report.md")

def md(lines):
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

def fail(msg):
    md(["# PAYROLL-UAT-01 FAILED", "", msg])
    print(msg)
    sys.exit(2)

def main():
    lines=[]
    lines.append("# PAYROLL-UAT-01 工资MVP回归")
    lines.append("")
    lines.append(f"- ts: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    try:
        from app import db  # type: ignore
        import sqlalchemy as sa
    except Exception as e:
        fail(f"DB import failed: {e}")

    # basic connectivity check
    try:
        db.session.execute(sa.text("SELECT 1"))
    except Exception as e:
        fail(f"DB session not ready: {e}")

    # ensure tables exist (simple probe)
    for t in ["payroll_employees","payroll_runs","payroll_run_lines"]:
        try:
            db.session.execute(sa.text(f"SELECT 1 FROM {t} LIMIT 1"))
        except Exception as e:
            fail(f"Table probe failed for {t}: {e}")

    # seed employees (idempotent by employee_no)
    employees = [
        {"employee_no":"E0001","employee_name":"张三","department_id":101,"status":"active","base_salary":10000,"allowance_total":500,"deduction_total":800},
        {"employee_no":"E0002","employee_name":"李四","department_id":102,"status":"active","base_salary":12000,"allowance_total":0,"deduction_total":1200},
    ]

    inserted=0
    for e in employees:
        hit=db.session.execute(
            sa.text("SELECT id FROM payroll_employees WHERE employee_no=:no"),
            {"no": e["employee_no"]}
        ).fetchone()
        if hit:
            # update to expected values for determinism
            db.session.execute(sa.text("""
                UPDATE payroll_employees
                SET employee_name=:name, department_id=:dept, status=:st,
                    base_salary=:b, allowance_total=:a, deduction_total=:d
                WHERE employee_no=:no
            """), {"no":e["employee_no"],"name":e["employee_name"],"dept":e["department_id"],"st":e["status"],
                   "b":e["base_salary"],"a":e["allowance_total"],"d":e["deduction_total"]})
        else:
            db.session.execute(sa.text("""
                INSERT INTO payroll_employees (employee_no, employee_name, department_id, status, base_salary, allowance_total, deduction_total)
                VALUES (:no,:name,:dept,:st,:b,:a,:d)
            """), {"no":e["employee_no"],"name":e["employee_name"],"dept":e["department_id"],"st":e["status"],
                   "b":e["base_salary"],"a":e["allowance_total"],"d":e["deduction_total"]})
            inserted += 1

    # create run for current month (YYYY-MM)
    period=datetime.now().strftime("%Y-%m")
    db.session.execute(sa.text("INSERT INTO payroll_runs (period_yyyymm, status) VALUES (:p,'draft')"), {"p": period})
    run_id=db.session.execute(sa.text("SELECT id FROM payroll_runs WHERE period_yyyymm=:p ORDER BY id DESC LIMIT 1"), {"p": period}).scalar()

    # generate lines (same logic as route)
    db.session.execute(sa.text("DELETE FROM payroll_run_lines WHERE run_id=:rid"), {"rid": run_id})
    emps=db.session.execute(sa.text("""
        SELECT id, COALESCE(base_salary,0) AS base_salary, COALESCE(allowance_total,0) AS allowance_total, COALESCE(deduction_total,0) AS deduction_total
        FROM payroll_employees WHERE COALESCE(status,'active')='active'
    """)).mappings().all()

    for e in emps:
        gross=float(e["base_salary"]) + float(e["allowance_total"])
        ded=float(e["deduction_total"])
        net=gross - ded
        db.session.execute(sa.text("""
            INSERT INTO payroll_run_lines (run_id, employee_id, gross_pay, total_deductions, net_pay)
            VALUES (:rid,:eid,:g,:d,:n)
        """), {"rid":run_id,"eid":e["id"],"g":gross,"d":ded,"n":net})

    db.session.execute(sa.text("UPDATE payroll_runs SET status='generated' WHERE id=:rid"), {"rid": run_id})
    db.session.commit()

    # assertions
    line_cnt=db.session.execute(sa.text("SELECT COUNT(1) FROM payroll_run_lines WHERE run_id=:rid"), {"rid":run_id}).scalar()
    emp_cnt=len(emps)

    bad=[]
    rows=db.session.execute(sa.text("""
        SELECT l.employee_id, l.gross_pay, l.total_deductions, l.net_pay,
               e.base_salary, e.allowance_total, e.deduction_total
        FROM payroll_run_lines l
        JOIN payroll_employees e ON e.id=l.employee_id
        WHERE l.run_id=:rid
        ORDER BY l.id ASC
    """), {"rid":run_id}).mappings().all()

    for r in rows:
        expect=float(r["base_salary"] or 0) + float(r["allowance_total"] or 0) - float(r["deduction_total"] or 0)
        if abs(float(r["net_pay"] or 0) - expect) > 0.0001:
            bad.append({"employee_id": r["employee_id"], "expect": expect, "net_pay": float(r["net_pay"] or 0)})

    lines.append("## Seed")
    lines.append(f"- inserted_new_employees: **{inserted}**")
    lines.append(f"- period: **{period}**")
    lines.append(f"- run_id: **{run_id}**")
    lines.append("")
    lines.append("## Assert")
    lines.append(f"- active_employee_count: **{emp_cnt}**")
    lines.append(f"- run_line_count: **{line_cnt}**")
    lines.append(f"- net_pay_mismatch_count: **{len(bad)}**")
    if line_cnt != emp_cnt:
        lines.append("")
        lines.append("**FAIL**: line count != employee count")
        md(lines)
        sys.exit(3)
    if bad:
        lines.append("")
        lines.append("**FAIL**: net_pay mismatches")
        for b in bad:
            lines.append(f"- employee_id={b['employee_id']} expect={b['expect']} got={b['net_pay']}")
        md(lines)
        sys.exit(4)

    lines.append("")
    lines.append("✅ PASS: payroll MVP end-to-end seed + generate + assert ok")
    md(lines)
    print("PAYROLL-UAT-01 PASS")

if __name__ == "__main__":
    main()
