import os, re, json, sys
from pathlib import Path
from collections import Counter, defaultdict

OUT_JSON = Path("evidence/AUXDIM-FIELD-01/auxdim_struct_audit.json")
OUT_MD   = Path("evidence/AUXDIM-FIELD-01/auxdim_struct_audit.md")

SCAN_EXT = {".py",".sql"}
SCAN_DIRS = ["app","migrations","scripts"]

# === Spec fields (derived from 《部门、单位、个人、银行账户管理字段列表》) ===
# 部门/员工/银行账户/往来单位四大模块字段与规则。:contentReference[oaicite:1]{index=1}
# 本卡聚焦：单位、个人、项目、银行账户（部门可在下一卡单独做树结构/预算策略/法人归属的强化）
SPEC = {
  "往来单位": [
    "party_code","party_full_name","credit_code","taxpayer_type","industry",
    "registered_address","registered_phone",
    "bank_accounts",  # list/json: multiple accounts + default flag
    "business_scope",
    "party_type","settlement_currency","payment_terms",
    "credit_limit","credit_days",
    "ar_ap_subject_code",
    "tax_device_info","einvoice_credit_quota",
    "primary_contact","contact_phone","contact_email",
    "shipping_invoice_address","contract_ids",
    "business_status","risk_level","blacklist_flag","cooperation_status",
    "last_trade_date","archive_file_id"
  ],
  "个人": [
    "employee_no","name","id_card_no","department_code","job_title",
    "hire_date","termination_date",
    "employment_type","tax_residency",
    "bank_account_no","cnaps_code",
    "social_security_city","housing_fund_account",
    "special_additional_deduction",
    "employee_credit_score",
    "internal_arap_subject",
    "status"
  ],
  "项目": [
    "project_code","project_name","project_manager",
    "department_code","legal_entity_id",
    "start_date","end_date",
    "project_status",
    "budget_total","budget_control_policy",
    "revenue_center_code","cost_center_code",
    "customer_party_code","contract_ids",
    "remarks"
  ],
  "银行账户": [
    "account_internal_code","account_name",
    "bank_account_no","bank_full_name","cnaps_code",
    "account_type","currency",
    "legal_entity_id",
    "cash_pool_flag",
    "bank_connect_config_id",
    "account_status",
    "open_date","close_date",
    "balance_alert_threshold",
    "reconciliation_method",
    "last_reconciliation_date",
    "unreconciled_flag"
  ]
}

# Some alias hints to detect existing naming variants
ALIASES = {
  "party_code":["party_code","customer_code","vendor_code","单位编码","往来单位编码"],
  "party_full_name":["party_full_name","party_name","company_name","单位全称","客户名称","供应商名称"],
  "credit_code":["credit_code","uscc","unified_social_credit_code","统一社会信用代码"],
  "contact_email":["contact_email","email","电子邮箱"],
  "bank_account_no":["bank_account_no","bank_account","account_no","银行卡号","银行账号"],
  "cnaps_code":["cnaps_code","联行号","cnaps"],
  "legal_entity_id":["legal_entity_id","entity_id","法人实体","所属法人实体"],
  "department_code":["department_code","dept_code","所属部门编码"],
  "cost_center_code":["cost_center_code","成本中心代码","cost_center"],
  "budget_control_policy":["budget_control_policy","预算控制策略"],
}

def iter_files():
  for d in SCAN_DIRS:
    base=Path(d)
    if not base.exists():
      continue
    for p in base.rglob("*"):
      if p.is_file() and p.suffix.lower() in SCAN_EXT:
        yield p

