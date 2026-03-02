import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch17ConsolidationTypeTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_authorizations (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        approval_document_number VARCHAR(255) NOT NULL,
                        approval_document_name VARCHAR(255) NOT NULL,
                        effective_start DATE NOT NULL,
                        effective_end DATE NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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
                        control_type VARCHAR(32) NULL,
                        effective_from DATE NOT NULL,
                        effective_to DATE NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            def _has_col(table_name: str, col: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name=:table_name
                          AND column_name=:col
                        """
                    ),
                    {"table_name": table_name, "col": col},
                ).fetchone()
                return int(row.cnt or 0) > 0

            if not _has_col("consolidation_ownership", "control_type"):
                conn.execute(text("ALTER TABLE consolidation_ownership ADD COLUMN control_type VARCHAR(32) NULL"))
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_audit_log (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        operator_id BIGINT NULL,
                        action VARCHAR(64) NOT NULL,
                        group_id BIGINT NULL,
                        payload_json JSON NULL,
                        result_status VARCHAR(16) NOT NULL,
                        result_code INT NOT NULL,
                        note VARCHAR(255) NULL
                    )
                    """
                )
            )

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH17-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH17组{self.sid}"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": int(group_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (:gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1)
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH17 AUTH"},
            )

    def _audit_count(self, group_id: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid
                      AND action='type_post'
                    """
                ),
                {"gid": int(group_id)},
            ).fetchone()
        return int(row.c or 0)

    def _insert_ownership(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_ownership WHERE group_id=:gid"),
                {"gid": int(group_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_ownership (
                        group_id, parent_entity_id, child_entity_id, ownership_pct, control_type,
                        effective_from, effective_to, status, is_enabled, operator_id
                    ) VALUES
                        (:gid, 1001, 2001, 0.80, 'same_control', '2025-01-01', '2025-12-31', 'active', 1, 1),
                        (:gid, 1001, 2002, 0.60, 'purchase', '2025-01-01', '2025-12-31', 'active', 1, 1),
                        (:gid, 1001, 2003, 0.30, 'same_control', '2025-01-01', '2025-12-31', 'active', 1, 1)
                    """
                ),
                {"gid": int(group_id)},
            )

    def test_01_post_type_engine_same_vs_non_same_control(self):
        group_id = self._create_group()
        self._insert_ownership(group_id)

        unauth = self.client.post(
            "/api/consolidation/type",
            json={"consolidation_group_id": group_id, "as_of": "2025-03-01", "operator_id": 1},
        )
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))

        self._grant(group_id)
        before = self._audit_count(group_id)
        ok = self.client.post(
            "/api/consolidation/type",
            json={"consolidation_group_id": group_id, "as_of": "2025-03-01", "operator_id": 1},
        )
        self.assertEqual(ok.status_code, 200, ok.get_data(as_text=True))
        body = ok.get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertEqual(int(body.get("group_id") or 0), group_id)
        self.assertEqual(str(body.get("as_of") or ""), "2025-03-01")

        items = body.get("items") or []
        self.assertEqual(len(items), 3)
        d = {int(x["child_entity_id"]): x for x in items}
        self.assertEqual(str(d[2001]["classification"]), "subsidiary")
        self.assertEqual(str(d[2001]["consolidation_type"]), "same_control")
        self.assertTrue(bool(d[2001]["controlled"]))

        self.assertEqual(str(d[2002]["classification"]), "subsidiary")
        self.assertEqual(str(d[2002]["consolidation_type"]), "non_same_control")
        self.assertTrue(bool(d[2002]["controlled"]))

        self.assertEqual(str(d[2003]["classification"]), "associate")
        self.assertEqual(str(d[2003]["consolidation_type"]), "non_same_control")
        self.assertFalse(bool(d[2003]["controlled"]))

        self.assertTrue(str(d[2001].get("rationale") or "").strip())
        summary = body.get("summary") or {}
        self.assertEqual(int(summary.get("same_control_count") or 0), 1)
        self.assertEqual(int(summary.get("non_same_control_count") or 0), 2)
        self.assertEqual(int(summary.get("subsidiary_count") or 0), 2)
        self.assertEqual(int(summary.get("associate_count") or 0), 1)

        invalid = self.client.post(
            "/api/consolidation/type",
            json={"consolidation_group_id": group_id, "as_of": "", "operator_id": 1},
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_data(as_text=True))

        after = self._audit_count(group_id)
        self.assertGreaterEqual(after - before, 2)


if __name__ == "__main__":
    unittest.main()
