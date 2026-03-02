import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch14ConsolidationNciTest(unittest.TestCase):
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
                        is_enabled TINYINT NOT NULL DEFAULT 1
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
                        operator_id BIGINT NOT NULL DEFAULT 0
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

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH14-{self.sid}", "group_name": f"ARCH14组{self.sid}"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (:gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1)
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH14 AUTH"},
            )

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
            insert_vals = [":group_id"]
            params = {"group_id": int(group_id), "book_id": 1}
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
                insert_vals.append("'2025-12-31'")
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
            conn.execute(
                text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"),
                {"gid": int(group_id)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                        virtual_subject_id, parent_subject_type, parent_subject_id, child_subject_type, child_subject_id,
                        ownership_ratio, control_type, include_in_consolidation,
                        effective_start, effective_end, status, operator_id,
                        consolidation_method, default_scope, effective_from
                    ) VALUES (
                        :gid, '', :gid, '', :gid,
                        1.000000, '2025-01', 1,
                        '2025-01-01', '2099-12-31', 'active', 1,
                        'full', 'raw', '2025-01-01'
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
                        :gid, 1001, :child_id, :pct, '2025-01-01', '2025-12-31', 'active', 1, 1
                    )
                    """
                ),
                {"gid": int(group_id), "child_id": int(child_id), "pct": pct},
            )

    def test_01_nci_contract(self):
        gid = self._create_group()
        self._grant(gid)
        self._insert_member(gid)
        self._insert_method_full(gid)
        self._insert_ownership(gid, 2001, "0.6")
        self._insert_ownership(gid, 2002, "1.0")
        self._insert_ownership(gid, 2003, "0.3")

        resp = self.client.get(
            "/api/consolidation/nci",
            query_string={"consolidation_group_id": gid, "as_of": "2025-03-01"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        items = (resp.get_json() or {}).get("items") or []
        by_entity = {int(x["entity_id"]): x for x in items}

        self.assertAlmostEqual(float(by_entity[2001]["nci_pct"]), 0.4, places=6)
        self.assertAlmostEqual(float(by_entity[2002]["nci_pct"]), 0.0, places=6)
        self.assertAlmostEqual(float(by_entity[2003]["nci_pct"]), 0.0, places=6)
        self.assertTrue(str(by_entity[2001].get("rationale") or "").strip())
        self.assertTrue(str(by_entity[2002].get("rationale") or "").strip())
        self.assertTrue(str(by_entity[2003].get("rationale") or "").strip())


if __name__ == "__main__":
    unittest.main()
