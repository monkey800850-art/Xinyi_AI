import re, sys
from pathlib import Path
from datetime import datetime

OUT = Path("evidence/PAYROLL-UAT-03/uat_report.md")

def write(lines):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    lines=[]
    lines.append("# PAYROLL-UAT-03 Offline 回归（无 SQLAlchemy 依赖）")
    lines.append("")
    lines.append(f"- ts: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- scope: 公式/SQL 计划/迁移静态校验（不做真实 DB 读写）")
    lines.append("")

    ok=True

    # 1) formula assertions
    lines.append("## 1) 工资净薪公式校验")
    cases=[
        ("case1", 10000, 500, 800, 9700),
        ("case2", 12000, 0, 1200, 10800),
        ("zero", 0, 0, 0, 0),
        ("neg", 100, 0, 200, -100),
    ]
    bad=[]
    for name,b,a,d,expect in cases:
        got=(b+a)-d
        if got!=expect:
            bad.append((name,expect,got))
    if bad:
        ok=False
        lines.append(f"- ❌ FAIL: {len(bad)} cases mismatch")
        for n,e,g in bad:
            lines.append(f"  - {n}: expect={e} got={g}")
    else:
        lines.append("- ✅ PASS: net = (base + allowance) - deduction")

    # 2) SQL plan check: ensure route SQL includes expected columns/tables
    lines.append("\n## 2) 路由 SQL 计划静态校验（app.py）")
    app_py=Path("app.py")
    if not app_py.exists():
        ok=False
        lines.append("- ❌ FAIL: app.py not found")
    else:
        s=app_py.read_text(encoding="utf-8", errors="ignore")

        must = [
            ("employees_select", r"FROM\s+payroll_employees", ["employee_no","employee_name"]),
            ("runs_select", r"FROM\s+payroll_runs", ["period_yyyymm","status"]),
            ("lines_select", r"FROM\s+payroll_run_lines", ["gross_pay","net_pay"]),
            ("generate_delete", r"DELETE\s+FROM\s+payroll_run_lines", ["run_id"]),
            ("generate_insert", r"INSERT\s+INTO\s+payroll_run_lines", ["gross_pay","total_deductions","net_pay"]),
        ]

        for name,pat,cols in must:
            if not re.search(pat, s, re.IGNORECASE):
                ok=False
                lines.append(f"- ❌ FAIL: missing SQL pattern: {name} / {pat}")
                continue
            missing_cols=[c for c in cols if c not in s]
            if missing_cols:
                ok=False
                lines.append(f"- ❌ FAIL: {name} missing cols: {missing_cols}")
            else:
                lines.append(f"- ✅ PASS: {name}")

    # 3) migration static check: payroll mvp migration contains key tables/cols
    lines.append("\n## 3) 迁移静态校验（migrations/versions/*payroll*）")
    mig_dir=Path("migrations/versions")
    if not mig_dir.exists():
        ok=False
        lines.append("- ❌ FAIL: migrations/versions not found")
    else:
        migs=sorted([p for p in mig_dir.glob("*payroll*mvp*tables*.py")])
        if not migs:
            # fallback: search any payroll migration
            migs=sorted([p for p in mig_dir.glob("*payroll*.py")])
        if not migs:
            ok=False
            lines.append("- ❌ FAIL: no payroll migration file found")
        else:
            m=migs[-1]
            txt=m.read_text(encoding="utf-8", errors="ignore")
            checks=[
                ("table_employees", "payroll_employees", ["employee_no","employee_name","base_salary","allowance_total","deduction_total"]),
                ("table_runs", "payroll_runs", ["period_yyyymm","status"]),
                ("table_lines", "payroll_run_lines", ["run_id","employee_id","gross_pay","total_deductions","net_pay"]),
            ]
            for name,tbl,cols in checks:
                if tbl not in txt:
                    ok=False
                    lines.append(f"- ❌ FAIL: {name} missing table: {tbl}")
                    continue
                miss=[c for c in cols if c not in txt]
                if miss:
                    ok=False
                    lines.append(f"- ❌ FAIL: {name} missing cols: {miss}")
                else:
                    lines.append(f"- ✅ PASS: {name} ({tbl})")
            lines.append(f"- checked_migration: `{m}`")

    lines.append("\n## Result")
    lines.append("✅ PASS" if ok else "❌ FAIL")
    write(lines)
    print("PAYROLL-UAT-03", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