def extract_model_fields(py_text: str):
  # SQLAlchemy-like patterns
  fields=set()
  patterns=[
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*db\.Column\s*\(",
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Column\s*\(",
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*mapped_column\s*\(",
  ]
  for pat in patterns:
    for m in re.finditer(pat, py_text, re.MULTILINE):
      fields.add(m.group(1))
  return fields

def extract_migration_fields(text: str):
  fields=set()
  for m in re.finditer(r"add_column\([^,]+,\s*sa\.Column\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
    fields.add(m.group(1))
  for m in re.finditer(r"sa\.Column\(\s*['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text):
    fields.add(m.group(1))
  for m in re.finditer(r"ADD\s+COLUMN\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, re.IGNORECASE):
    fields.add(m.group(1))
  for m in re.finditer(r"CREATE\s+TABLE\s+.*?\((.*?)\)\s*;", text, re.IGNORECASE|re.DOTALL):
    body=m.group(1)
    for line in body.split(","):
      mm=re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+[A-Z]", line.strip(), re.IGNORECASE)
      if mm: fields.add(mm.group(1))
  return fields

def is_related(p: Path):
  s=str(p).lower()
  kws=[
    "customer","vendor","supplier","party","contact","ar","ap",
    "employee","staff","person","user",
    "project",
    "bank","account","cash","treasury","reconcile",
    "aux","dimension","assist","辅助","往来","单位","客户","供应商","员工","项目","银行"
  ]
  return any(k in s for k in kws)

def flatten_spec():
  pairs=[]
  for g, arr in SPEC.items():
    for f in arr:
      if isinstance(f,str):
        pairs.append((g,f))
  return pairs

def main():
  spec_pairs=flatten_spec()
  spec_fields=set([f for _,f in spec_pairs])

  model_fields=set()
  db_fields=set()

  for p in iter_files():
    if not is_related(p):
      continue
    text=p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix.lower()==".py":
      model_fields |= extract_model_fields(text)
    if "migrations" in str(p).lower() or p.suffix.lower()==".sql":
      db_fields |= extract_migration_fields(text)

  missing_in_model=sorted(spec_fields - model_fields)
  missing_in_db=sorted(spec_fields - db_fields)

  mismatch=[]
  for f,alts in ALIASES.items():
    if f in spec_fields and f not in model_fields:
      hit=[a for a in alts if a in model_fields]
      if hit: mismatch.append({"spec":f,"maybe_model":hit})
    if f in spec_fields and f not in db_fields:
      hit=[a for a in alts if a in db_fields]
      if hit: mismatch.append({"spec":f,"maybe_db":hit})

  # per-dimension breakdown
  per={}
  for dim, arr in SPEC.items():
    fset=set([x for x in arr if isinstance(x,str)])
    per[dim]={
      "spec_count": len(fset),
      "missing_in_model": sorted(list(fset - model_fields)),
      "missing_in_db": sorted(list(fset - db_fields)),
    }

  res={
    "summary":{
      "spec_count": len(spec_fields),
      "model_count": len(model_fields),
      "db_count": len(db_fields),
      "missing_in_model_count": len(missing_in_model),
      "missing_in_db_count": len(missing_in_db),
      "mismatch_count": len(mismatch),
    },
    "missing_in_model": missing_in_model,
    "missing_in_db": missing_in_db,
    "mismatch": mismatch,
    "per_dimension": per,
    "samples":{
      "model_fields_sample": sorted(list(model_fields))[:120],
      "db_fields_sample": sorted(list(db_fields))[:120],
    }
  }

  OUT_JSON.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")

  s=res["summary"]
  md=[]
  md.append("# AUXDIM-FIELD-01 辅助核算字段结构级审计（单位/个人/项目/银行账户）")
  md.append("")
  md.append(f"- spec_count: **{s['spec_count']}**")
  md.append(f"- model_count: **{s['model_count']}**")
  md.append(f"- db_count: **{s['db_count']}**")
  md.append(f"- missing_in_model_count: **{s['missing_in_model_count']}**")
  md.append(f"- missing_in_db_count: **{s['missing_in_db_count']}**")
  md.append(f"- mismatch_count: **{s['mismatch_count']}**")
  md.append("")
  md.append("## 分维度缺口")
  for dim,v in res["per_dimension"].items():
    md.append(f"\n### {dim} (spec={v['spec_count']})")
    md.append(f"- missing_in_model: {len(v['missing_in_model'])}")
    md.append(f"- missing_in_db: {len(v['missing_in_db'])}")
  md.append("\n## 命名疑似不一致（alias 命中）")
  for it in mismatch[:200]:
    md.append(f"- spec `{it['spec']}` -> maybe {it.get('maybe_model') or it.get('maybe_db')}")
  md.append("\n## 缺失字段：Model 未覆盖（抽样）")
  for f in missing_in_model[:120]:
    md.append(f"- `{f}`")
  md.append("\n## 缺失字段：DB/Migration 未覆盖（抽样）")
  for f in missing_in_db[:120]:
    md.append(f"- `{f}`")
  OUT_MD.write_text("\n".join(md),encoding="utf-8")

  print("WROTE", OUT_JSON)
  print("WROTE", OUT_MD)
  print("SUMMARY", s)

if __name__=="__main__":
  main()
