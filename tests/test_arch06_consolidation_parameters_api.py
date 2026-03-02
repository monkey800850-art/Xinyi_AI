import os
import runpy
import sys
import time
import unittest
from datetime import date

from sqlalchemy import text

from app.db import get_engine


class Arch06ConsolidationParametersApiTest(unittest.TestCase):
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
        cls.group_id = int(cls.sid)
        cls._ensure_tables()

    @classmethod
    def _ensure_tables(cls):
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_authorizations (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        approval_document_number VARCHAR(64) NOT NULL,
                        approval_document_name VARCHAR(128) NOT NULL,
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
                    CREATE TABLE IF NOT EXISTS consolidation_parameters (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_subject_id BIGINT NOT NULL,
                        parent_subject_type VARCHAR(32) NOT NULL,
                        parent_subject_id BIGINT NOT NULL,
                        child_subject_type VARCHAR(32) NOT NULL,
                        child_subject_id BIGINT NOT NULL,
                        ownership_ratio DECIMAL(9,6) NOT NULL DEFAULT 0,
                        control_type VARCHAR(32) NOT NULL DEFAULT 'control',
                        include_in_consolidation TINYINT NOT NULL DEFAULT 1,
                        effective_start DATE NOT NULL,
                        effective_end DATE NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )

    def setUp(self):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"),
                {"gid": self.group_id},
            )
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": self.group_id},
            )

    def _grant_authorization(self):
        today = date.today().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id,
                        approval_document_number,
                        approval_document_name,
                        effective_start,
                        effective_end,
                        status,
                        operator_id
                    ) VALUES (
                        :gid,
                        :doc_no,
                        :doc_name,
                        :start_date,
                        '2099-12-31',
                        'active',
                        1
                    )
                    """
                ),
                {
                    "gid": self.group_id,
                    "doc_no": f"AUTH-{self.sid}",
                    "doc_name": "ARCH06 授权",
                    "start_date": today,
                },
            )

    def test_01_get_unauthorized_returns_403(self):
        resp = self.client.get(
            "/api/consolidation/parameters",
            query_string={"consolidation_group_id": self.group_id},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertEqual(body.get("error"), "forbidden")

    def test_02_authorized_get_returns_contract(self):
        self._grant_authorization()
        resp = self.client.get(
            "/api/consolidation/parameters",
            query_string={"consolidation_group_id": self.group_id},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body.get("ok"))
        self.assertIn("items", body)
        self.assertIn("version", body)
        self.assertIn("ts", body)
        self.assertIsInstance(body["items"], list)

    def test_03_write_then_read_back(self):
        self._grant_authorization()
        payload = {
            "consolidation_group_id": self.group_id,
            "start_period": "2026-03",
            "note": "arch06 write",
            "operator_id": 7,
        }
        write_resp = self.client.put("/api/consolidation/parameters", json=payload)
        self.assertEqual(write_resp.status_code, 200, write_resp.get_data(as_text=True))
        self.assertTrue(write_resp.get_json().get("ok"))

        read_resp = self.client.get(
            "/api/consolidation/parameters",
            query_string={"consolidation_group_id": self.group_id},
        )
        self.assertEqual(read_resp.status_code, 200, read_resp.get_data(as_text=True))
        body = read_resp.get_json()
        self.assertTrue(body.get("ok"))
        self.assertGreaterEqual(len(body.get("items") or []), 1)
        latest = body["items"][0]
        self.assertEqual(int(latest["consolidation_group_id"]), self.group_id)
        self.assertEqual(latest["start_period"], "2026-03")
        self.assertEqual(latest["note"], "arch06 write")


if __name__ == "__main__":
    unittest.main()
