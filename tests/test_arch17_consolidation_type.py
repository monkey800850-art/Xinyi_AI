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
                    CREATE TABLE IF NOT EXISTS consolidation_group_types (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        consolidation_type VARCHAR(32) NOT NULL,
                        note VARCHAR(255) NULL,
                        created_by BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_by BIGINT NOT NULL DEFAULT 0,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_conso_group_types_group (group_id)
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
                      AND action IN ('type_get', 'type_post')
                    """
                ),
                {"gid": int(group_id)},
            ).fetchone()
        return int(row.c or 0)

    def test_01_consolidation_type_contract_auth_and_validation(self):
        group_id = self._create_group()

        unauth_get = self.client.get("/api/consolidation/type", query_string={"group_id": group_id})
        self.assertEqual(unauth_get.status_code, 403, unauth_get.get_data(as_text=True))

        unauth_post = self.client.post(
            "/api/consolidation/type",
            json={"group_id": group_id, "consolidation_type": "same_control", "operator_id": 1},
        )
        self.assertEqual(unauth_post.status_code, 403, unauth_post.get_data(as_text=True))

        self._grant(group_id)
        before = self._audit_count(group_id)

        default_get = self.client.get("/api/consolidation/type", query_string={"group_id": group_id})
        self.assertEqual(default_get.status_code, 200, default_get.get_data(as_text=True))
        default_item = (default_get.get_json() or {}).get("item") or {}
        self.assertEqual(str(default_item.get("consolidation_type") or ""), "purchase")
        self.assertTrue(bool(default_item.get("is_default")))

        set_same = self.client.post(
            "/api/consolidation/type",
            json={"group_id": group_id, "consolidation_type": "same_control", "note": "arch17", "operator_id": 9},
        )
        self.assertEqual(set_same.status_code, 200, set_same.get_data(as_text=True))
        same_item = (set_same.get_json() or {}).get("item") or {}
        self.assertEqual(str(same_item.get("consolidation_type") or ""), "same_control")
        self.assertEqual(str(same_item.get("note") or ""), "arch17")

        set_purchase = self.client.post(
            "/api/consolidation/type",
            json={"group_id": group_id, "consolidation_type": "purchase", "operator_id": 9},
        )
        self.assertEqual(set_purchase.status_code, 200, set_purchase.get_data(as_text=True))
        purchase_item = (set_purchase.get_json() or {}).get("item") or {}
        self.assertEqual(str(purchase_item.get("consolidation_type") or ""), "purchase")

        invalid = self.client.post(
            "/api/consolidation/type",
            json={"group_id": group_id, "consolidation_type": "invalid_type", "operator_id": 9},
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_data(as_text=True))

        after = self._audit_count(group_id)
        self.assertGreaterEqual(after - before, 4)


if __name__ == "__main__":
    unittest.main()
