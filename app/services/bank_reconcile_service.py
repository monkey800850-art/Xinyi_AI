from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine


class ReconcileError(RuntimeError):
    pass


def _log_action(conn, bank_transaction_id: int, voucher_id: int, action: str, from_status: str, to_status: str, operator: str, role: str, comment: str = None):
    conn.execute(
        text(
            """
            INSERT INTO bank_reconciliation_logs (
                bank_transaction_id, voucher_id, action, from_status, to_status, operator, operator_role, comment
            ) VALUES (
                :txn_id, :voucher_id, :action, :from_status, :to_status, :operator, :role, :comment
            )
            """
        ),
        {
            "txn_id": bank_transaction_id,
            "voucher_id": voucher_id,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "operator": operator,
            "role": role,
            "comment": comment,
        },
    )


def list_reconciliation_items(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    bank_account_raw = (params.get("bank_account_id") or "").strip()
    if not book_id_raw:
        raise ReconcileError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReconcileError("book_id must be integer")

    bank_account_id = None
    if bank_account_raw:
        try:
            bank_account_id = int(bank_account_raw)
        except Exception:
            raise ReconcileError("bank_account_id must be integer")

    sql = """
        SELECT bt.id, bt.bank_account_id, bt.txn_date, bt.amount, bt.summary, bt.counterparty,
               bt.balance, bt.match_status, bt.matched_voucher_id,
               v.voucher_date, v.voucher_word, v.voucher_no
        FROM bank_transactions bt
        LEFT JOIN vouchers v ON v.id = bt.matched_voucher_id
        WHERE bt.book_id = :book_id
    """
    params_sql = {"book_id": book_id}
    if bank_account_id:
        sql += " AND bt.bank_account_id=:bank_account_id"
        params_sql["bank_account_id"] = bank_account_id
    sql += " ORDER BY bt.txn_date DESC, bt.id DESC LIMIT 200"

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params_sql).fetchall()

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "bank_account_id": r.bank_account_id,
                "txn_date": r.txn_date.isoformat(),
                "amount": float(r.amount),
                "summary": r.summary or "",
                "counterparty": r.counterparty or "",
                "balance": float(r.balance) if r.balance is not None else None,
                "match_status": r.match_status,
                "matched_voucher_id": r.matched_voucher_id or "",
                "voucher_date": r.voucher_date.isoformat() if r.voucher_date else "",
                "voucher_no": (r.voucher_word or "") + (r.voucher_no or ""),
            }
        )

    return {"book_id": book_id, "items": items}


