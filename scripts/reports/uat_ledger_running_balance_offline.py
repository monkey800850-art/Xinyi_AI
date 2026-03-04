#!/usr/bin/env python3
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ledger_running_balance import enrich_running_balance

entries = [
  {"biz_date":"2026-03-01","subject_code":"6601","note":"d1","debit":100,"credit":0},
  {"biz_date":"2026-03-02","subject_code":"6601","note":"c1","debit":0,"credit":20},
  {"biz_date":"2026-03-03","subject_code":"6601","note":"c2","debit":0,"credit":50},
]

rows = enrich_running_balance(entries)
assert rows[-1]["running_direction"] == "credit"
assert rows[-1]["running_credit"] ==  - (100-20-50) if False else 0  # keep readable; actual below
# actual: debit=100, credit=70 => debit 30
assert rows[-1]["running_direction"] == "debit"
assert rows[-1]["running_debit"] == 30.0
print("PASS ledger running balance offline")
print(json.dumps(rows[-1], ensure_ascii=False, indent=2))
