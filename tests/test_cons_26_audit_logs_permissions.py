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


class Cons26AuditLogsPermissionsTest(unittest.TestCase):
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
            json={
                "group_code": f"CONS26-{self.sid}-{self._testMethodName[-2:]}",
                "group_name": f"CONS26组{self.sid}",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"), {"gid": group_id})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (
                        :gid, :doc_no, :doc_name, '2025-01-01', '2025-12-31', 'active', 1
                    )
                    """
                ),
                {"gid": group_id, "doc_no": f"AUTH-{group_id}", "doc_name": "CONS26 AUTH"},
            )

    def test_01_audit_and_permission_control(self):
        gid = self._create_group()
        payload = {
            "consolidation_group_id": gid,
            "as_of": "2025-04-30",
            "operator_id": 1,
            "action_content": "cons26-check",
        }

        unauth = self.client.post("/task/cons-26", json=payload)
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))
        unauth_body = unauth.get_json() or {}
        self.assertEqual(str(unauth_body.get("status") or ""), "failed")
        self.assertFalse(bool(unauth_body.get("permission_granted")))

        with self.engine.connect() as conn:
            row1 = conn.execute(
                text(
                    """
                    SELECT ts, operator_id, action, group_id, payload_json, result_status, result_code, note
                    FROM consolidation_audit_log
                    WHERE action='cons26_audit_permission_control' AND group_id=:gid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
        self.assertIsNotNone(row1)
        payload_json_1 = json.loads(str(row1.payload_json or "{}"))
        self.assertEqual(int(row1.operator_id or 0), 1)
        self.assertTrue(str(row1.ts or ""))
        self.assertEqual(str(row1.action or ""), "cons26_audit_permission_control")
        self.assertEqual(str(row1.result_status or ""), "forbidden")
        self.assertEqual(int(row1.result_code or 0), 403)
        self.assertEqual(str(payload_json_1.get("action_content") or ""), "cons26-check")
        self.assertFalse(bool(payload_json_1.get("permission_granted")))

        self._grant(gid)
        ok = self.client.post("/task/cons-26", json=payload)
        self.assertEqual(ok.status_code, 200, ok.get_data(as_text=True))
        body = ok.get_json() or {}
        self.assertEqual(str(body.get("status") or ""), "success")
        self.assertTrue(bool(body.get("permission_granted")))
        audit_log = body.get("audit_log") or {}
        self.assertEqual(int(audit_log.get("operator_id") or 0), 1)
        self.assertTrue(str(audit_log.get("ts") or ""))
        self.assertEqual(str(audit_log.get("action") or ""), "cons26_audit_permission_control")
        self.assertTrue(str(audit_log.get("note") or ""))

        with self.engine.connect() as conn:
            row2 = conn.execute(
                text(
                    """
                    SELECT ts, operator_id, action, group_id, payload_json, result_status, result_code, note
                    FROM consolidation_audit_log
                    WHERE action='cons26_audit_permission_control' AND group_id=:gid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
        self.assertEqual(str(row2.result_status or ""), "success")
        self.assertEqual(int(row2.result_code or 0), 200)
        self.assertEqual(int(row2.operator_id or 0), 1)
        self.assertTrue(str(row2.ts or ""))


if __name__ == "__main__":
    unittest.main()
