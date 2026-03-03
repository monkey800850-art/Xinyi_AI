import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.tax_service import (
    build_tax_declaration_mapping,
    create_tax_diff_entry,
    list_tax_declaration_mappings,
    list_tax_diff_entries,
    map_tax_declaration,
    validate_invoice,
    verify_invoice,
)


class TaxEnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="tax_enh_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tax_invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        invoice_code TEXT NULL,
                        invoice_no TEXT NOT NULL,
                        invoice_date DATE NOT NULL,
                        amount NUMERIC NOT NULL,
                        tax_rate NUMERIC NULL,
                        tax_amount NUMERIC NULL,
                        seller_name TEXT NULL,
                        buyer_name TEXT NULL,
                        verification_status TEXT NOT NULL DEFAULT 'pending',
                        verification_message TEXT NULL,
                        verified_at DATETIME NULL
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
                        period TEXT NOT NULL,
                        tax_subject TEXT NOT NULL,
                        tax_amount NUMERIC NOT NULL,
                        accounting_amount NUMERIC NOT NULL,
                        diff_amount NUMERIC NOT NULL,
                        reason_code TEXT NULL,
                        remark TEXT NULL,
                        created_at DATETIME NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tax_declaration_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        declaration_code TEXT NOT NULL,
                        worksheet_cell TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source_key TEXT NOT NULL,
                        expression TEXT NULL,
                        is_enabled INTEGER NOT NULL DEFAULT 1,
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
            conn.execute(text("DELETE FROM tax_declaration_mappings"))
            conn.execute(text("DELETE FROM tax_difference_ledger"))
            conn.execute(text("DELETE FROM tax_invoices"))

    def test_invoice_verify_diff_ledger_and_mapping(self):
        with patch("app.services.tax_service.get_engine", return_value=self.engine):
            ok = validate_invoice(
                {
                    "invoice_code": "3100",
                    "invoice_no": "12345678",
                    "invoice_date": "2026-03-03",
                    "amount": "1000",
                    "tax_rate": "0.06",
                    "tax_amount": "60",
                    "seller_name": "A",
                    "buyer_name": "B",
                }
            )
            self.assertTrue(ok["valid"])

            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO tax_invoices (
                            id, book_id, invoice_code, invoice_no, invoice_date, amount, tax_rate, tax_amount, seller_name, buyer_name
                        ) VALUES (
                            1, 1, '3100', '12345678', '2026-03-03', 1000, 0.06, 60, 'A', 'B'
                        )
                        """
                    )
                )
            v = verify_invoice({"invoice_id": 1})
            self.assertTrue(v["valid"])

            d = create_tax_diff_entry(
                {
                    "book_id": 1,
                    "period": "2026-03",
                    "tax_subject": "VAT_INPUT",
                    "tax_amount": "100.00",
                    "accounting_amount": "95.00",
                    "reason_code": "TIMING",
                }
            )
            self.assertEqual(float(d["diff_amount"]), 5.0)
            lst = list_tax_diff_entries({"book_id": "1", "period": "2026-03"})
            self.assertEqual(len(lst["items"]), 1)

            saved = map_tax_declaration(
                {
                    "book_id": 1,
                    "declaration_code": "VAT_MAIN",
                    "mappings": [
                        {"worksheet_cell": "A1", "source_type": "ledger", "source_key": "vat_input"},
                        {"worksheet_cell": "A2", "source_type": "ledger", "source_key": "vat_output"},
                    ],
                }
            )
            self.assertEqual(int(saved["count"]), 2)
            mapping = list_tax_declaration_mappings({"book_id": "1", "declaration_code": "VAT_MAIN"})
            self.assertEqual(len(mapping["items"]), 2)
            built = build_tax_declaration_mapping(
                {
                    "book_id": 1,
                    "declaration_code": "VAT_MAIN",
                    "source_values": {"vat_input": 100.5, "vat_output": 200},
                }
            )
            self.assertEqual(len(built["cells"]), 2)
            self.assertTrue(any(c["worksheet_cell"] == "A1" and float(c["value"]) == 100.5 for c in built["cells"]))


if __name__ == "__main__":
    unittest.main()
