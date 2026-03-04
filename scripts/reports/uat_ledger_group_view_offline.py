#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ledger_running_balance import enrich_running_balance_grouped
from app.services.ledger_group_view import build_grouped_ledger

entries = [
  {"biz_date":"2026-03-01","subject_code":"6601","note":"A d1","aux_person_id":"A","debit":100,"credit":0},
  {"biz_date":"2026-03-02","subject_code":"6601","note":"A c1","aux_person_id":"A","debit":0,"credit":20},
  {"biz_date":"2026-03-03","subject_code":"6601","note":"B d1","aux_person_id":"B","debit":50,"credit":0},
  {"biz_date":"2026-03-04","subject_code":"6601","note":"B c1","aux_person_id":"B","debit":0,"credit":10},
]

rows = enrich_running_balance_grouped(entries, ["aux_person_id","subject_code"])
# group by person + subject (simulate your multi-dim grouping)
groups = build_grouped_ledger(rows, ["aux_person_id","subject_code"])

assert len(groups)==2
ga = next(g for g in groups if g["key"]["aux_person_id"]=="A")
gb = next(g for g in groups if g["key"]["aux_person_id"]=="B")

assert ga["subtotal"]["period_debit"]==100.0
assert ga["subtotal"]["period_credit"]==20.0
assert ga["subtotal"]["closing_direction"]=="debit"
assert ga["subtotal"]["closing_amount"]==80.0

assert gb["subtotal"]["period_debit"]==50.0
assert gb["subtotal"]["period_credit"]==10.0
assert gb["subtotal"]["closing_direction"]=="debit"
assert gb["subtotal"]["closing_amount"]==40.0

print("PASS ledger grouped view offline")
print(json.dumps(groups, ensure_ascii=False, indent=2))
