import os
import runpy
import sys
import time
import unittest
from datetime import date

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch08ConsolidationOnboardingAuditTest(unittest.TestCase):
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
        cls.book_id = cls._create_book_for_member()

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
                        book_id BIGINT NOT NULL,
                        member_book_id BIGINT NULL,
                        member_entity_id BIGINT NULL,
                        member_type VARCHAR(16) NOT NULL DEFAULT 'BOOK',
                        effective_from DATE NULL,
                        effective_to DATE NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        note VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            has_book_id = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name = 'consolidation_group_members'
                      AND column_name = 'book_id'
                    """
                )
            ).fetchone()
            if int(has_book_id.cnt or 0) == 0:
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN book_id BIGINT NOT NULL DEFAULT 0")
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

    @classmethod
    def _create_book_for_member(cls) -> int:
        payload = make_book_payload(cls.sid, suffix="ARCH08")
        resp = cls.client.post("/books", json=payload)
        if resp.status_code != 201:
            raise AssertionError(resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _create_group(self) -> int:
        code = f"ARCH08-{self.sid}-{self._testMethodName[-2:]}"
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": code, "group_name": f"ARCH08组{code}", "group_type": "standard"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant_authorization(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": group_id},
            )
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
                        9
                    )
                    """
                ),
                {
                    "gid": group_id,
                    "doc_no": f"AUTH-{group_id}",
                    "doc_name": "ARCH08 AUTH",
                    "start_date": date.today().isoformat(),
                },
            )

    def _audit_count(self, group_id: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid
                      AND action IN ('members_post', 'read_probe')
                    """
                ),
                {"gid": group_id},
            ).fetchone()
        return int(row.c or 0)

    def test_01_unauthorized_members_post_and_read_probe_forbidden(self):
        group_id = self._create_group()
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": group_id},
            )
        m_resp = self.client.post(
            "/api/consolidation/members",
            json={
                "consolidation_group_id": group_id,
                "member_book_id": self.book_id,
                "member_type": "BOOK",
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "operator_id": 88,
            },
        )
        self.assertEqual(m_resp.status_code, 403, m_resp.get_data(as_text=True))
        self.assertEqual((m_resp.get_json() or {}).get("error"), "forbidden")

        p_resp = self.client.get(
            "/api/consolidation/read_probe",
            query_string={"consolidation_group_id": group_id},
        )
        self.assertEqual(p_resp.status_code, 403, p_resp.get_data(as_text=True))
        self.assertEqual((p_resp.get_json() or {}).get("error"), "forbidden")

    def test_02_authorized_members_post_and_read_probe_success_with_audit(self):
        group_id = self._create_group()
        self._grant_authorization(group_id)

        before = self._audit_count(group_id)
        m_resp = self.client.post(
            "/api/consolidation/members",
            json={
                "consolidation_group_id": group_id,
                "member_book_id": self.book_id,
                "member_type": "BOOK",
                "effective_from": "2026-01-01",
                "effective_to": "2026-12-31",
                "operator_id": 77,
            },
        )
        self.assertIn(m_resp.status_code, (200, 201), m_resp.get_data(as_text=True))
        m_data = m_resp.get_json() or {}
        self.assertTrue(m_data.get("ok"))

        p_resp = self.client.get(
            "/api/consolidation/read_probe",
            query_string={"consolidation_group_id": group_id},
        )
        self.assertEqual(p_resp.status_code, 200, p_resp.get_data(as_text=True))
        p_data = p_resp.get_json() or {}
        self.assertTrue(p_data.get("ok"))

        after = self._audit_count(group_id)
        self.assertGreaterEqual(after - before, 2)


if __name__ == "__main__":
    unittest.main()
