import os, re, json, sys
from pathlib import Path
from collections import defaultdict

OUT_JSON = Path("evidence/AUXDIM-FIELD-01/auxdim_struct_audit.json")
OUT_MD   = Path("evidence/AUXDIM-FIELD-01/auxdim_struct_audit.md")
PLAN_JSON= Path("evidence/AUXDIM-FIELD-01/auxdim_patch_plan.json")
PLAN_MD  = Path("evidence/AUXDIM-FIELD-01/auxdim_patch_plan.md")

SCAN_EXT = {".py",".sql"}
SCAN_DIRS = ["app","migrations","scripts"]

# ===== Spec fields =====
# 单位/个人/银行账户：来自《部门、单位、个人、银行账户管理字段列表》 :contentReference[oaicite:2]{index=2}
# 项目：文档未给，本脚本使用“最小常用字段假设”，以便先跑通结构审计/计划（后续可替换）。
SPEC = {
  "单位(客户/供应商)": {
    "spec_source": "doc",
    "fields": [
      "party_code","party_full_name","credit_code","taxpayer_type","industry",
      "registered_address","registered_phone",
      "bank_accounts",  # list/json
      "business_scope",
      "party_type","settlement_currency","payment_terms",
      "credit_limit","credit_days",
      "ar_ap_subject_code",
      "tax_device_info","einvoice_credit_quota",
      "primary_contact","contact_phone","contact_email",
      "shipping_invoice_address","contract_ids",
      "business_status","risk_level","blacklist_flag","cooperation_status",
      "last_trade_date","archive_file_id"
    ]
  },
  "个人(员工/往来主体)": {
    "spec_source": "doc",
    "fields": [
      "employee_no","name","id_card_no","department_code","job_title",
      "hire_date","termination_date",
      "employment_type","tax_residency",
      "bank_account_no","cnaps_code",
      "social_security_city","housing_fund_account",
      "special_additional_deduction",
      "employee_credit_score",
      "internal_arap_subject",
      "status"
    ]
  },
  "银行账户": {
    "spec_source": "doc",
    "fields": [
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
  },
  "项目": {
    "spec_source": "assumption",
    "fields": [
      "project_code","project_name","project_manager",
      "department_code","legal_entity_id",
      "start_date","end_date","project_status",
      "budget_total","budget_control_policy",
      "revenue_center_code","cost_center_code",
      "customer_party_code","contract_ids",
      "remarks"
    ]
  }
}

ALIASES = {
  "party_code":["party_code","customer_code","vendor_code","supplier_code","单位编码"],
  "party_full_name":["party_full_name","party_name","company_name","单位全称","客户名称","供应商名称"],
  "credit_code":["credit_code","uscc","unified_social_credit_code","统一社会信用代码"],
  "taxpayer_type":["taxpayer_type","纳税人身份","一般纳税人","小规模"],
  "registered_address":["registered_address","注册地址"],
  "registered_phone":["registered_phone","注册电话"],
  "primary_contact":["primary_contact","联系人","主要联系人"],
  "contact_phone":["contact_phone","mobile","联系电话","手机"],
  "contact_email":["contact_email","email","电子邮箱"],
  "bank_account_no":["bank_account_no","bank_account","account_no","银行账号","银行卡号"],
  "cnaps_code":["cnaps_code","联行号","cnaps"],
  "legal_entity_id":["legal_entity_id","entity_id","所属法人实体","法人实体"],
  "department_code":["department_code","dept_code","所属部门编码","部门编码"],
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
  fields=set()
  pats=[
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*db\.Column\s*\(",
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Column\s*\(",
    r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*mapped_column\s*\(",
  ]
  for pat in pats:
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
    "employee","staff","person",
    "project",
    "bank","account","cash","treasury","reconcile",
    "aux","dimension","assist",
    "往来","单位","客户","供应商","员工","个人","项目","银行","账户"
  ]
  return any(k in s for k in kws)

def flatten_spec():
  pairs=[]
  for dim, obj in SPEC.items():
    for f in obj["fields"]:
      pairs.append((dim,f))
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

  per={}
  for dim,obj in SPEC.items():
    fset=set(obj["fields"])
    per[dim]={
      "spec_source": obj["spec_source"],
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
      "model_fields_sample": sorted(list(model_fields))[:140],
      "db_fields_sample": sorted(list(db_fields))[:140],
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
  for dim,v in per.items():
    md.append(f"\n### {dim} (spec={v['spec_count']}, source={v['spec_source']})")
    md.append(f"- missing_in_model: {len(v['missing_in_model'])}")
    md.append(f"- missing_in_db: {len(v['missing_in_db'])}")
  md.append("\n## 命名疑似不一致（alias 命中）")
  for it in mismatch[:200]:
    md.append(f"- spec `{it['spec']}` -> maybe {it.get('maybe_model') or it.get('maybe_db')}")
  OUT_MD.write_text("\n".join(md),encoding="utf-8")

  # ===== Patch plan (do not modify DB in this card) =====
  # Suggest new tables for each dimension
  table_suggest = {
    "单位(客户/供应商)": "aux_parties",
    "个人(员工/往来主体)": "aux_persons",
    "项目": "aux_projects",
    "银行账户": "aux_bank_accounts"
  }
  plan={"tables":{}, "notes":[]}
  for dim,v in per.items():
    plan["tables"][table_suggest.get(dim, dim)] = {
      "dimension": dim,
      "spec_source": v["spec_source"],
      "missing_in_db": v["missing_in_db"],
      "missing_in_model": v["missing_in_model"],
      "suggest_primary_key": "code" if "单位" in dim or "项目" in dim else "id",
      "suggest_indexes": ["code","name","credit_code"] if "单位" in dim else ["code","name"],
    }

  plan["notes"].append("本卡仅生成补充完善计划，不做迁移/建模落库。下一卡 AUXDIM-FIELD-02 执行落地（新表+模型+最小CRUD）。")
  plan["notes"].append("项目维度字段为 assumption，可用你的项目字段规范替换后再落地。")

  PLAN_JSON.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
  mdp=[]
  mdp.append("# AUXDIM-FIELD-01 补充完善计划（Patch Plan）")
  mdp.append("")
  for t,info in plan["tables"].items():
    mdp.append(f"## {t}  <- {info['dimension']} (source={info['spec_source']})")
    mdp.append(f"- missing_in_db: {len(info['missing_in_db'])}")
    mdp.append(f"- missing_in_model: {len(info['missing_in_model'])}")
    if info["missing_in_db"][:25]:
      mdp.append("### 缺失字段（DB，抽样）")
      for f in info["missing_in_db"][:25]:
        mdp.append(f"- `{f}`")
    mdp.append("")
  mdp.append("## Notes")
  for n in plan["notes"]:
    mdp.append(f"- {n}")
  PLAN_MD.write_text("\n".join(mdp),encoding="utf-8")

  print("WROTE", OUT_JSON)
  print("WROTE", OUT_MD)
  print("WROTE", PLAN_JSON)
  print("WROTE", PLAN_MD)
  print("SUMMARY", s)

if __name__=="__main__":
  main()
