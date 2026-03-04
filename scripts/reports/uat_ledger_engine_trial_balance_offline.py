#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ledger_engine import compute_trial_balance_from_entries

def must(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)

entries = [
  {"biz_date":"2026-03-01","subject_code":"6601","aux_person_id":"A","aux_department_id":"HR","debit":100,"credit":0},
  {"biz_date":"2026-03-02","subject_code":"6601","aux_person_id":"A","aux_department_id":"HR","debit":0,"credit":20},
  {"biz_date":"2026-03-03","subject_code":"6602","aux_person_id":"B","aux_department_id":"SALES","debit":50,"credit":0},
]

rows = compute_trial_balance_from_entries(entries, ["aux_person_id","subject_code","aux_department_id"])
must(len(rows)==2, f"expected 2 rows, got {len(rows)}")

a = next(r for r in rows if r["aux_person_id"]=="A")
must(a["period_debit"]==100.0, "A period_debit should be 100")
must(a["period_credit"]==20.0, "A period_credit should be 20")
must(a["closing_debit"]==80.0 and a["closing_credit"]==0.0 and a["direction"]=="debit", "A closing should be debit 80")

b = next(r for r in rows if r["aux_person_id"]=="B")
must(b["period_debit"]==50.0 and b["period_credit"]==0.0, "B movement mismatch")
must(b["closing_debit"]==50.0 and b["direction"]=="debit", "B closing should be debit 50")

print("PASS ledger engine trial balance offline")
print("rows=", rows)
