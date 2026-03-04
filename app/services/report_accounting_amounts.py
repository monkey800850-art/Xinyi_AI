"""
REPORTS-QUERY-07

Accounting balance structure helpers
"""

def calc_closing(open_debit, open_credit, period_debit, period_credit):

    debit = (open_debit or 0) + (period_debit or 0)
    credit = (open_credit or 0) + (period_credit or 0)

    if debit >= credit:
        return {
            "closing_debit": debit-credit,
            "closing_credit": 0,
            "direction":"debit"
        }

    return {
        "closing_debit":0,
        "closing_credit":credit-debit,
        "direction":"credit"
    }
