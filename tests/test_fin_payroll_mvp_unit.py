import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.payroll_service import (
    confirm_payroll_slip,
    create_payroll_payment_request,
    get_payroll_voucher_suggestion,
    list_payroll_periods,
    list_payroll_slips,
    set_payroll_period_status,
    sync_attendance_interface,
    upsert_payroll_period,
    upsert_payroll_slip,
)


class PayrollMvpUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="payroll_mvp_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_periods (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'open',
                        locked_by INTEGER NULL,
                        locked_at DATETIME NULL,
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_slips (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        employee_id INTEGER NOT NULL,
                        employee_name TEXT NULL,
                        department TEXT NULL,
                        attendance_ref TEXT NULL,
                        attendance_days INTEGER NOT NULL DEFAULT 0,
                        absent_days INTEGER NOT NULL DEFAULT 0,
                        gross_amount NUMERIC NOT NULL DEFAULT 0,
                        deduction_amount NUMERIC NOT NULL DEFAULT 0,
                        social_insurance NUMERIC NOT NULL DEFAULT 0,
                        housing_fund NUMERIC NOT NULL DEFAULT 0,
                        bonus_amount NUMERIC NOT NULL DEFAULT 0,
                        overtime_amount NUMERIC NOT NULL DEFAULT 0,
                        taxable_base NUMERIC NOT NULL DEFAULT 0,
                        tax_amount NUMERIC NOT NULL DEFAULT 0,
                        net_amount NUMERIC NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'draft',
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_tax_ledger (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        tax_type TEXT NOT NULL,
                        taxable_base NUMERIC NOT NULL DEFAULT 0,
                        tax_amount NUMERIC NOT NULL DEFAULT 0,
                        calc_version TEXT NULL,
                        snapshot_json TEXT NULL,
                        created_at DATETIME NULL
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
                        title TEXT NULL,
                        payee_name TEXT NULL,
                        payee_account TEXT NULL,
                        pay_method TEXT NULL,
                        amount NUMERIC NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'draft',
                        related_type TEXT NULL,
                        related_id INTEGER NULL,
                        reimbursement_id INTEGER NULL,
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL
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
            conn.execute(text("DELETE FROM payment_requests"))
            conn.execute(text("DELETE FROM payroll_tax_ledger"))
            conn.execute(text("DELETE FROM payroll_slips"))
            conn.execute(text("DELETE FROM payroll_periods"))

    def test_payroll_period_slip_confirm_flow(self):
        with patch("app.services.payroll_service.get_engine", return_value=self.engine):
            p = upsert_payroll_period({"book_id": 1, "period": "2026-03", "status": "open"})
            self.assertEqual(p["status"], "open")

            periods = list_payroll_periods({"book_id": "1"})
            self.assertEqual(len(periods["items"]), 1)

            slip = upsert_payroll_slip(
                {
                    "book_id": 1,
                    "period": "2026-03",
                    "employee_id": 101,
                    "employee_name": "Alice",
                    "department": "FIN",
                    "attendance_ref": "ATT-202603-101",
                    "attendance_days": 21,
                    "absent_days": 1,
                    "gross_amount": "12000",
                    "deduction_amount": "300",
                    "social_insurance": "1000",
                    "housing_fund": "500",
                    "bonus_amount": "1000",
                    "overtime_amount": "500",
                }
            )
            self.assertGreater(slip["tax_amount"], 0)

            slips = list_payroll_slips({"book_id": "1", "period": "2026-03"})
            self.assertEqual(len(slips["items"]), 1)
            self.assertEqual(slips["items"][0]["status"], "draft")

            confirmed = confirm_payroll_slip(int(slip["id"]), "admin_user", "admin")
            self.assertEqual(confirmed["status"], "confirmed")

            suggestion = get_payroll_voucher_suggestion(int(slip["id"]))
            self.assertEqual(suggestion["status"], "confirmed")
            self.assertTrue(len(suggestion["voucher_draft"]["lines"]) >= 2)

            pay_req = create_payroll_payment_request(int(slip["id"]), "cashier_a", "cashier")
            self.assertEqual(pay_req["status"], "pending")

            with self.engine.connect() as conn:
                row = conn.execute(text("SELECT COUNT(*) AS c FROM payroll_tax_ledger")).fetchone()
                self.assertEqual(int(row.c), 2)
                pay_row = conn.execute(text("SELECT COUNT(*) AS c FROM payment_requests")).fetchone()
                self.assertEqual(int(pay_row.c), 1)

            closed = set_payroll_period_status(int(p["id"]), "close", operator_id=1)
            self.assertEqual(closed["status"], "closed")

            reopened = set_payroll_period_status(int(p["id"]), "reopen")
            self.assertEqual(reopened["status"], "open")

    def test_attendance_interface_preserved(self):
        payload = {
            "period": "2026-03",
            "records": [
                {"employee_id": 101, "attendance_days": 22, "absent_days": 0, "attendance_ref": "A-101"},
                {"employee_id": 102, "attendance_days": 20, "absent_days": 2, "attendance_ref": "A-102"},
            ],
        }
        out = sync_attendance_interface(payload)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["items"][0]["employee_id"], 101)


if __name__ == "__main__":
    unittest.main()
