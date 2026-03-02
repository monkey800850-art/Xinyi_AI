import json
import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Cons21EquityMethodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"
        from pathlib import Path

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
            ]
            for name, ddl in optional_columns:
                if not _has_column(name):
                    conn.execute(text(ddl))

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={
                "group_code": f"CONS21-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS21组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def test_01_equity_method_task_generate(self):
        gid = self._create_group()
        payload = {
            "consolidation_group_id": gid,
            "as_of": "2025-03-31",
            "associate_entity_id": 9001,
            "opening_carrying_amount": "100.00",
            "ownership_pct": "0.30",
            "net_income": "50.00",
            "other_comprehensive_income": "20.00",
            "dividends": "10.00",
            "impairment": "3.00",
            "operator_id": 1,
        }

        first = self.client.post("/task/cons-21", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "权益法核算完成")
        set_id = str(body.get("set_id") or "")
        self.assertTrue(set_id)
        self.assertGreaterEqual(int(body.get("line_count") or 0), 8)
        self.assertAlmostEqual(float(body.get("closing_carrying_amount") or 0), 115.0, places=2)

        second = self.client.post("/task/cons-21", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        self.assertEqual(str(second_body.get("set_id") or ""), set_id)
        self.assertTrue(bool(second_body.get("reused_existing_set")))

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT source, rule_code, evidence_ref, batch_id, status, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND batch_id=:batch_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid, "batch_id": set_id},
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row.source or ""), "generated")
        self.assertEqual(str(row.rule_code or ""), "EQUITY_METHOD")
        self.assertEqual(str(row.evidence_ref or ""), set_id)
        self.assertEqual(str(row.batch_id or ""), set_id)
        self.assertEqual(str(row.status or ""), "draft")
        lines = json.loads(str(row.lines_json or "[]"))
        subjects = {str(item.get("subject_code") or "") for item in lines}
        self.assertIn("EM_LTI", subjects)
        self.assertIn("EM_INVEST_INCOME", subjects)
        self.assertIn("EM_OCI", subjects)
        self.assertIn("EM_CASH", subjects)
        self.assertIn("EM_IMPAIRMENT_LOSS", subjects)


if __name__ == "__main__":
    unittest.main()
