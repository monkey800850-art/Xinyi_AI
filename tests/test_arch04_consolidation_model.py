import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch04ConsolidationModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"
        from pathlib import Path

        REPO_ROOT = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(REPO_ROOT))
        ns = runpy.run_path(str(REPO_ROOT / "app.py"))
        cls.app = ns["create_app"]()
        cls.client = cls.app.test_client()
        cls.sid = str(int(time.time()))[-6:]
        cls.engine = get_engine()
        cls._ensure_tables_for_test()

    @classmethod
    def _ensure_tables_for_test(cls):
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS legal_entities (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        entity_code VARCHAR(64) NOT NULL UNIQUE,
                        entity_name VARCHAR(128) NOT NULL,
                        entity_kind VARCHAR(16) NOT NULL DEFAULT 'legal',
                        book_id BIGINT NULL,
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
                    CREATE TABLE IF NOT EXISTS virtual_entities (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        virtual_code VARCHAR(64) NOT NULL UNIQUE,
                        virtual_name VARCHAR(128) NOT NULL,
                        book_id BIGINT NULL,
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
                        member_entity_id BIGINT NULL,
                        member_type VARCHAR(16) NOT NULL,
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
            # Compatibility for legacy table structures in local DB:
            # ensure ARCH-04 required columns exist even when table was created by older scripts.
            def _has_column(table_name: str, column_name: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = :table_name
                          AND column_name = :column_name
                        """
                    ),
                    {"table_name": table_name, "column_name": column_name},
                ).fetchone()
                return int(row.cnt or 0) > 0

            if not _has_column("consolidation_groups", "group_type"):
                conn.execute(
                    text("ALTER TABLE consolidation_groups ADD COLUMN group_type VARCHAR(32) NOT NULL DEFAULT 'standard'")
                )
            if not _has_column("consolidation_group_members", "member_book_id"):
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN member_book_id BIGINT NULL")
                )
            if not _has_column("consolidation_group_members", "member_entity_id"):
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN member_entity_id BIGINT NULL")
                )
            if not _has_column("consolidation_group_members", "member_type"):
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN member_type VARCHAR(16) NOT NULL DEFAULT 'BOOK'")
                )
            if not _has_column("consolidation_group_members", "effective_from"):
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN effective_from DATE NULL")
                )
            if not _has_column("consolidation_group_members", "effective_to"):
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN effective_to DATE NULL")
                )

    def _create_book(self) -> int:
        payload = {"name": f"ARCH04_BOOK_{self.sid}", "accounting_standard": "enterprise"}
        payload.setdefault("book_code", payload.get("book_name") or f"BK_{self.sid}")
        payload.setdefault("start_period", "2026-01")
        resp = self.client.post(
            "/books",
            json=payload,
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def test_01_create_group_member_and_query_effective(self):
        b1 = self._create_book()
        b2 = self._create_book()

        create_group = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"G{self.sid}", "group_name": f"合并组{self.sid}", "group_type": "finance"},
        )
        self.assertEqual(create_group.status_code, 201, create_group.get_data(as_text=True))
        gid = int(create_group.get_json()["id"])

        m1 = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "BOOK",
                "member_book_id": b1,
                "effective_from": "2025-01-01",
                "effective_to": "2025-06-30",
            },
        )
        self.assertEqual(m1.status_code, 201, m1.get_data(as_text=True))
        m2 = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "BOOK",
                "member_book_id": b2,
                "effective_from": "2025-07-01",
                "effective_to": "",
            },
        )
        self.assertEqual(m2.status_code, 201, m2.get_data(as_text=True))

        q1 = self.client.get(
            f"/api/consolidation/groups/{gid}/members/effective",
            query_string={"as_of_date": "2025-03-01"},
        )
        self.assertEqual(q1.status_code, 200, q1.get_data(as_text=True))
        data1 = q1.get_json()
        self.assertIn(b1, data1["member_book_ids"])
        self.assertNotIn(b2, data1["member_book_ids"])

        q2 = self.client.get(
            f"/api/consolidation/groups/{gid}/members/effective",
            query_string={"as_of_date": "2025-08-01"},
        )
        self.assertEqual(q2.status_code, 200, q2.get_data(as_text=True))
        data2 = q2.get_json()
        self.assertIn(b2, data2["member_book_ids"])
        self.assertNotIn(b1, data2["member_book_ids"])

    def test_02_member_overlap_blocked(self):
        b1 = self._create_book()
        create_group = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"GOV{self.sid}", "group_name": f"重叠校验{self.sid}"},
        )
        self.assertEqual(create_group.status_code, 201, create_group.get_data(as_text=True))
        gid = int(create_group.get_json()["id"])

        ok = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "BOOK",
                "member_book_id": b1,
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
            },
        )
        self.assertEqual(ok.status_code, 201, ok.get_data(as_text=True))

        overlap = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "BOOK",
                "member_book_id": b1,
                "effective_from": "2025-06-01",
                "effective_to": "2025-07-01",
            },
        )
        self.assertEqual(overlap.status_code, 400, overlap.get_data(as_text=True))
        self.assertIn("member_effective_period_overlap", overlap.get_json().get("error", ""))

    def test_03_legal_and_virtual_member_types(self):
        book_id = self._create_book()
        with self.engine.begin() as conn:
            legal_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO legal_entities (entity_code, entity_name, entity_kind, status, is_enabled)
                        VALUES (:code, :name, 'legal', 'active', 1)
                        """
                    ),
                    {"code": f"LE{self.sid}", "name": f"法人{self.sid}"},
                ).lastrowid
            )
            virtual_id = int(
                conn.execute(
                    text(
                        """
                        INSERT INTO virtual_entities (virtual_code, virtual_name, status, is_enabled)
                        VALUES (:code, :name, 'active', 1)
                        """
                    ),
                    {"code": f"VE{self.sid}", "name": f"虚拟主体{self.sid}"},
                ).lastrowid
            )

        create_group = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"GT{self.sid}", "group_name": f"类型校验{self.sid}"},
        )
        self.assertEqual(create_group.status_code, 201, create_group.get_data(as_text=True))
        gid = int(create_group.get_json()["id"])

        legal_member = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "LEGAL",
                "member_book_id": book_id,
                "member_entity_id": legal_id,
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
            },
        )
        self.assertEqual(legal_member.status_code, 201, legal_member.get_data(as_text=True))

        virtual_member = self.client.post(
            f"/api/consolidation/groups/{gid}/members",
            json={
                "member_type": "VIRTUAL",
                "member_book_id": book_id,
                "member_entity_id": virtual_id,
                "effective_from": "2025-01-01",
                "effective_to": "",
            },
        )
        self.assertEqual(virtual_member.status_code, 201, virtual_member.get_data(as_text=True))

        query = self.client.get(
            f"/api/consolidation/groups/{gid}/members/effective",
            query_string={"as_of_date": "2025-06-01"},
        )
        self.assertEqual(query.status_code, 200, query.get_data(as_text=True))
        members = query.get_json().get("members", [])
        member_types = {str(item.get("member_type") or "") for item in members}
        self.assertIn("LEGAL", member_types)
        self.assertIn("VIRTUAL", member_types)


if __name__ == "__main__":
    unittest.main()
