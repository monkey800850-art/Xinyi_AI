import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from app.services.report_accounting_amounts import calc_closing

r=calc_closing(100,0,50,20)

assert r["closing_debit"]==130
assert r["closing_credit"]==0

print("PASS accounting balance calc")
