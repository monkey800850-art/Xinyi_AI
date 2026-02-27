from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine
from app.services.ar_ap_service import get_warning_summary


class DashboardError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as err:
        raise DashboardError("invalid_date") from err


def get_workbench_metrics(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    if not book_id_raw:
        raise DashboardError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise DashboardError("book_id must be integer")

    engine = get_engine()
    with engine.connect() as conn:
        pending_vouchers = conn.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM vouchers WHERE book_id=:book_id AND status='draft'"
            ),
            {"book_id": book_id},
        ).fetchone().cnt

        pending_reimburse = conn.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM reimbursements WHERE book_id=:book_id AND status='in_review'"
            ),
            {"book_id": book_id},
        ).fetchone().cnt

        pending_payments = conn.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM payment_requests WHERE book_id=:book_id AND status='approved'"
            ),
            {"book_id": book_id},
        ).fetchone().cnt

        unmatched_bank = conn.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM bank_transactions WHERE book_id=:book_id AND match_status='unmatched'"
            ),
            {"book_id": book_id},
        ).fetchone().cnt

    arap = get_warning_summary({"book_id": str(book_id)})

    shortcuts = [
        {"label": "凭证录入", "url": "/voucher/entry"},
        {"label": "发生余额表", "url": "/reports/trial_balance"},
        {"label": "银行导入", "url": "/banks/import"},
        {"label": "银行对账", "url": "/banks/reconcile"},
        {"label": "报销管理", "url": "/reimbursements"},
        {"label": "支付申请", "url": "/payments"},
        {"label": "税务汇总", "url": "/tax/summary"},
    ]

    return {
        "book_id": book_id,
        "pending_vouchers": int(pending_vouchers),
        "pending_reimbursements": int(pending_reimburse),
        "pending_payments": int(pending_payments),
        "unmatched_bank_transactions": int(unmatched_bank),
        "arap_due_soon": arap["due_soon_count"],
        "arap_overdue": arap["overdue_count"],
        "shortcuts": shortcuts,
    }


def _sum_by_category(conn, book_id: int, start_date: date, end_date: date) -> Dict[str, Decimal]:
    rows = conn.execute(
        text(
            """
            SELECT s.category,
                   SUM(vl.debit) AS debit_sum,
                   SUM(vl.credit) AS credit_sum
            FROM voucher_lines vl
            JOIN vouchers v ON v.id = vl.voucher_id
            JOIN subjects s ON s.book_id = v.book_id AND s.code = vl.subject_code
            WHERE v.book_id=:book_id
              AND v.status='posted'
              AND v.voucher_date BETWEEN :start_date AND :end_date
            GROUP BY s.category
            """
        ),
        {"book_id": book_id, "start_date": start_date, "end_date": end_date},
    ).fetchall()

    result: Dict[str, Decimal] = {}
    for r in rows:
        category = (r.category or "").strip()
        debit = Decimal(str(r.debit_sum or 0))
        credit = Decimal(str(r.credit_sum or 0))
        result[category] = debit - credit
    return result


def get_boss_metrics(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    start_raw = (params.get("start_date") or "").strip()
    end_raw = (params.get("end_date") or "").strip()

    if not book_id_raw or not start_raw or not end_raw:
        raise DashboardError("book_id/start_date/end_date required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise DashboardError("book_id must be integer")

    start_date = _parse_date(start_raw)
    end_date = _parse_date(end_raw)

    engine = get_engine()
    with engine.connect() as conn:
        # cash: latest balance per bank account
        balances = conn.execute(
            text(
                """
                SELECT bank_account_id, MAX(txn_date) AS d
                FROM bank_transactions
                WHERE book_id=:book_id
                GROUP BY bank_account_id
                """
            ),
            {"book_id": book_id},
        ).fetchall()
        cash = Decimal("0")
        for b in balances:
            row = conn.execute(
                text(
                    """
                    SELECT balance FROM bank_transactions
                    WHERE book_id=:book_id AND bank_account_id=:bid AND txn_date=:d
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"book_id": book_id, "bid": b.bank_account_id, "d": b.d},
            ).fetchone()
            if row and row.balance is not None:
                cash += Decimal(str(row.balance))

        cats = _sum_by_category(conn, book_id, start_date, end_date)
        assets = abs(cats.get("资产", Decimal("0")))
        liabilities = abs(cats.get("负债", Decimal("0")))
        income = abs(cats.get("收入", Decimal("0")))
        expense = abs(cats.get("费用", Decimal("0")))
        profit = income - expense

        # trend: daily voucher total (debit) within range
        trend_rows = conn.execute(
            text(
                """
                SELECT v.voucher_date AS d, SUM(vl.debit) AS debit_sum
                FROM vouchers v
                JOIN voucher_lines vl ON vl.voucher_id = v.id
                WHERE v.book_id=:book_id AND v.status='posted'
                  AND v.voucher_date BETWEEN :start_date AND :end_date
                GROUP BY v.voucher_date
                ORDER BY v.voucher_date
                """
            ),
            {"book_id": book_id, "start_date": start_date, "end_date": end_date},
        ).fetchall()

    trend = [
        {"date": r.d.isoformat(), "value": float(r.debit_sum or 0)} for r in trend_rows
    ]

    arap = get_warning_summary({"book_id": str(book_id)})

    risk = {
        "arap_overdue": arap["overdue_count"],
        "arap_due_soon": arap["due_soon_count"],
    }

    return {
        "book_id": book_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "cash": float(cash),
        "assets": float(assets),
        "liabilities": float(liabilities),
        "profit": float(profit),
        "arap_due_soon": arap["due_soon_count"],
        "arap_overdue": arap["overdue_count"],
        "risk": risk,
        "trend": trend,
    }
