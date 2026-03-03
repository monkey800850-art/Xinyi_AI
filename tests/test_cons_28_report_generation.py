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


class Cons28ReportGenerationAutomationTest(unittest.TestCase):
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
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_report_snapshots (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        period VARCHAR(7) NOT NULL,
                        report_code VARCHAR(64) NOT NULL,
                        template_code VARCHAR(64) NOT NULL,
                        source VARCHAR(32) NOT NULL DEFAULT 'generated',
                        rule_code VARCHAR(64) NOT NULL DEFAULT 'CONS_REPORTS_GEN',
                        batch_id VARCHAR(64) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'draft',
                        template_json JSON NOT NULL,
                        report_json JSON NOT NULL,
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_conso_report_snapshot (group_id, period, report_code)
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
                "group_code": f"CONS28-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS28组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _insert_source_adjustment(self, gid: int):
        lines = [
            {"subject_code": "1001", "debit": "100.00", "credit": "20.00", "note": "cash", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
            {"subject_code": "6001", "debit": "0", "credit": "50.00", "note": "revenue", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
            {"subject_code": "5001", "debit": "30.00", "credit": "0", "note": "cost", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
            {"subject_code": "6601", "debit": "10.00", "credit": "0", "note": "expense", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
            {"subject_code": "2201", "debit": "0", "credit": "40.00", "note": "liability", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
            {"subject_code": "3001", "debit": "0", "credit": "8.00", "note": "equity", "set_id": "SRC-28", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-28", "operator_id": "1"},
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
                        'generated', 'src', 'UP_INV', 'SRC-28', 'SRC-28', 'src-28'
                    )
                    """
                ),
                {"gid": gid, "lines_json": json.dumps(lines, ensure_ascii=False)},
            )

    def test_01_automate_report_generation_and_adjustment(self):
        gid = self._create_group()
        self._insert_source_adjustment(gid)
        payload = {"consolidation_group_id": gid, "period": "2025-04", "operator_id": 1}

        first = self.client.post("/task/cons-28", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "合并报表自动化生成与调节完成")
        self.assertEqual(str(body.get("rule_code") or ""), "CONS28_AUTO_ADJ")
        self.assertEqual(int(body.get("template_count") or 0), 4)
        self.assertEqual(int(body.get("report_count") or 0), 4)
        self.assertTrue(bool(body.get("adjustment_generated")))
        self.assertTrue(str(body.get("adjustment_set_id") or "").startswith(f"AUTOADJ-{gid}-202504"))
        self.assertAlmostEqual(float(body.get("delta_before_adjustment") or 0), 32.0, places=2)
        self.assertAlmostEqual(float(body.get("delta_after_adjustment") or 0), 0.0, places=2)

        second = self.client.post("/task/cons-28", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        self.assertAlmostEqual(float(second_body.get("delta_after_adjustment") or 0), 0.0, places=2)
        self.assertFalse(bool(second_body.get("adjustment_generated")))
        self.assertEqual(str(second_body.get("adjustment_set_id") or ""), "")

        with self.engine.connect() as conn:
            adj = conn.execute(
                text(
                    """
                    SELECT source, rule_code, batch_id, status, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND rule_code='CONS28_AUTO_ADJ'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
            rows = conn.execute(
                text(
                    """
                    SELECT report_code, template_code, rule_code, status, report_json
                    FROM consolidation_report_snapshots
                    WHERE group_id=:gid AND period='2025-04'
                    ORDER BY report_code ASC
                    """
                ),
                {"gid": gid},
            ).fetchall()
        self.assertIsNotNone(adj)
        self.assertEqual(str(adj.source or ""), "generated")
        self.assertEqual(str(adj.rule_code or ""), "CONS28_AUTO_ADJ")
        self.assertEqual(str(adj.status or ""), "draft")
        lines = json.loads(str(adj.lines_json or "[]"))
        subjects = {str(item.get("subject_code") or "") for item in lines}
        self.assertIn("3001", subjects)
        self.assertIn("6601", subjects)

        self.assertEqual(len(rows), 4)
        bs = None
        for r in rows:
            if str(r.report_code or "") == "BALANCE_SHEET":
                bs = json.loads(str(r.report_json or "{}"))
        self.assertIsNotNone(bs)
        kv = {str(i.get("item_code") or ""): float(i.get("amount") or 0) for i in (bs.get("items") or [])}
        self.assertAlmostEqual(kv.get("asset_total", 0), kv.get("liability_equity_total", 0), places=2)


if __name__ == "__main__":
    unittest.main()
