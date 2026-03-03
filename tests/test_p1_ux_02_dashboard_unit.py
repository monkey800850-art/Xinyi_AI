import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.user_dashboard_service import (
    get_role_dashboard,
    send_reminder,
    track_task_status,
)


class P1Ux02DashboardUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="ux02_dash_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS reimbursements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        status TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS bank_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        match_status TEXT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payment_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        status TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tax_invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        verification_status TEXT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tax_difference_ledger (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        diff_amount NUMERIC NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_approval_flows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        approval_status TEXT NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_audit_packages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        status TEXT NOT NULL
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
            for t in (
                "reimbursements",
                "bank_transactions",
                "payment_requests",
                "tax_invoices",
                "tax_difference_ledger",
                "consolidation_approval_flows",
                "consolidation_audit_packages",
            ):
                conn.execute(text(f"DELETE FROM {t}"))
            conn.execute(text("INSERT INTO reimbursements (book_id, status) VALUES (1, 'in_review')"))
            conn.execute(text("INSERT INTO bank_transactions (book_id, match_status) VALUES (1, 'unmatched')"))
            conn.execute(text("INSERT INTO payment_requests (book_id, status) VALUES (1, 'approved')"))
            conn.execute(text("INSERT INTO tax_invoices (book_id, verification_status) VALUES (1, 'pending')"))
            conn.execute(text("INSERT INTO tax_difference_ledger (book_id, diff_amount) VALUES (1, 12.34)"))
            conn.execute(text("INSERT INTO consolidation_approval_flows (approval_status) VALUES ('submitted')"))
            conn.execute(text("INSERT INTO consolidation_audit_packages (status) VALUES ('draft')"))

    def test_role_dashboard_and_tracking_and_reminder(self):
        with patch("app.services.user_dashboard_service.get_engine", return_value=self.engine):
            board = get_role_dashboard("财务经理", 1)
            self.assertEqual(board["role"], "finance_manager")
            self.assertGreaterEqual(board["pending_total"], 1)
            self.assertGreaterEqual(board["task_count"], 2)

            st = track_task_status("cashier", "payment_execute", 1)
            self.assertEqual(st["task_code"], "payment_execute")
            self.assertEqual(st["status"], "处理中")

            r = send_reminder(
                role="tax",
                task_code="tax_invoice_verify",
                operator="tester",
                operator_role="admin",
                assignee="user_a",
                book_id=1,
                note="请今日完成",
            )
            self.assertEqual(r["status"], "sent")
            self.assertTrue(int(r["id"]) > 0)

            board2 = get_role_dashboard("tax", 1)
            row = [x for x in board2["tasks"] if x["task_code"] == "tax_invoice_verify"][0]
            self.assertGreaterEqual(int(row["reminder_count_today"]), 1)


if __name__ == "__main__":
    unittest.main()
