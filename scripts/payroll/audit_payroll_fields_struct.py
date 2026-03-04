import os, re, json, sys
from pathlib import Path
from collections import defaultdict

# Source of truth for spec: re-use PAYROLL-FIELD-01 output if present
SPEC_JSON = Path("evidence/PAYROLL-FIELD-01/payroll_field_audit.json")

OUT_JSON = Path("evidence/PAYROLL-FIELD-02/payroll_struct_audit.json")
OUT_MD   = Path("evidence/PAYROLL-FIELD-02/payroll_struct_audit.md")

REPO_DIRS = ["app","migrations","docs","scripts"]
SCAN_EXT = {".py",".sql"}

def load_spec():
    if SPEC_JSON.exists():
        d=json.loads(SPEC_JSON.read_text(encoding="utf-8"))
        spec=d.get("spec",{})
        # flatten
        fields=[]
        for g,arr in spec.items():
            for f in arr:
                fields.append((g,f))
        return spec, fields
    else:
        return {}, []

def iter_files():
    for d in REPO_DIRS:
        base=Path(d)
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in SCAN_EXT:
                yield p

def extract_model_fields(py_text: str):
    """
    Best-effort for SQLAlchemy declarative:
      foo = db.Column(...)
      foo = Column(...)
      foo = mapped_column(...)
    """
    fields=set()
    # common patterns
    patterns=[
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*db\.Column\s*\(",
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Column\s*\(",
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*mapped_column\s*\(",
    ]
    rx=[re.compile(p, re.MULTILINE) for p in patterns]
    for rxx in rx:
        for m in rxx.finditer(py_text):
            fields.add(m.group(1))
    return fields

def extract_migration_fields(text: str):
    """
    Best-effort for Alembic / raw SQL:
      op.add_column('table', sa.Column('col', ...))
      sa.Column('col', ...)
      CREATE TABLE ... col TYPE ...
      ALTER TABLE ... ADD COLUMN col ...
    """
    fields=set()

    # op.add_column(..., sa.Column('col', ...))
    for m in re.finditer(r"add_column\([^,]+,\s*sa\.Column\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
        fields.add(m.group(1))

    # sa.Column('col', ...) inside create_table
    for m in re.finditer(r"sa\.Column\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
        fields.add(m.group(1))

    # SQL: ADD COLUMN col
    for m in re.finditer(r"ADD\s+COLUMN\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, re.IGNORECASE):
        fields.add(m.group(1))

    # SQL: CREATE TABLE (...) with col lines (very rough)
    # capture tokens like "col_name TYPE"
    for m in re.finditer(r"CREATE\s+TABLE\s+.*?\((.*?)\)\s*;", text, re.IGNORECASE|re.DOTALL):
        body=m.group(1)
        for line in body.split(","):
            line=line.strip()
            mm=re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+[A-Z]", line, re.IGNORECASE)
            if mm:
                fields.add(mm.group(1))

    return fields

def is_payroll_related_path(p: Path):
    s=str(p).lower()
    # focus on payroll/wage/salary/attendance/tax/employee areas
    keywords=["payroll","salary","wage","attendance","employee","tax","social","housing","hr","工资","薪","社保","公积金","个税","考勤"]
    return any(k in s for k in keywords)

def main():
    spec_map, spec_pairs = load_spec()
    if not spec_pairs:
        print("ERROR: missing spec from PAYROLL-FIELD-01; expected evidence/PAYROLL-FIELD-01/payroll_field_audit.json")
        sys.exit(1)

    spec_fields=set([f for _,f in spec_pairs])

    model_fields=set()
    db_fields=set()

    model_evidence=defaultdict(list)
    db_evidence=defaultdict(list)

    for p in iter_files():
        if not is_payroll_related_path(p):
            continue
        text=p.read_text(encoding="utf-8", errors="ignore")
        if p.suffix.lower()==".py":
            mf=extract_model_fields(text)
            for f in mf:
                model_fields.add(f)
                if len(model_evidence[f])<3:
                    model_evidence[f].append(str(p))
        # treat migrations and sql as db sources
        if "migrations" in str(p).lower() or p.suffix.lower()==".sql":
            df=extract_migration_fields(text)
            for f in df:
                db_fields.add(f)
                if len(db_evidence[f])<3:
                    db_evidence[f].append(str(p))

    # Determine missing
    missing_in_model=sorted(spec_fields - model_fields)
    missing_in_db=sorted(spec_fields - db_fields)

    # simple mismatch heuristics: snake-case differences, common aliases
    aliases={
      "id_card_no":["id_card","identity_no","id_number"],
      "employee_no":["emp_no","staff_no"],
      "bank_account_no":["bank_account","bank_no","card_no"],
      "hire_date":["join_date","entry_date"],
      "termination_date":["leave_date","exit_date"],
    }
    mismatch=[]
    for f,alts in aliases.items():
        if f in spec_fields and f not in model_fields:
            hit=[a for a in alts if a in model_fields]
            if hit:
                mismatch.append({"spec":f,"maybe_model":hit})
        if f in spec_fields and f not in db_fields:
            hit=[a for a in alts if a in db_fields]
            if hit:
                mismatch.append({"spec":f,"maybe_db":hit})

    res={
      "summary":{
        "spec_count":len(spec_fields),
        "model_count":len(model_fields),
        "db_count":len(db_fields),
        "missing_in_model_count":len(missing_in_model),
        "missing_in_db_count":len(missing_in_db),
        "mismatch_count":len(mismatch),
      },
      "missing_in_model":missing_in_model,
      "missing_in_db":missing_in_db,
      "mismatch":mismatch,
      "samples":{
        "model_fields_sample":sorted(list(model_fields))[:80],
        "db_fields_sample":sorted(list(db_fields))[:80],
      },
      "evidence":{
        "model_evidence":{k:v for k,v in list(model_evidence.items())[:120]},
        "db_evidence":{k:v for k,v in list(db_evidence.items())[:120]},
      }
    }

    OUT_JSON.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")

    # markdown
    s=res["summary"]
    md=[]
    md.append("# PAYROLL-FIELD-02 工资管理结构级字段审计（真实落库/模型）")
    md.append("")
    md.append(f"- spec_count: **{s['spec_count']}**")
    md.append(f"- model_count: **{s['model_count']}**")
    md.append(f"- db_count: **{s['db_count']}**")
    md.append(f"- missing_in_model_count: **{s['missing_in_model_count']}**")
    md.append(f"- missing_in_db_count: **{s['missing_in_db_count']}**")
    md.append(f"- mismatch_count: **{s['mismatch_count']}**")
    md.append("")
    md.append("## 缺失字段：Model 未覆盖")
    for f in res["missing_in_model"][:200]:
        md.append(f"- `{f}`")
    md.append("")
    md.append("## 缺失字段：DB/Migration 未覆盖")
    for f in res["missing_in_db"][:200]:
        md.append(f"- `{f}`")
    md.append("")
    md.append("## 命名疑似不一致（alias 命中）")
    for it in res["mismatch"][:200]:
        md.append(f"- spec `{it['spec']}` -> maybe {it.get('maybe_model') or it.get('maybe_db')}")
    md.append("")
    md.append("## 抽样：Model 字段样本")
    for f in res["samples"]["model_fields_sample"]:
        md.append(f"- `{f}`")
    md.append("")
    md.append("## 抽样：DB 字段样本")
    for f in res["samples"]["db_fields_sample"]:
        md.append(f"- `{f}`")

    OUT_MD.write_text("\n".join(md),encoding="utf-8")

    print("WROTE", OUT_JSON)
    print("WROTE", OUT_MD)
    print("SUMMARY", s)

if __name__=="__main__":
    main()
