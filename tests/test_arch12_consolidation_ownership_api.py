import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch12ConsolidationOwnershipApiTest(unittest.TestCase):
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
            json={"group_code": f"ARCH12-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH12组{self.sid}"},
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
                    ) VALUES (
                        :gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1
                    )
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH12 AUTH"},
            )

    def _audit_count(self, group_id: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid
                      AND action IN ('ownership_post', 'ownership_get')
                    """
                ),
                {"gid": int(group_id)},
            ).fetchone()
        return int(row.c or 0)

    def test_01_ownership_auth_and_query_and_audit(self):
        group_id = self._create_group()

        unauth_post = self.client.post(
            "/api/consolidation/ownership",
            json={
                "consolidation_group_id": group_id,
                "parent_entity_id": 1001,
                "child_entity_id": 1002,
                "ownership_pct": "60",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
                "operator_id": 1,
            },
        )
        self.assertEqual(unauth_post.status_code, 403, unauth_post.get_data(as_text=True))
        unauth_get = self.client.get(
            "/api/consolidation/ownership",
            query_string={"consolidation_group_id": group_id, "as_of": "2025-03-01"},
        )
        self.assertEqual(unauth_get.status_code, 403, unauth_get.get_data(as_text=True))

        self._grant(group_id)
        before = self._audit_count(group_id)
        ok_post = self.client.post(
            "/api/consolidation/ownership",
            json={
                "consolidation_group_id": group_id,
                "parent_entity_id": 1001,
                "child_entity_id": 1002,
                "ownership_pct": "60",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
                "operator_id": 1,
            },
        )
        self.assertEqual(ok_post.status_code, 201, ok_post.get_data(as_text=True))
        item = (ok_post.get_json() or {}).get("item") or {}
        self.assertEqual(item.get("ownership_scale"), "0_to_1_ratio")
        self.assertAlmostEqual(float(item.get("ownership_pct") or 0.0), 0.6, places=6)

        ok_get = self.client.get(
            "/api/consolidation/ownership",
            query_string={"consolidation_group_id": group_id, "as_of": "2025-03-01"},
        )
        self.assertEqual(ok_get.status_code, 200, ok_get.get_data(as_text=True))
        data = ok_get.get_json() or {}
        self.assertGreaterEqual(len(data.get("items") or []), 1)

        after = self._audit_count(group_id)
        self.assertGreaterEqual(after - before, 2)


if __name__ == "__main__":
    unittest.main()
