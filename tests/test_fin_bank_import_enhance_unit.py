import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.bank_import_service import import_bank_transactions


class BankImportEnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="bank_import_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS bank_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        book_id INTEGER NOT NULL,
                        bank_account_id INTEGER NOT NULL,
                        txn_date DATE NOT NULL,
                        amount NUMERIC NOT NULL,
                        summary TEXT NULL,
                        counterparty TEXT NULL,
                        balance NUMERIC NULL,
                        serial_no TEXT NULL,
                        currency TEXT NOT NULL DEFAULT 'CNY',
                        source_file TEXT NULL,
                        import_hash TEXT NOT NULL UNIQUE,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
            conn.execute(text("DELETE FROM bank_transactions"))

    def test_template_mapping_dedup_and_exception_receipt(self):
        csv_bytes = (
            "交易时间,发生额,说明,对手方,余额,流水号\n"
            "2026-03-01,100.00,来款A,客户A,1000.00,SN001\n"
            "2026-03-01,100.00,来款A,客户A,1000.00,SN001\n"
            "BAD_DATE,50.00,来款B,客户B,1050.00,SN002\n"
        ).encode("utf-8")
        mapping = {
            "date": "交易时间",
            "amount": "发生额",
            "summary": "说明",
            "counterparty": "对手方",
            "balance": "余额",
            "serial_no": "流水号",
        }
        with patch("app.services.bank_import_service.get_engine", return_value=self.engine):
            result = import_bank_transactions(1, 100, "bank.csv", csv_bytes, template_mapping=mapping)
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["success"], 1)
            self.assertEqual(result["duplicated"], 1)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["exception_receipt"]["status"], "partial_failed")
            self.assertEqual(result["exception_receipt"]["error_count"], 1)
            self.assertEqual(result["exception_receipt"]["errors"][0]["error_code"], "invalid_date")
            self.assertEqual(result["template_mapping_used"]["date"], "交易时间")

            result2 = import_bank_transactions(1, 100, "bank.csv", csv_bytes, template_mapping=mapping)
            self.assertEqual(result2["success"], 0)
            self.assertGreaterEqual(result2["duplicated"], 2)


if __name__ == "__main__":
    unittest.main()
