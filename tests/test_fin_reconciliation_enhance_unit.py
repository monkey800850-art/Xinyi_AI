import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.reconciliation_service import (
    bulk_confirm_reconciliation,
    get_discrepancy_reasons,
    get_reconciliation_rules,
)


class ReconciliationEnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="reconcile_enh_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS bank_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        match_status TEXT NOT NULL DEFAULT 'unmatched',
                        matched_voucher_id INTEGER NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS bank_reconciliations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bank_transaction_id INTEGER NOT NULL UNIQUE,
                        voucher_id INTEGER NULL,
                        status TEXT NOT NULL,
                        match_score INTEGER NOT NULL DEFAULT 0,
                        match_reason TEXT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS bank_reconciliation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bank_transaction_id INTEGER NOT NULL,
                        voucher_id INTEGER NULL,
                        action TEXT NOT NULL,
                        from_status TEXT NOT NULL,
                        to_status TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        operator_role TEXT NOT NULL,
                        comment TEXT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sys_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_key TEXT NOT NULL,
                        rule_value TEXT NULL
                    )
                    """
                )
            )

    @classmethod
    def tearDownClass(cls):
        try:
            cls.engine.dispose()
        finally:
            if cls.db_path.exists():
                cls.db_path.unlink()

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM bank_reconciliation_logs"))
            conn.execute(text("DELETE FROM bank_reconciliations"))
            conn.execute(text("DELETE FROM bank_transactions"))
            conn.execute(text("DELETE FROM sys_rules"))

    def test_rule_and_reason_library_with_extensions(self):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO sys_rules (rule_key, rule_value)
                    VALUES
                    ('reconcile_rule:R100', 'Counterparty exact'),
                    ('reconcile_reason:D900', 'Bank fee timing difference')
                    """
                )
            )
        with patch("app.services.reconciliation_service.get_engine", return_value=self.engine):
            rules = get_reconciliation_rules()
            reasons = get_discrepancy_reasons()
        self.assertTrue(any(str(x.get("rule_id")) == "R100" for x in rules))
        self.assertTrue(any(str(x.get("reason_id")) == "D900" for x in reasons))

    def test_bulk_confirm(self):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO bank_transactions (id, match_status, matched_voucher_id)
                    VALUES (101, 'unmatched', NULL), (102, 'matched', 5002)
                    """
                )
            )
        with patch("app.services.reconciliation_service.get_engine", return_value=self.engine):
            out = bulk_confirm_reconciliation(
                [
                    {"bank_transaction_id": 101, "voucher_id": 9001, "reason_id": "D001"},
                    {"bank_transaction_id": 102, "voucher_id": 9002, "reason": "manual_adjust"},
                ],
                operator="checker_a",
                role="admin",
            )
        self.assertEqual(int(out["total"]), 2)
        self.assertEqual(int(out["success"]), 2)
        self.assertEqual(int(out["failed"]), 0)

        with self.engine.connect() as conn:
            txns = conn.execute(
                text("SELECT id, match_status, matched_voucher_id FROM bank_transactions ORDER BY id ASC")
            ).fetchall()
            self.assertEqual(str(txns[0].match_status), "confirmed")
            self.assertEqual(int(txns[0].matched_voucher_id), 9001)
            self.assertEqual(str(txns[1].match_status), "confirmed")
            self.assertEqual(int(txns[1].matched_voucher_id), 9002)

            cnt_logs = conn.execute(text("SELECT COUNT(*) AS c FROM bank_reconciliation_logs")).fetchone()
            self.assertEqual(int(cnt_logs.c), 2)


if __name__ == "__main__":
    unittest.main()
