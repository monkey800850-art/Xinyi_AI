import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

from app.services.consolidation_service import create_audit_index, generate_disclosure_notes, trace_consolidation_batch


class _Provider:
    def __init__(self, engine):
        self._engine = engine

    def begin(self):
        return self._engine.begin()

    def connect(self):
        return self._engine.connect()


class P1Cons01EnhanceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, path = tempfile.mkstemp(prefix="cons01_", suffix=".db")
        os.close(fd)
        cls.db_path = Path(path)
        cls.engine = create_engine(f"sqlite:///{cls.db_path}", future=True)
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_adjustments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        batch_id TEXT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
                        lines_json TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_report_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        report_code TEXT NOT NULL,
                        report_json TEXT NOT NULL,
                        batch_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_approval_flows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        batch_id TEXT NOT NULL,
                        check_result TEXT NOT NULL DEFAULT 'failed',
                        approval_status TEXT NOT NULL DEFAULT 'submitted',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_audit_packages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        period TEXT NOT NULL,
                        batch_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'draft',
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
            conn.execute(text("DELETE FROM consolidation_audit_packages"))
            conn.execute(text("DELETE FROM consolidation_approval_flows"))
            conn.execute(text("DELETE FROM consolidation_report_snapshots"))
            conn.execute(text("DELETE FROM consolidation_adjustments"))
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments (group_id, period, batch_id, status, lines_json)
                    VALUES (1, '2026-03', 'ADJ-202603', 'draft', :lines_json)
                    """
                ),
                {
                    "lines_json": json.dumps(
                        [
                            {"subject_code": "1001", "debit": "100", "credit": "0"},
                            {"subject_code": "2201", "debit": "0", "credit": "100"},
                        ],
                        ensure_ascii=False,
                    )
                },
            )
            report_codes = ["BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW", "EQUITY_CHANGE"]
            for code in report_codes:
                conn.execute(
                    text(
                        """
                        INSERT INTO consolidation_report_snapshots (group_id, period, report_code, report_json, batch_id, status)
                        VALUES (1, '2026-03', :code, :report_json, 'RPT-202603', 'draft')
                        """
                    ),
                    {
                        "code": code,
                        "report_json": json.dumps(
                            {
                                "items": [
                                    {"item_code": f"{code}_1", "label": "L1", "amount": 10},
                                    {"item_code": f"{code}_2", "label": "L2", "amount": 20},
                                ]
                            },
                            ensure_ascii=False,
                        ),
                    },
                )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_approval_flows (group_id, period, batch_id, check_result, approval_status)
                    VALUES (1, '2026-03', 'FINAL-202603', 'passed', 'approved')
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_audit_packages (group_id, period, batch_id, status)
                    VALUES (1, '2026-03', 'AUDPKG-202603', 'draft')
                    """
                )
            )

    def test_generate_notes_index_and_trace(self):
        provider = _Provider(self.engine)
        with patch("app.services.consolidation_service.get_connection_provider", return_value=provider):
            notes = generate_disclosure_notes({"consolidation_group_id": 1, "period": "2026-03"}, operator_id=1)
            self.assertEqual(notes["failed_count"], 0)
            self.assertEqual(notes["check_count"], 3)

            idx = create_audit_index({"consolidation_group_id": 1, "period": "2026-03"}, operator_id=1)
            self.assertEqual(int(idx["report_count"]), 4)
            self.assertEqual(int(idx["indexed_count"]), 8)

            trace = trace_consolidation_batch({"consolidation_group_id": 1, "period": "2026-03"})
            self.assertGreaterEqual(int(trace["trace_count"]), 1)
            stages = {x["stage"] for x in trace["items"]}
            self.assertIn("adjustment", stages)
            self.assertIn("report_snapshot", stages)
            self.assertIn("approval_flow", stages)
            self.assertIn("audit_package", stages)
            self.assertIn("disclosure_check", stages)
            self.assertIn("audit_index", stages)


if __name__ == "__main__":
    unittest.main()
