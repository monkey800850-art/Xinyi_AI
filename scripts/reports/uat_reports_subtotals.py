import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from app.services.report_result_tree import rows_to_tree
from app.services.report_result_subtotals import tree_to_lines, overall_total

rows = [
  {"aux_person_id":"A","subject_code":"6601","aux_department_id":"HR","amount":100},
  {"aux_person_id":"A","subject_code":"6602","aux_department_id":"HR","amount":50},
  {"aux_person_id":"B","subject_code":"6601","aux_department_id":"SALES","amount":80},
]
tree = rows_to_tree(rows, ["aux_person_id","subject_code","aux_department_id"])
lines = tree_to_lines(tree)
tot = overall_total(lines)

assert tot == 230, f"total should be 230, got {tot}"
# ensure subtotals exist
assert any(l["kind"]=="subtotal" and l["label"].startswith("小计(") for l in lines), "missing subtotals"
print("PASS subtotals")
print("total=", tot)
print("lines_count=", len(lines))