def auto_match(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    bank_account_raw = (params.get("bank_account_id") or "").strip()
    tolerance_raw = (params.get("date_tolerance") or "").strip() or "3"

    if not book_id_raw:
        raise ReconcileError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReconcileError("book_id must be integer")

    bank_account_id = None
    if bank_account_raw:
        try:
            bank_account_id = int(bank_account_raw)
        except Exception:
            raise ReconcileError("bank_account_id must be integer")

    try:
        tolerance_days = int(tolerance_raw)
    except Exception:
        raise ReconcileError("date_tolerance must be integer")

    engine = get_engine()
    matched = 0

    with engine.begin() as conn:
        sql_txn = """
            SELECT id, txn_date, amount, summary
            FROM bank_transactions
            WHERE book_id=:book_id AND match_status='unmatched'
        """
        params_txn = {"book_id": book_id}
        if bank_account_id:
            sql_txn += " AND bank_account_id=:bank_account_id"
            params_txn["bank_account_id"] = bank_account_id
        rows = conn.execute(text(sql_txn), params_txn).fetchall()

        for r in rows:
            start = r.txn_date - timedelta(days=tolerance_days)
            end = r.txn_date + timedelta(days=tolerance_days)

            vsql = """
                SELECT v.id, v.voucher_date, v.voucher_word, v.voucher_no,
                       SUM(vl.debit) AS debit_sum, SUM(vl.credit) AS credit_sum,
                       MAX(vl.summary) AS any_summary
                FROM vouchers v
                JOIN voucher_lines vl ON vl.voucher_id = v.id
                WHERE v.book_id=:book_id
                  AND v.status='posted'
                  AND v.voucher_date BETWEEN :start_date AND :end_date
                GROUP BY v.id
                HAVING ABS(SUM(vl.debit) - :amt) < 0.01 OR ABS(SUM(vl.credit) - :amt) < 0.01
                LIMIT 5
            """
            vrows = conn.execute(
                text(vsql),
                {
                    "book_id": book_id,
                    "start_date": start,
                    "end_date": end,
                    "amt": abs(Decimal(str(r.amount))),
                },
            ).fetchall()

            if not vrows:
                continue

            # pick best by summary similarity
            best = None
            best_score = -1
            for v in vrows:
                score = 60
                if r.summary and v.any_summary and (r.summary in v.any_summary or v.any_summary in r.summary):
                    score += 20
                if v.voucher_date == r.txn_date:
                    score += 20
                if score > best_score:
                    best_score = score
                    best = v

            if not best:
                continue

            conn.execute(
                text(
                    """
                    INSERT INTO bank_reconciliations (
                        bank_transaction_id, voucher_id, status, match_score, match_reason
                    ) VALUES (
                        :txn_id, :voucher_id, 'matched', :score, :reason
                    )
                    ON DUPLICATE KEY UPDATE
                        voucher_id=VALUES(voucher_id), status='matched', match_score=VALUES(match_score), match_reason=VALUES(match_reason)
                    """
                ),
                {
                    "txn_id": r.id,
                    "voucher_id": best.id,
                    "score": best_score,
                    "reason": "amount/date/summary",
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE bank_transactions
                    SET match_status='matched', matched_voucher_id=:vid
                    WHERE id=:id
                    """
                ),
                {"vid": best.id, "id": r.id},
            )
            _log_action(conn, r.id, best.id, "auto_match", "unmatched", "matched", "system", "system")
            matched += 1

    return {"matched": matched}


def confirm_match(bank_transaction_id: int, voucher_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise ReconcileError("operator_required")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT match_status FROM bank_transactions WHERE id=:id"),
            {"id": bank_transaction_id},
        ).fetchone()
        if not row:
            raise ReconcileError("bank_transaction_not_found")

        from_status = row.match_status
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations (
                    bank_transaction_id, voucher_id, status, match_score, match_reason
                ) VALUES (
                    :txn_id, :voucher_id, 'confirmed', 100, 'manual'
                )
                ON DUPLICATE KEY UPDATE
                    voucher_id=VALUES(voucher_id), status='confirmed', match_score=100, match_reason='manual'
                """
            ),
            {"txn_id": bank_transaction_id, "voucher_id": voucher_id},
        )
        conn.execute(
            text(
                "UPDATE bank_transactions SET match_status='confirmed', matched_voucher_id=:vid WHERE id=:id"
            ),
            {"vid": voucher_id, "id": bank_transaction_id},
        )
        _log_action(conn, bank_transaction_id, voucher_id, "confirm", from_status, "confirmed", operator, role)

    return {"bank_transaction_id": bank_transaction_id, "voucher_id": voucher_id, "status": "confirmed"}


def cancel_match(bank_transaction_id: int, operator: str, role: str) -> Dict[str, object]:
    if not operator:
        raise ReconcileError("operator_required")

    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT match_status, matched_voucher_id FROM bank_transactions WHERE id=:id"),
            {"id": bank_transaction_id},
        ).fetchone()
        if not row:
            raise ReconcileError("bank_transaction_not_found")

        from_status = row.match_status
        conn.execute(
            text(
                "UPDATE bank_transactions SET match_status='unmatched', matched_voucher_id=NULL WHERE id=:id"
            ),
            {"id": bank_transaction_id},
        )
        conn.execute(
            text(
                "UPDATE bank_reconciliations SET status='unmatched' WHERE bank_transaction_id=:id"
            ),
            {"id": bank_transaction_id},
        )
        _log_action(conn, bank_transaction_id, row.matched_voucher_id or None, "cancel", from_status, "unmatched", operator, role)

    return {"bank_transaction_id": bank_transaction_id, "status": "unmatched"}


def get_reconcile_report(params: Dict[str, str]) -> Dict[str, object]:
    book_id_raw = (params.get("book_id") or "").strip()
    bank_account_raw = (params.get("bank_account_id") or "").strip()
    if not book_id_raw:
        raise ReconcileError("book_id required")
    try:
        book_id = int(book_id_raw)
    except Exception:
        raise ReconcileError("book_id must be integer")

    bank_account_id = None
    if bank_account_raw:
        try:
            bank_account_id = int(bank_account_raw)
        except Exception:
            raise ReconcileError("bank_account_id must be integer")

    sql = """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN match_status='unmatched' THEN 1 ELSE 0 END) AS unmatched_count,
               SUM(CASE WHEN match_status='unmatched' THEN amount ELSE 0 END) AS unmatched_amount,
               SUM(CASE WHEN match_status!='unmatched' THEN amount ELSE 0 END) AS matched_amount,
               MAX(balance) AS latest_balance
        FROM bank_transactions
        WHERE book_id=:book_id
    """
    params_sql = {"book_id": book_id}
    if bank_account_id:
        sql += " AND bank_account_id=:bank_account_id"
        params_sql["bank_account_id"] = bank_account_id

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(sql), params_sql).fetchone()

    return {
        "book_id": book_id,
        "bank_account_id": bank_account_id or "",
        "total": int(row.total or 0),
        "unmatched_count": int(row.unmatched_count or 0),
        "unmatched_amount": float(Decimal(str(row.unmatched_amount or 0))),
        "matched_amount": float(Decimal(str(row.matched_amount or 0))),
        "latest_balance": float(Decimal(str(row.latest_balance or 0))) if row.latest_balance is not None else None,
    }
