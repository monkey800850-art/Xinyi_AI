#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.report_result_tree_vector import rows_to_tree_vector
from app.services.report_result_subtotals_vector import tree_to_lines_vector, overall_total_vector

rows = [
  {"aux_person_id":"A","subject_code":"6601","aux_department_id":"HR",
   "opening_debit":0,"opening_credit":0,"period_debit":100,"period_credit":20,"closing_debit":80,"closing_credit":0},
  {"aux_person_id":"B","subject_code":"6602","aux_department_id":"SALES",
   "opening_debit":0,"opening_credit":0,"period_debit":50,"period_credit":0,"closing_debit":50,"closing_credit":0},
]

tree = rows_to_tree_vector(rows, ["aux_person_id","subject_code","aux_department_id"])
lines = tree_to_lines_vector(tree)
tot = overall_total_vector(lines)

assert tot["period_debit"] == 150.0, tot
assert tot["period_credit"] == 20.0, tot
assert tot["closing_debit"] == 130.0, tot  # 80+50
print("PASS vector tree/subtotals")
print(json.dumps(tot, ensure_ascii=False, indent=2))
print("lines_count=", len(lines))
