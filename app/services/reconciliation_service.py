from __future__ import annotations

from typing import Dict, List

from sqlalchemy import text

from app.db import get_engine
from app.services.bank_reconcile_service import ReconcileError


def _default_rules() -> List[Dict[str, object]]:
    return [
        {"rule_id": "R001", "description": "Amount matches", "enabled": True},
        {"rule_id": "R002", "description": "Date matches", "enabled": True},
        {"rule_id": "R003", "description": "Summary similarity", "enabled": True},
    ]


def _default_reasons() -> List[Dict[str, object]]:
    return [
        {"reason_id": "D001", "description": "Amount mismatch"},
        {"reason_id": "D002", "description": "Date mismatch"},
        {"reason_id": "D003", "description": "Counterparty mismatch"},
    ]


def get_reconciliation_rules() -> List[Dict[str, object]]:
    # Built-in rules + optional extension from sys_rules: reconcile_rule:<id>=<description>
    items = list(_default_rules())
    engine = get_engine()
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text(
                    """
                    SELECT rule_key, rule_value
                    FROM sys_rules
                    WHERE rule_key LIKE 'reconcile_rule:%'
                    ORDER BY rule_key ASC
                    """
                )
            ).fetchall()
        except Exception:
            rows = []
    for r in rows:
        key = str(getattr(r, "rule_key", "") or "")
        rid = key.split(":", 1)[1] if ":" in key else key
        items.append({"rule_id": rid, "description": str(getattr(r, "rule_value", "") or ""), "enabled": True})
    return items


def get_discrepancy_reasons() -> List[Dict[str, object]]:
    # Built-in reasons + optional extension from sys_rules: reconcile_reason:<id>=<description>
    items = list(_default_reasons())
    engine = get_engine()
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text(
                    """
                    SELECT rule_key, rule_value
                    FROM sys_rules
                    WHERE rule_key LIKE 'reconcile_reason:%'
                    ORDER BY rule_key ASC
                    """
                )
            ).fetchall()
        except Exception:
            rows = []
    for r in rows:
        key = str(getattr(r, "rule_key", "") or "")
        rid = key.split(":", 1)[1] if ":" in key else key
        items.append({"reason_id": rid, "description": str(getattr(r, "rule_value", "") or "")})
    return items


def _upsert_reconcile_row(conn, txn_id: int, voucher_id: int | None, reason: str):
    dialect = str(conn.engine.dialect.name or "").lower()
    if dialect == "sqlite":
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations (
                    bank_transaction_id, voucher_id, status, match_score, match_reason
                ) VALUES (
                    :txn_id, :voucher_id, 'confirmed', 100, :reason
                )
                ON CONFLICT(bank_transaction_id) DO UPDATE SET
                    voucher_id=excluded.voucher_id,
                    status='confirmed',
                    match_score=100,
                    match_reason=excluded.match_reason
                """
            ),
            {"txn_id": txn_id, "voucher_id": voucher_id, "reason": reason},
        )
    else:
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations (
                    bank_transaction_id, voucher_id, status, match_score, match_reason
                ) VALUES (
                    :txn_id, :voucher_id, 'confirmed', 100, :reason
                )
                ON DUPLICATE KEY UPDATE
                    voucher_id=VALUES(voucher_id),
                    status='confirmed',
                    match_score=100,
                    match_reason=VALUES(match_reason)
                """
            ),
            {"txn_id": txn_id, "voucher_id": voucher_id, "reason": reason},
        )


def bulk_confirm_reconciliation(records: List[Dict[str, object]], operator: str, role: str) -> Dict[str, object]:
    if role not in ("cashier", "approver", "admin"):
        raise ReconcileError("permission_denied")
    if not operator:
        raise ReconcileError("operator_required")
    if not isinstance(records, list) or not records:
        raise ReconcileError("records_required")

    success = 0
    failed = 0
    failed_items: List[Dict[str, object]] = []

    engine = get_engine()
    with engine.begin() as conn:
        for i, rec in enumerate(records):
            if not isinstance(rec, dict):
                failed += 1
                failed_items.append({"index": i, "error": "record_must_be_object"})
                continue
            try:
                txn_id = int(rec.get("bank_transaction_id"))
            except Exception:
                failed += 1
                failed_items.append({"index": i, "error": "invalid_bank_transaction_id"})
                continue
            voucher_id_raw = rec.get("voucher_id")
            voucher_id = None
            if voucher_id_raw not in (None, ""):
                try:
                    voucher_id = int(voucher_id_raw)
                except Exception:
                    failed += 1
                    failed_items.append({"index": i, "bank_transaction_id": txn_id, "error": "invalid_voucher_id"})
                    continue

            row = conn.execute(
                text("SELECT match_status FROM bank_transactions WHERE id=:id"),
                {"id": txn_id},
            ).fetchone()
            if not row:
                failed += 1
                failed_items.append({"index": i, "bank_transaction_id": txn_id, "error": "bank_transaction_not_found"})
                continue

            reason = str(rec.get("reason") or rec.get("reason_id") or "bulk_confirm")
            from_status = str(getattr(row, "match_status", "") or "unmatched")
            _upsert_reconcile_row(conn, txn_id, voucher_id, reason)
            conn.execute(
                text(
                    """
                    UPDATE bank_transactions
                    SET match_status='confirmed', matched_voucher_id=:voucher_id
                    WHERE id=:id
                    """
                ),
                {"id": txn_id, "voucher_id": voucher_id},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO bank_reconciliation_logs (
                        bank_transaction_id, voucher_id, action, from_status, to_status, operator, operator_role, comment
                    ) VALUES (
                        :txn_id, :voucher_id, 'bulk_confirm', :from_status, 'confirmed', :operator, :role, :comment
                    )
                    """
                ),
                {
                    "txn_id": txn_id,
                    "voucher_id": voucher_id,
                    "from_status": from_status,
                    "operator": operator,
                    "role": role,
                    "comment": reason,
                },
            )
            success += 1

    return {"total": len(records), "success": success, "failed": failed, "failed_items": failed_items}
