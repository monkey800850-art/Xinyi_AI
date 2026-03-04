import os
import sys
import importlib

# Ensure repo root on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

def main():
    try:
        rb = importlib.import_module("app.services.ledger_running_balance")
        gv = importlib.import_module("app.services.ledger_group_view")
    except ModuleNotFoundError as e:
        # Hard fail with actionable message
        raise SystemExit(f"[FAIL] import error: {e}. "
                         f"Hint: this invariant test must only import app.services.* modules; "
                         f"if flask is required during import, isolate it behind runtime-only routes.") from e

    # Anchor symbols (contract)
    assert hasattr(rb, "_rq13_is_group_first_row"), "Missing group-first gate helper (_rq13_is_group_first_row)"
    assert hasattr(rb, "_rq13_group_key"), "Missing group key extractor (_rq13_group_key)"
    assert hasattr(gv, "_rq13_recalc_subtotal_closing"), "Missing subtotal closing recalculator (_rq13_recalc_subtotal_closing)"

    # closing = opening + period
    subtotal = {"opening_amount": 10.0, "period_amount": 60.0, "closing_amount": -999.0}
    out = gv._rq13_recalc_subtotal_closing(subtotal)
    assert out["closing_amount"] == 70.0, f"closing formula mismatch: {out}"

    # opening only on group-first
    row1 = {"group_key": "G1", "opening_amount": 10.0, "row_type": "group_first"}
    row2 = {"group_key": "G1", "opening_amount": 10.0}
    assert rb._rq13_is_group_first_row(row1, None) is True
    assert rb._rq13_is_group_first_row(row2, "G1") is False

    print("[OK] REPORTS-QUERY-13 invariants passed.")

if __name__ == "__main__":
    main()
