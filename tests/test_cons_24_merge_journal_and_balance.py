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


class Cons24MergeJournalAndBalanceTest(unittest.TestCase):
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
            ]
            for name, ddl in optional_columns:
                if not _has_column(name):
                    conn.execute(text(ddl))

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={
                "group_code": f"CONS24-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS24组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _insert_source_adjustments(self, gid: int):
        lines_a = [
            {
                "subject_code": "1001",
                "debit": "10.00",
                "credit": "0",
                "note": "A-借",
                "set_id": "SRC-A",
                "source": "generated",
                "rule": "UP_INV",
                "evidence_ref": "SRC-A",
                "operator_id": "1",
            },
            {
                "subject_code": "6001",
                "debit": "0",
                "credit": "10.00",
                "note": "A-贷",
                "set_id": "SRC-A",
                "source": "generated",
                "rule": "UP_INV",
                "evidence_ref": "SRC-A",
                "operator_id": "1",
            },
        ]
        lines_b = [
            {
                "subject_code": "5001",
                "debit": "3.00",
                "credit": "0",
                "note": "B-借",
                "set_id": "SRC-B",
                "source": "generated",
                "rule": "IC_MATCH",
                "evidence_ref": "SRC-B",
                "operator_id": "1",
            },
            {
                "subject_code": "1001",
                "debit": "0",
                "credit": "3.00",
                "note": "B-贷",
                "set_id": "SRC-B",
                "source": "generated",
                "rule": "IC_MATCH",
                "evidence_ref": "SRC-B",
                "operator_id": "1",
            },
        ]
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments (
                        group_id, period, status, operator_id, lines_json,
                        source, tag, rule_code, evidence_ref, batch_id, note
                    ) VALUES (
                        :gid, '2025-04', 'draft', 1, :lines_json,
                        'generated', 'src', 'UP_INV', 'SRC-A', 'SRC-A', 'src-a'
                    )
                    """
                ),
                {"gid": gid, "lines_json": json.dumps(lines_a, ensure_ascii=False)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_adjustments (
                        group_id, period, status, operator_id, lines_json,
                        source, tag, rule_code, evidence_ref, batch_id, note
                    ) VALUES (
                        :gid, '2025-04', 'draft', 1, :lines_json,
                        'generated', 'src', 'IC_MATCH', 'SRC-B', 'SRC-B', 'src-b'
                    )
                    """
                ),
                {"gid": gid, "lines_json": json.dumps(lines_b, ensure_ascii=False)},
            )

    def test_01_merge_journal_and_post_balance(self):
        gid = self._create_group()
        self._insert_source_adjustments(gid)
        payload = {
            "consolidation_group_id": gid,
            "period": "2025-04",
            "operator_id": 1,
        }

        first = self.client.post("/task/cons-24", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "合并作业单与合并后余额层完成")
        self.assertEqual(str(body.get("rule_code") or ""), "MERGE_JOURNAL_POST_BALANCE")
        self.assertEqual(int(body.get("source_set_count") or 0), 2)
        self.assertEqual(int(body.get("merged_journal_line_count") or 0), 4)
        self.assertEqual(float(body.get("total_debit") or 0), 13.0)
        self.assertEqual(float(body.get("total_credit") or 0), 13.0)
        balances = {str(x.get("subject_code") or ""): x for x in (body.get("post_merge_balance") or [])}
        self.assertAlmostEqual(float(balances["1001"]["net_debit"]), 7.0, places=2)
        self.assertAlmostEqual(float(balances["6001"]["net_credit"]), 10.0, places=2)
        self.assertAlmostEqual(float(balances["5001"]["net_debit"]), 3.0, places=2)
        set_id = str(body.get("set_id") or "")
        self.assertTrue(set_id)

        second = self.client.post("/task/cons-24", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        self.assertEqual(str(second_body.get("set_id") or ""), set_id)
        self.assertTrue(bool(second_body.get("reused_existing_set")))

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT source, rule_code, evidence_ref, batch_id, status, period, lines_json
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
        self.assertEqual(str(row.rule_code or ""), "MERGE_JOURNAL_POST_BALANCE")
        self.assertEqual(str(row.evidence_ref or ""), set_id)
        self.assertEqual(str(row.batch_id or ""), set_id)
        self.assertEqual(str(row.status or ""), "draft")
        self.assertEqual(str(row.period or ""), "2025-04")
        lines = json.loads(str(row.lines_json or "[]"))
        subjects = {str(item.get("subject_code") or "") for item in lines}
        self.assertIn("1001", subjects)
        self.assertIn("5001", subjects)
        self.assertIn("6001", subjects)


if __name__ == "__main__":
    unittest.main()
