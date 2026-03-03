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


class Cons22NciDynamicCalculationTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_group_members (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        member_book_id BIGINT NULL,
                        member_type VARCHAR(16) NOT NULL DEFAULT 'BOOK',
                        effective_from DATE NULL,
                        effective_to DATE NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_parameters (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        parent_subject_type VARCHAR(64) NOT NULL DEFAULT '',
                        parent_subject_id BIGINT NOT NULL DEFAULT 0,
                        child_subject_type VARCHAR(64) NOT NULL DEFAULT '',
                        child_subject_id BIGINT NOT NULL DEFAULT 0,
                        ownership_ratio DECIMAL(9,6) NOT NULL DEFAULT 1.000000,
                        control_type VARCHAR(32) NOT NULL DEFAULT '',
                        include_in_consolidation TINYINT NOT NULL DEFAULT 1,
                        effective_start DATE NOT NULL DEFAULT '2000-01-01',
                        effective_end DATE NOT NULL DEFAULT '2099-12-31',
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        consolidation_method VARCHAR(16) NOT NULL DEFAULT 'full',
                        default_scope VARCHAR(16) NOT NULL DEFAULT 'raw',
                        effective_from DATE NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_ownership (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        parent_entity_id BIGINT NOT NULL,
                        child_entity_id BIGINT NOT NULL,
                        ownership_pct DECIMAL(9,6) NOT NULL,
                        effective_from DATE NOT NULL,
                        effective_to DATE NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        operator_id BIGINT NOT NULL DEFAULT 0
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
                "group_code": f"CONS22-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS22组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _insert_member(self, group_id: int):
        with self.engine.begin() as conn:
            cols = {
                str(r[0] or "").strip().lower()
                for r in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = 'consolidation_group_members'
                        """
                    )
                ).fetchall()
            }
            insert_cols = ["group_id"]
            insert_vals = [":gid"]
            params = {"gid": int(group_id), "book_id": 1}
            if "member_book_id" in cols:
                insert_cols.append("member_book_id")
                insert_vals.append(":book_id")
            if "book_id" in cols:
                insert_cols.append("book_id")
                insert_vals.append(":book_id")
            if "member_type" in cols:
                insert_cols.append("member_type")
                insert_vals.append("'BOOK'")
            if "effective_from" in cols:
                insert_cols.append("effective_from")
                insert_vals.append("'2025-01-01'")
            if "effective_to" in cols:
                insert_cols.append("effective_to")
                insert_vals.append("'2099-12-31'")
            if "status" in cols:
                insert_cols.append("status")
                insert_vals.append("'active'")
            if "is_enabled" in cols:
                insert_cols.append("is_enabled")
                insert_vals.append("1")
            conn.execute(
                text(
                    f"""
                    INSERT INTO consolidation_group_members ({', '.join(insert_cols)})
                    VALUES ({', '.join(insert_vals)})
                    """
                ),
                params,
            )

    def _insert_method_full(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"), {"gid": int(group_id)})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                        virtual_subject_id, parent_subject_type, parent_subject_id, child_subject_type, child_subject_id,
                        ownership_ratio, control_type, include_in_consolidation,
                        effective_start, effective_end, status, operator_id, consolidation_method, default_scope, effective_from
                    ) VALUES (
                        :gid, '', :gid, '', :gid,
                        1.000000, '2025-01', 1,
                        '2025-01-01', '2099-12-31', 'active', 1, 'full', 'raw', '2025-01-01'
                    )
                    """
                ),
                {"gid": int(group_id)},
            )

    def _insert_ownership(self, group_id: int, child_id: int, pct: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_ownership (
                        group_id, parent_entity_id, child_entity_id, ownership_pct,
                        effective_from, effective_to, status, is_enabled, operator_id
                    ) VALUES (
                        :gid, 1001, :child_id, :pct, '2025-01-01', '2099-12-31', 'active', 1, 1
                    )
                    """
                ),
                {"gid": int(group_id), "child_id": int(child_id), "pct": pct},
            )

    def test_01_nci_dynamic_generation(self):
        gid = self._create_group()
        self._insert_member(gid)
        self._insert_method_full(gid)
        self._insert_ownership(gid, 2201, "0.6")

        payload = {
            "consolidation_group_id": gid,
            "as_of": "2025-03-31",
            "entity_net_assets": {"2201": 200},
            "entity_net_profit": {"2201": 50},
            "opening_nci_balance": {"2201": 30},
            "operator_id": 1,
        }
        first = self.client.post("/task/cons-22", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        body = first.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertEqual(str(body.get("message") or ""), "NCI动态计算完成")
        self.assertGreaterEqual(int(body.get("line_count") or 0), 2)
        items = body.get("items") or []
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(float(items[0].get("nci_share_of_net_assets") or 0), 80.0, places=2)
        self.assertAlmostEqual(float(items[0].get("nci_share_of_profit") or 0), 20.0, places=2)
        self.assertAlmostEqual(float(items[0].get("closing_nci_balance") or 0), 50.0, places=2)
        set_id = str(body.get("set_id") or "")
        self.assertTrue(set_id)

        second = self.client.post("/task/cons-22", json=payload)
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
        self.assertEqual(str(row.rule_code or ""), "NCI_DYNAMIC")
        self.assertEqual(str(row.evidence_ref or ""), set_id)
        self.assertEqual(str(row.batch_id or ""), set_id)
        self.assertEqual(str(row.status or ""), "draft")
        lines = json.loads(str(row.lines_json or "[]"))
        subjects = {str(item.get("subject_code") or "") for item in lines}
        self.assertIn("NCI_PNL_ALLOC", subjects)
        self.assertIn("NCI_EQUITY", subjects)


if __name__ == "__main__":
    unittest.main()
