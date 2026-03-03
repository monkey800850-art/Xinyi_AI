import json
import os
import runpy
import sys
import time
import unittest
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import get_engine


class Cons23MultiPeriodRolloverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"

        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        ns = runpy.run_path(str(repo_root / "app.py"))
        cls.app = ns["create_app"]()
        cls.client = cls.app.test_client()
        cls.engine = get_engine()
        cls.sid = str(int(time.time()))[-6:]
        cls._ensure_tables()

    @classmethod
    def _ensure_tables(cls):
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_groups (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_code VARCHAR(64) NOT NULL UNIQUE,
                        group_name VARCHAR(128) NOT NULL,
                        group_type VARCHAR(32) NOT NULL DEFAULT 'standard',
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        note VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_adjustments (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        period VARCHAR(7) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL,
                        lines_json JSON NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

            def _has_column(name: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name='consolidation_adjustments'
                          AND column_name=:name
                        """
                    ),
                    {"name": name},
                ).fetchone()
                return int(row.cnt or 0) > 0

            optional_columns = [
                ("source", "ALTER TABLE consolidation_adjustments ADD COLUMN source VARCHAR(32) NULL"),
                ("rule_code", "ALTER TABLE consolidation_adjustments ADD COLUMN rule_code VARCHAR(64) NULL"),
                ("evidence_ref", "ALTER TABLE consolidation_adjustments ADD COLUMN evidence_ref VARCHAR(255) NULL"),
                ("batch_id", "ALTER TABLE consolidation_adjustments ADD COLUMN batch_id VARCHAR(64) NULL"),
                ("tag", "ALTER TABLE consolidation_adjustments ADD COLUMN tag VARCHAR(64) NULL"),
                ("reviewed_by", "ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_by BIGINT NULL"),
                ("reviewed_at", "ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_at DATETIME NULL"),
                ("locked_by", "ALTER TABLE consolidation_adjustments ADD COLUMN locked_by BIGINT NULL"),
                ("locked_at", "ALTER TABLE consolidation_adjustments ADD COLUMN locked_at DATETIME NULL"),
                ("note", "ALTER TABLE consolidation_adjustments ADD COLUMN note VARCHAR(255) NULL"),
                ("period_start", "ALTER TABLE consolidation_adjustments ADD COLUMN period_start DATE NULL"),
                ("period_end", "ALTER TABLE consolidation_adjustments ADD COLUMN period_end DATE NULL"),
                ("origin_period_start", "ALTER TABLE consolidation_adjustments ADD COLUMN origin_period_start DATE NULL"),
                ("origin_period_end", "ALTER TABLE consolidation_adjustments ADD COLUMN origin_period_end DATE NULL"),
                ("original_unrealized_profit", "ALTER TABLE consolidation_adjustments ADD COLUMN original_unrealized_profit DECIMAL(18,2) NULL"),
                ("remaining_unrealized_profit", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_unrealized_profit DECIMAL(18,2) NULL"),
                ("original_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN original_amount DECIMAL(18,2) NULL"),
                ("remaining_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_amount DECIMAL(18,2) NULL"),
                ("original_tax_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN original_tax_amount DECIMAL(18,2) NULL"),
                ("remaining_tax_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_tax_amount DECIMAL(18,2) NULL"),
                ("tax_rate_snapshot", "ALTER TABLE consolidation_adjustments ADD COLUMN tax_rate_snapshot DECIMAL(9,6) NULL"),
            ]
            for name, ddl in optional_columns:
                if not _has_column(name):
                    conn.execute(text(ddl))

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={
                "group_code": f"CONS23-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS23组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _insert_source_adjustment(self, group_id: int):
        lines = [
            {
                "subject_code": "UP_INV_ELIM",
                "debit": "8.00",
                "credit": "0",
                "note": "source line debit",
                "set_id": "UPINV-SRC",
                "source": "generated",
                "rule": "UP_INV",
                "evidence_ref": "UPINV-SRC",
                "operator_id": "1",
            },
            {
                "subject_code": "UP_INV_ELIM",
                "debit": "0",
                "credit": "8.00",
                "note": "source line credit",
                "set_id": "UPINV-SRC",
                "source": "generated",
                "rule": "UP_INV",
                "evidence_ref": "UPINV-SRC",
                "operator_id": "1",
            },
        ]
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments (
                        group_id, period, status, operator_id, lines_json,
                        source, tag, rule_code, evidence_ref, batch_id, note,
                        period_start, period_end, origin_period_start, origin_period_end,
                        original_unrealized_profit, remaining_unrealized_profit,
                        original_amount, remaining_amount,
                        original_tax_amount, remaining_tax_amount, tax_rate_snapshot
                    ) VALUES (
                        :gid, '2025-03', 'draft', 1, :lines_json,
                        'generated', 'unrealized_profit_inventory', 'UP_INV', 'UPINV-SRC', 'UPINV-SRC', 'src',
                        '2025-03-01', '2025-03-31', '2025-03-01', '2025-03-31',
                        8.00, 5.00, 8.00, 5.00, 2.00, 1.20, 0.250000
                    )
                    """
                ),
                {"gid": int(group_id), "lines_json": json.dumps(lines, ensure_ascii=False)},
            )

    def test_01_multi_period_rollover(self):
        gid = self._create_group()
        self._insert_source_adjustment(gid)
        payload = {
            "consolidation_group_id": gid,
            "from_period": "2025-03",
            "to_period": "2025-04",
            "operator_id": 1,
        }

        first = self.client.post("/task/cons-23", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "多期滚动支持完成")
        self.assertEqual(str(body.get("from_period") or ""), "2025-03")
        self.assertEqual(str(body.get("to_period") or ""), "2025-04")
        self.assertGreaterEqual(int(body.get("source_set_count") or 0), 1)
        items = body.get("items") or []
        self.assertTrue(len(items) >= 1)
        set_id = str(items[0].get("set_id") or "")
        self.assertTrue(set_id)

        second = self.client.post("/task/cons-23", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        second_items = second_body.get("items") or []
        self.assertEqual(str(second_items[0].get("set_id") or ""), set_id)
        self.assertTrue(bool(second_items[0].get("reused_existing_set")))

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT source, rule_code, evidence_ref, batch_id, status, period,
                           note, period_start, period_end, origin_period_start, origin_period_end,
                           original_unrealized_profit, remaining_unrealized_profit,
                           original_amount, remaining_amount,
                           original_tax_amount, remaining_tax_amount,
                           lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid
                      AND period='2025-04'
                      AND batch_id=:batch_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid, "batch_id": set_id},
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row.source or ""), "generated")
        self.assertEqual(str(row.rule_code or ""), "ROLL_CARRY_FORWARD")
        self.assertEqual(str(row.evidence_ref or ""), set_id)
        self.assertEqual(str(row.batch_id or ""), set_id)
        self.assertEqual(str(row.status or ""), "draft")
        self.assertEqual(str(row.period or ""), "2025-04")
        self.assertTrue("carry_from=2025-03" in str(row.note or ""))
        self.assertEqual(str(row.period_start or ""), "2025-04-01")
        self.assertEqual(str(row.period_end or ""), "2025-04-30")
        self.assertEqual(str(row.origin_period_start or ""), "2025-03-01")
        self.assertEqual(str(row.origin_period_end or ""), "2025-03-31")
        self.assertEqual(str(row.original_unrealized_profit or ""), "5.00")
        self.assertEqual(str(row.remaining_unrealized_profit or ""), "5.00")
        self.assertEqual(str(row.original_amount or ""), "5.00")
        self.assertEqual(str(row.remaining_amount or ""), "5.00")
        self.assertEqual(str(row.original_tax_amount or ""), "1.20")
        self.assertEqual(str(row.remaining_tax_amount or ""), "1.20")
        lines = json.loads(str(row.lines_json or "[]"))
        self.assertEqual(len(lines), 2)
        self.assertTrue(str(lines[0].get("note") or "").startswith("期初滚动"))


if __name__ == "__main__":
    unittest.main()
