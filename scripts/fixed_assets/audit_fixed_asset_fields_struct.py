import os, re, json
from pathlib import Path

OUT_JSON = Path("evidence/FA-FIELD-01/fa_struct_audit.json")
OUT_MD   = Path("evidence/FA-FIELD-01/fa_struct_audit.md")
PLAN_JSON= Path("evidence/FA-FIELD-01/fa_patch_plan.json")
PLAN_MD  = Path("evidence/FA-FIELD-01/fa_patch_plan.md")

SCAN_EXT = {".py",".sql"}
SCAN_DIRS = ["app","migrations","scripts"]

# ===== Spec fields (derived from uploaded doc “固定资产管理功能字段”) =====
# 规范点：资产卡片、价值税务、责任与盘点、电子凭证合规、多法人、多账簿折旧建议分表等。
SPEC = {
  "fa_assets": {
    "spec_source": "doc",
    "fields": [
      "asset_code","asset_name","spec_model","asset_category","uom","quantity",
      "in_service_date","economic_use","use_status",
      "book_date","capitalized_date",
      "original_cost_excl_tax","input_vat_amount","original_cost_incl_tax",
      "salvage_rate","salvage_value",
      "depreciation_method","useful_life_months",
      "accumulated_depreciation","impairment_reserve","net_book_value",
      "funding_source",
      "gl_asset_subject","gl_acc_dep_subject","gl_dep_expense_subject",
      "using_department_id","storage_location_id",
      "responsible_person_id","custodian_person_id",
      "vendor_name","purchase_contract_no",
      "warranty_end_date","next_inventory_date",
      "tag_qr_payload",
      "invoice_number","invoice_code",
      "e_voucher_xml_ofd_path",
      "acceptance_doc_no",
      "posting_voucher_no",
      "archive_status",
      "project_code",
      "env_safety_level",
      "tech_params_json",
      "remarks",
      "legal_entity_id",
      "audit_trail_required_flag",
      "multi_book_depreciation_flag"
    ]
  },
  "fa_depreciation_books": {
    "spec_source": "doc",
    "fields": [
      "asset_id",
      "book_type",
      "depreciation_method",
      "useful_life_months",
      "salvage_rate",
      "salvage_value",
      "accumulated_depreciation",
      "net_book_value",
      "last_dep_period"
    ]
  }
}

ALIASES = {
  "asset_code":["asset_code","fa_code"],
  "asset_name":["asset_name","name"],
  "spec_model":["spec_model","model"],
  "asset_category":["asset_category","category"],
  "in_service_date":["in_service_date","start_use_date"],
  "original_cost_excl_tax":["original_cost_excl_tax","original_cost"],
  "input_vat_amount":["input_vat_amount","vat_amount"],
  "depreciation_method":["depreciation_method","dep_method"],
  "useful_life_months":["useful_life_months","useful_life"],
  "accumulated_depreciation":["accumulated_depreciation","acc_dep"],
  "net_book_value":["net_book_value","nbv"],
  "legal_entity_id":["legal_entity_id","entity_id"],
  "invoice_number":["invoice_number","fapiao_no"],
  "invoice_code":["invoice_code","fapiao_code"],
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
  kws=["fixed","asset","fa_","depreciation","dep_","inventory","invoice","voucher","固定资产","资产","折旧","盘点","处置","报废"]
  return any(k in s for k in kws)

def flatten_spec():
  pairs=[]
  for table,obj in SPEC.items():
    for f in obj["fields"]:
      pairs.append((table,f))
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
  for table,obj in SPEC.items():
    fset=set(obj["fields"])
    per[table]={
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
    "per_table": per,
  }

  OUT_JSON.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")

  s=res["summary"]
  md=[]
  md.append("# FA-FIELD-01 固定资产字段结构级审计（Model/Migration/DDL）")
  md.append("")
  md.append(f"- spec_count: **{s['spec_count']}**")
  md.append(f"- model_count: **{s['model_count']}**")
  md.append(f"- db_count: **{s['db_count']}**")
  md.append(f"- missing_in_model_count: **{s['missing_in_model_count']}**")
  md.append(f"- missing_in_db_count: **{s['missing_in_db_count']}**")
  md.append(f"- mismatch_count: **{s['mismatch_count']}**")
  md.append("")
  md.append("## 分表缺口")
  for t,v in per.items():
    md.append(f"\n### {t} (spec={v['spec_count']})")
    md.append(f"- missing_in_model: {len(v['missing_in_model'])}")
    md.append(f"- missing_in_db: {len(v['missing_in_db'])}")
  md.append("\n## 命名疑似不一致（alias 命中）")
  for it in mismatch[:200]:
    md.append(f"- spec `{it['spec']}` -> maybe {it.get('maybe_model') or it.get('maybe_db')}")
  OUT_MD.write_text("\n".join(md),encoding="utf-8")

  plan={"tables":{}, "notes":[]}
  for t,v in per.items():
    plan["tables"][t]={
      "missing_in_db": v["missing_in_db"],
      "missing_in_model": v["missing_in_model"],
      "suggest_primary_key": "id",
      "suggest_indexes": ["asset_code"] if t=="fa_assets" else ["asset_id","book_type"],
    }
  plan["notes"].append("本卡仅审计+计划；下一卡 FA-FIELD-02 执行落地（新表+模型+最小入口）。")
  plan["notes"].append("强建议折旧多账簿分表（fa_depreciation_books）。")
  PLAN_JSON.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")

  mdp=[]
  mdp.append("# FA-FIELD-01 补充完善计划（Patch Plan）")
  for t,info in plan["tables"].items():
    mdp.append(f"\n## {t}")
    mdp.append(f"- missing_in_db: {len(info['missing_in_db'])}")
    mdp.append(f"- missing_in_model: {len(info['missing_in_model'])}")
    if info["missing_in_db"][:20]:
      mdp.append("### 缺失字段（DB，抽样）")
      for f in info["missing_in_db"][:20]:
        mdp.append(f"- `{f}`")
  mdp.append("\n## Notes")
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
