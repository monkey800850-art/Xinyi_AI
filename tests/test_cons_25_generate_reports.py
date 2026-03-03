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


class Cons25GenerateReportsTest(unittest.TestCase):
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
                "group_code": f"CONS25-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS25组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _insert_source_adjustment(self, gid: int):
        lines = [
            {"subject_code": "1001", "debit": "100.00", "credit": "20.00", "note": "cash", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "6001", "debit": "0", "credit": "50.00", "note": "revenue", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "5001", "debit": "30.00", "credit": "0", "note": "cost", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "6601", "debit": "10.00", "credit": "0", "note": "expense", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "2201", "debit": "0", "credit": "40.00", "note": "liability", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "3001", "debit": "0", "credit": "8.00", "note": "equity", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "1501", "debit": "15.00", "credit": "0", "note": "investing", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
            {"subject_code": "4001", "debit": "0", "credit": "5.00", "note": "financing", "set_id": "SRC-25", "source": "generated", "rule": "UP_INV", "evidence_ref": "SRC-25", "operator_id": "1"},
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
                        'generated', 'src', 'UP_INV', 'SRC-25', 'SRC-25', 'src-25'
                    )
                    """
                ),
                {"gid": gid, "lines_json": json.dumps(lines, ensure_ascii=False)},
            )

    def test_01_generate_reports(self):
        gid = self._create_group()
        self._insert_source_adjustment(gid)
        payload = {"consolidation_group_id": gid, "period": "2025-04", "operator_id": 1}

        first = self.client.post("/task/cons-25", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "报表模板与合并报表生成完成")
        self.assertEqual(int(body.get("template_count") or 0), 4)
        self.assertEqual(int(body.get("report_count") or 0), 4)
        self.assertTrue(str(body.get("batch_id") or "").startswith(f"RPT-{gid}-202504"))
        report_map = {str(r.get("report_code") or ""): r for r in (body.get("reports") or [])}
        self.assertIn("BALANCE_SHEET", report_map)
        self.assertIn("INCOME_STATEMENT", report_map)
        self.assertIn("CASH_FLOW", report_map)
        self.assertIn("EQUITY_CHANGE", report_map)

        bs_items = {str(i["item_code"]): float(i["amount"]) for i in report_map["BALANCE_SHEET"].get("items") or []}
        self.assertAlmostEqual(bs_items.get("asset_total", 0), 95.0, places=2)
        self.assertAlmostEqual(bs_items.get("liability_total", 0), 40.0, places=2)
        self.assertAlmostEqual(bs_items.get("equity_total", 0), 8.0, places=2)

        is_items = {str(i["item_code"]): float(i["amount"]) for i in report_map["INCOME_STATEMENT"].get("items") or []}
        self.assertAlmostEqual(is_items.get("net_profit", 0), 10.0, places=2)

        second = self.client.post("/task/cons-25", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        self.assertEqual(str(second_body.get("batch_id") or ""), str(body.get("batch_id") or ""))

        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT report_code, template_code, source, rule_code, batch_id, status, template_json, report_json
                    FROM consolidation_report_snapshots
                    WHERE group_id=:gid AND period='2025-04'
                    ORDER BY report_code ASC
                    """
                ),
                {"gid": gid},
            ).fetchall()
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertEqual(str(row.source or ""), "generated")
            self.assertEqual(str(row.rule_code or ""), "CONS_REPORTS_GEN")
            self.assertEqual(str(row.status or ""), "draft")
            self.assertTrue(str(row.batch_id or "").startswith(f"RPT-{gid}-202504"))
            template = json.loads(str(row.template_json or "{}"))
            report = json.loads(str(row.report_json or "{}"))
            self.assertEqual(str(template.get("report_code") or ""), str(row.report_code or ""))
            self.assertEqual(str(report.get("report_code") or ""), str(row.report_code or ""))


if __name__ == "__main__":
    unittest.main()
