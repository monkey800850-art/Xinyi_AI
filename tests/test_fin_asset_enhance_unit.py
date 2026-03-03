import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.asset_service import (
    check_asset_impairment,
    dispose_asset,
    generate_journal_entry,
    perform_inventory_check,
    revalue_asset,
)


class AssetEnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="asset_enh_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS fixed_assets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        asset_code TEXT NOT NULL,
                        asset_name TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        original_value NUMERIC NOT NULL DEFAULT 0,
                        residual_value NUMERIC NOT NULL DEFAULT 0,
                        updated_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_impairments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        impairment_date DATE NOT NULL,
                        book_value NUMERIC NOT NULL,
                        current_value NUMERIC NOT NULL,
                        impairment_amount NUMERIC NOT NULL,
                        reason TEXT NULL,
                        evidence_ref TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_disposals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        disposal_date DATE NOT NULL,
                        disposal_method TEXT NOT NULL,
                        disposal_income NUMERIC NOT NULL,
                        disposal_cost NUMERIC NOT NULL,
                        book_value NUMERIC NOT NULL,
                        gain_loss NUMERIC NOT NULL,
                        note TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_inventory_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        check_date DATE NOT NULL,
                        note TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_inventory_check_lines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        check_id INTEGER NOT NULL,
                        asset_id INTEGER NOT NULL,
                        is_found INTEGER NOT NULL,
                        discrepancy_reason TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_revaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        revaluation_date DATE NOT NULL,
                        old_value NUMERIC NOT NULL,
                        new_value NUMERIC NOT NULL,
                        delta_amount NUMERIC NOT NULL,
                        reason TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS asset_journal_drafts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        rule_code TEXT NOT NULL,
                        reference_id INTEGER NULL,
                        debit_subject_code TEXT NOT NULL,
                        credit_subject_code TEXT NOT NULL,
                        amount NUMERIC NOT NULL,
                        note TEXT NULL,
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
            conn.execute(text("DELETE FROM asset_journal_drafts"))
            conn.execute(text("DELETE FROM asset_revaluations"))
            conn.execute(text("DELETE FROM asset_inventory_check_lines"))
            conn.execute(text("DELETE FROM asset_inventory_checks"))
            conn.execute(text("DELETE FROM asset_disposals"))
            conn.execute(text("DELETE FROM asset_impairments"))
            conn.execute(text("DELETE FROM fixed_assets"))
            conn.execute(
                text(
                    """
                    INSERT INTO fixed_assets (
                        id, book_id, asset_code, asset_name, status, original_value, residual_value, updated_at
                    ) VALUES (
                        1, 1, 'FA-001', 'Laptop', 'ACTIVE', 1000.00, 100.00, CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO fixed_assets (
                        id, book_id, asset_code, asset_name, status, original_value, residual_value, updated_at
                    ) VALUES (
                        2, 1, 'FA-002', 'Desk', 'ACTIVE', 500.00, 50.00, CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    def test_asset_enhancements_happy_path(self):
        with patch("app.services.asset_service.get_engine", return_value=self.engine):
            impairment = check_asset_impairment(
                1,
                {"current_value": "700.00", "impairment_date": "2026-03-03", "reason": "market_drop", "evidence_ref": "EV-1"},
            )
            self.assertAlmostEqual(float(impairment["impairment_amount"]), 200.0, places=2)

            disposal = dispose_asset(
                2,
                {
                    "disposal_method": "sell",
                    "disposal_date": "2026-03-03",
                    "disposal_income": "600.00",
                    "disposal_cost": "10.00",
                    "note": "sold out",
                },
            )
            self.assertEqual(disposal["status"], "DISPOSED")
            self.assertAlmostEqual(float(disposal["gain_loss"]), 140.0, places=2)

            inv = perform_inventory_check(
                {
                    "book_id": 1,
                    "check_date": "2026-03-03",
                    "asset_checks": [
                        {"asset_id": 1, "is_found": 1},
                        {"asset_id": 2, "is_found": 0, "discrepancy_reason": "not_found_on_site"},
                    ],
                }
            )
            self.assertEqual(inv["checked_count"], 2)
            self.assertEqual(inv["discrepancy_count"], 1)

            reval = revalue_asset(1, {"new_value": "1200.00", "revaluation_date": "2026-03-03", "reason": "fair_value_up"})
            self.assertAlmostEqual(float(reval["delta_amount"]), 200.0, places=2)

            journal = generate_journal_entry(
                1,
                "revaluation",
                {
                    "amount": "200.00",
                    "debit_subject_code": "1601",
                    "credit_subject_code": "4001",
                    "reference_id": int(reval["id"]),
                },
            )
            self.assertEqual(journal["rule_code"], "ASSET_REVALUATION")
            self.assertEqual(len(journal["lines"]), 2)

            with self.engine.connect() as conn:
                status = conn.execute(text("SELECT status FROM fixed_assets WHERE id=2")).fetchone()
                self.assertEqual(status[0], "DISPOSED")
                val = conn.execute(text("SELECT original_value FROM fixed_assets WHERE id=1")).fetchone()
                self.assertAlmostEqual(float(val[0]), 1200.0, places=2)


if __name__ == "__main__":
    unittest.main()
