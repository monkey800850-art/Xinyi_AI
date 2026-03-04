import json, os, re, sys
from pathlib import Path

REPO_ROOT = Path(".")
OUT_JSON = Path("evidence/PAYROLL-FIELD-01/payroll_field_audit.json")
OUT_MD   = Path("evidence/PAYROLL-FIELD-01/payroll_field_audit.md")

# === Spec fields (from 工资管理功能字段列表.docx) ===
# 员工基础信息：员工工号/姓名/身份证号/入离职/用工性质/部门/岗位职级/地点/银行卡/开户行/居民身份等 :contentReference[oaicite:5]{index=5}
# 薪资项目：基本工资/津贴/工龄/绩效/奖金/加班/提成/全勤/补贴/其他补发扣减等 :contentReference[oaicite:6]{index=6}
# 社保公积金：参保地、各险种基数、比例、企业承担额等 :contentReference[oaicite:7]{index=7}
# 个税累计预扣：累计收入/免税/减除/专项/附加/税率速算/本期税额/年终奖标识等 :contentReference[oaicite:8]{index=8}
# 考勤假期：计薪天数/出勤/事病假/旷工/迟到早退/加班(平日周末节日)/年假剩余等 :contentReference[oaicite:9]{index=9}
# 核算凭证：成本中心/应付职工薪酬科目/社保公积金科目/个税科目/凭证状态/凭证号/支付批次/支付状态等 :contentReference[oaicite:10]{index=10}

SPEC = {
  "员工基础信息": [
    "employee_no","name","id_card_no","hire_date","termination_date","employment_type",
    "department_id","job_grade","work_location","bank_account_no","bank_branch_info","tax_residency"
  ],
  "薪资项目固定项": ["base_salary","position_allowance","seniority_pay","fixed_performance"],
  "薪资项目变动项": ["performance_bonus","overtime_pay","commission","attendance_bonus","heat_allowance","other_adjustment"],
  "社保公积金": [
    "social_security_city","pension_base","medical_base","unemployment_base","injury_base","maternity_base",
    "housing_fund_base","social_housing_rate","employer_social_total"
  ],
  "个税累计预扣": [
    "ytd_income","ytd_tax_exempt_income","ytd_standard_deduction","ytd_social_housing_deduction",
    "ytd_special_additional_deduction","ytd_other_legal_deduction","ytd_taxable_income",
    "tax_rate","quick_deduction","current_withholding_tax","annual_bonus_separate_tax_flag"
  ],
  "考勤假期": [
    "payable_days","attendance_days","personal_leave_hours","sick_leave_hours","absent_days",
    "late_early_count","ot_hours_weekday","ot_hours_weekend","ot_hours_holiday","annual_leave_balance"
  ],
  "财务核算凭证": [
    "cost_center_code","payroll_payable_subject","social_housing_payable_subject","tax_payable_subject",
    "voucher_gen_status","voucher_no","pay_batch_no","pay_status"
  ]
}

# Heuristic aliases (to catch existing naming variants)
ALIASES = {
  "employee_no": ["employee_no","emp_no","staff_no","工号","员工工号"],
  "name": ["name","employee_name","姓名"],
  "id_card_no": ["id_card","id_card_no","identity_no","身份证","身份证号"],
  "department_id": ["department_id","dept_id","所属部门","部门"],
  "bank_account_no": ["bank_account","bank_account_no","银行卡","银行卡号"],
  "hire_date": ["hire_date","join_date","入职日期"],
  "termination_date": ["termination_date","leave_date","离职日期"],
  "base_salary": ["base_salary","basic_salary","基本工资"],
  "cost_center_code": ["cost_center_code","cost_center","成本中心","成本中心代码"],
  "voucher_no": ["voucher_no","voucher_number","关联凭证号","凭证号"],
}

# Repo scan targets
SCAN_EXT = {".py",".sql",".md",".html",".txt",".yml",".yaml",".json"}
SCAN_DIRS = ["app","migrations","scripts","docs"]

def read_text_safe(p: Path) -> str:
  try:
    return p.read_text(encoding="utf-8", errors="ignore")
  except Exception:
    return ""

