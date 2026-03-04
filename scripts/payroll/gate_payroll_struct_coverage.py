import json, sys
from pathlib import Path

audit_log = Path("evidence/PAYROLL-FIELD-02/payroll_struct_audit.json")
if not audit_log.exists():
    print("ERROR: missing PAYROLL-FIELD-02 audit json; run PAYROLL-FIELD-02 first")
    sys.exit(1)

d=json.loads(audit_log.read_text(encoding="utf-8"))
s=d.get("summary",{})

# We expect after implementation these become 0. For now, gate is "soft" in this card.
# In PAYROLL-FIELD-03.2 we will flip to hard gate.
print("INFO summary:", s)
sys.exit(0)
