import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.payroll_service import (
    confirm_payroll_slip,
    create_payroll_disbursement_batch,
    export_payroll_bank_file,
    list_payroll_slips,
    upsert_payroll_period,
    upsert_payroll_region_policy,
    upsert_payroll_slip,
)


class PayrollEnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="payroll_enh_", suffix=".db")
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
                        city TEXT NULL,
                        bank_account TEXT NULL,
                        attendance_ref TEXT NULL,
                        attendance_days INTEGER NOT NULL DEFAULT 0,
                        absent_days INTEGER NOT NULL DEFAULT 0,
                        gross_amount NUMERIC NOT NULL DEFAULT 0,
                        deduction_amount NUMERIC NOT NULL DEFAULT 0,
                        social_insurance NUMERIC NOT NULL DEFAULT 0,
                        housing_fund NUMERIC NOT NULL DEFAULT 0,
                        bonus_amount NUMERIC NOT NULL DEFAULT 0,
                        overtime_amount NUMERIC NOT NULL DEFAULT 0,
                        tax_method TEXT NOT NULL DEFAULT 'cumulative',
                        ytd_taxable_base NUMERIC NOT NULL DEFAULT 0,
                        ytd_tax_withheld NUMERIC NOT NULL DEFAULT 0,
                        taxable_base NUMERIC NOT NULL DEFAULT 0,
                        tax_amount NUMERIC NOT NULL DEFAULT 0,
                        net_amount NUMERIC NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'draft',
                        payment_status TEXT NOT NULL DEFAULT 'unpaid',
                        payment_request_id INTEGER NULL,
                        paid_at DATETIME NULL,
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
                    CREATE TABLE IF NOT EXISTS payroll_region_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        city TEXT NOT NULL,
                        social_rate NUMERIC NOT NULL DEFAULT 0,
                        housing_rate NUMERIC NOT NULL DEFAULT 0,
                        social_base_min NUMERIC NOT NULL DEFAULT 0,
                        social_base_max NUMERIC NOT NULL DEFAULT 0,
                        housing_base_min NUMERIC NOT NULL DEFAULT 0,
                        housing_base_max NUMERIC NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_disbursement_batches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        batch_no TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
                        total_count INTEGER NOT NULL DEFAULT 0,
                        total_amount NUMERIC NOT NULL DEFAULT 0,
                        file_name TEXT NULL,
                        created_by TEXT NULL,
                        created_at DATETIME NULL,
                        updated_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_disbursement_batch_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        batch_id INTEGER NOT NULL,
                        slip_id INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL,
                        employee_name TEXT NULL,
                        bank_account TEXT NOT NULL,
                        pay_amount NUMERIC NOT NULL,
                        created_at DATETIME NULL
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
            conn.execute(text("DELETE FROM payroll_disbursement_batch_items"))
            conn.execute(text("DELETE FROM payroll_disbursement_batches"))
            conn.execute(text("DELETE FROM payroll_region_policies"))
            conn.execute(text("DELETE FROM payroll_tax_ledger"))
            conn.execute(text("DELETE FROM payroll_slips"))
            conn.execute(text("DELETE FROM payroll_periods"))

    def test_cumulative_tax_region_policy_masking_and_batch_export(self):
        with patch("app.services.payroll_service.get_engine", return_value=self.engine):
            upsert_payroll_region_policy(
                {
                    "book_id": 1,
                    "city": "SH",
                    "social_rate": "0.10",
                    "housing_rate": "0.07",
                    "social_base_min": "5000",
                    "social_base_max": "30000",
                    "housing_base_min": "5000",
                    "housing_base_max": "30000",
                    "status": "active",
                }
            )

            upsert_payroll_period({"book_id": 1, "period": "2026-01", "status": "open"})
            s1 = upsert_payroll_slip(
                {
                    "book_id": 1,
                    "period": "2026-01",
                    "employee_id": 101,
                    "employee_name": "Alice",
                    "department": "FIN",
                    "city": "SH",
                    "bank_account": "6222020000001234",
                    "gross_amount": "35000",
                    "deduction_amount": "0",
                    "bonus_amount": "0",
                    "overtime_amount": "0",
                }
            )
            confirm_payroll_slip(int(s1["id"]), "admin_user", "admin")
            self.assertAlmostEqual(float(s1["tax_amount"]), 747.00, places=2)

            upsert_payroll_period({"book_id": 1, "period": "2026-02", "status": "open"})
            s2 = upsert_payroll_slip(
                {
                    "book_id": 1,
                    "period": "2026-02",
                    "employee_id": 101,
                    "employee_name": "Alice",
                    "department": "FIN",
                    "city": "SH",
                    "bank_account": "6222020000001234",
                    "gross_amount": "35000",
                    "deduction_amount": "0",
                    "bonus_amount": "0",
                    "overtime_amount": "0",
                    "tax_method": "cumulative",
                }
            )
            self.assertAlmostEqual(float(s2["tax_amount"]), 1713.00, places=2)
            self.assertAlmostEqual(float(s2["ytd_taxable_base"]), 49800.00, places=2)
            confirm_payroll_slip(int(s2["id"]), "admin_user", "admin")

            masked = list_payroll_slips(
                {"book_id": "1", "period": "2026-02", "viewer_role": "employee", "viewer_employee_id": "101"}
            )
            self.assertEqual(len(masked["items"]), 1)
            self.assertNotIn("tax_amount", masked["items"][0])
            self.assertTrue("*" in masked["items"][0]["employee_name"])
            self.assertTrue(masked["items"][0]["bank_account"].endswith("1234"))

            batch = create_payroll_disbursement_batch({"book_id": 1, "period": "2026-02"}, "cashier_a", "cashier")
            self.assertEqual(int(batch["total_count"]), 1)

            exported = export_payroll_bank_file(int(batch["batch_id"]), "cashier_a", "cashier")
            self.assertTrue(str(exported["file_name"]).endswith(".csv"))
            content = exported["content"].decode("utf-8-sig")
            self.assertIn("employee_id,employee_name,bank_account,amount,remark", content)
            self.assertIn("6222020000001234", content)


if __name__ == "__main__":
    unittest.main()
