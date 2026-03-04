#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# We can't import Flask app reliably in restricted env for HTTP calls,
# so we do a static import smoke + direct call for planner/engine helpers.
from app.services.ledger_engine import compute_trial_balance_from_entries

entries = [
  {"biz_date":"2026-03-01","subject_code":"6601","aux_person_id":"A","aux_department_id":"HR","debit":100,"credit":0},
]
rows = compute_trial_balance_from_entries(entries, ["aux_person_id","subject_code","aux_department_id"])
assert "period_debit" in rows[0] and "closing_debit" in rows[0] and "direction" in rows[0]
print("PASS engine tb offline structure")
print(json.dumps(rows[0], ensure_ascii=False, indent=2))