def file_iter():
  for d in SCAN_DIRS:
    base = REPO_ROOT / d
    if not base.exists():
      continue
    for p in base.rglob("*"):
      if p.is_file() and p.suffix.lower() in SCAN_EXT:
        yield p

def find_hits(term_list):
  hits=[]
  patterns=[re.escape(t) for t in term_list]
  if not patterns:
    return hits
  rx=re.compile("|".join(patterns), re.IGNORECASE)
  for p in file_iter():
    txt=read_text_safe(p)
    if not txt:
      continue
    if rx.search(txt):
      # Keep evidence light: first 3 lines around first match
      m=rx.search(txt)
      if not m: 
        continue
      start=max(0, txt.rfind("\n",0,m.start())-200)
      end=min(len(txt), m.end()+200)
      snippet=txt[start:end].replace("\n"," ")
      hits.append({"file": str(p), "snippet": snippet[:380]})
  return hits[:25]  # cap

def audit():
  result={"spec":SPEC,"groups":{}, "summary":{}}
  total_spec=0
  total_hit=0
  missing=[]
  suspicious=[]

  for g, fields in SPEC.items():
    g_res=[]
    for f in fields:
      total_spec += 1
      terms = ALIASES.get(f, [f])
      hits = find_hits(terms)
      ok = len(hits) > 0
      if ok:
        total_hit += 1
      else:
        missing.append({"group":g,"field":f,"alias_terms":terms})
      # suspicious: found only Chinese/only vague match
      if ok and all(len(t)>1 and not re.match(r"^[a-zA-Z0-9_]+$", t) for t in terms):
        suspicious.append({"group":g,"field":f,"note":"alias list non-ascii; verify mapping"})
      g_res.append({"field":f,"ok":ok,"terms":terms,"hits":hits})
    result["groups"][g]=g_res

  result["summary"]={
    "total_spec_fields": total_spec,
    "hit_fields": total_hit,
    "missing_fields": len(missing),
    "missing": missing[:200],
    "suspicious": suspicious[:200]
  }
  return result

def md_render(audit):
  lines=[]
  s=audit["summary"]
  lines.append(f"# 工资管理字段对比审计报告 (PAYROLL-FIELD-01)")
  lines.append("")
  lines.append(f"- Spec字段总数: **{s['total_spec_fields']}**")
  lines.append(f"- 命中字段数(仓库扫描命中): **{s['hit_fields']}**")
  lines.append(f"- 缺失字段数: **{s['missing_fields']}**")
  lines.append("")
  lines.append("## 缺失字段（按模块）")
  cur=None
  for it in s["missing"]:
    if cur!=it["group"]:
      cur=it["group"]
      lines.append(f"\n### {cur}")
    lines.append(f"- `{it['field']}` (alias: {', '.join(it['alias_terms'][:5])})")
  lines.append("\n## 命中证据（每组抽样）")
  for g, rows in audit["groups"].items():
    ok_rows=[r for r in rows if r["ok"]]
    lines.append(f"\n### {g}（命中 {len(ok_rows)}/{len(rows)}）")
    for r in ok_rows[:6]:
      ex=r["hits"][0]
      lines.append(f"- `{r['field']}` -> `{ex['file']}`: {ex['snippet']}")
  lines.append("\n## 下一步落地建议（表拆分建议）")
  lines.append("- employee: 员工基础信息（工号/身份证/部门/岗位/银行卡/居民身份等）")
  lines.append("- payroll_record: 当期工资单（固定项+变动项+实发/应发/扣款汇总）")
  lines.append("- payroll_social_housing: 三险一金（个人/企业、基数、比例、缴纳地）")
  lines.append("- payroll_tax_ytd: 个税累计预扣字段（累计口径与本期税额）")
  lines.append("- attendance_snapshot: 考勤与假期（计薪天数/加班/请假等）")
  lines.append("- payroll_posting: 凭证生成与支付状态（成本中心/科目/凭证号/批次/状态）")
  return "\n".join(lines)

audit_res=audit()
OUT_JSON.write_text(json.dumps(audit_res,ensure_ascii=False,indent=2),encoding="utf-8")
OUT_MD.write_text(md_render(audit_res),encoding="utf-8")

print("WROTE", OUT_JSON)
print("WROTE", OUT_MD)
print("SUMMARY", audit_res["summary"])
