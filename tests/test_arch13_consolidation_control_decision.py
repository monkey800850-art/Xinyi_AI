import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch13ConsolidationControlDecisionTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_group_members (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        member_book_id BIGINT NULL,
                        member_entity_id BIGINT NULL,
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
                        effective_from DATE NULL,
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

    def _create_group(self, suffix: str) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH13-{self.sid}-{suffix}", "group_name": f"ARCH13组{self.sid}-{suffix}"},
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
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH13 AUTH"},
            )

    def _insert_member(self, group_id: int, book_id: int):
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
            params = {"group_id": int(group_id), "book_id": int(book_id)}
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

    def _insert_method(self, group_id: int, method: str):
        with self.engine.begin() as conn:
            cols = {
                str(r[0] or "").strip().lower()
                for r in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = 'consolidation_parameters'
                        """
                    )
                ).fetchall()
            }
            conn.execute(
                text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"),
                {"gid": int(group_id)},
            )
            insert_cols = []
            insert_vals = []
            params = {"gid": int(group_id), "method": method}
            def add(name: str, expr: str):
                insert_cols.append(name)
                insert_vals.append(expr)

            add("virtual_subject_id", ":gid")
            if "parent_subject_type" in cols:
                add("parent_subject_type", "''")
            if "parent_subject_id" in cols:
                add("parent_subject_id", ":gid")
            if "child_subject_type" in cols:
                add("child_subject_type", "''")
            if "child_subject_id" in cols:
                add("child_subject_id", ":gid")
            if "ownership_ratio" in cols:
                add("ownership_ratio", "1.000000")
            if "control_type" in cols:
                add("control_type", "'2025-01'")
            if "include_in_consolidation" in cols:
                add("include_in_consolidation", "1")
            if "effective_start" in cols:
                add("effective_start", "'2025-01-01'")
            if "effective_end" in cols:
                add("effective_end", "'2099-12-31'")
            if "status" in cols:
                add("status", "'active'")
            if "operator_id" in cols:
                add("operator_id", "1")
            if "consolidation_method" in cols:
                add("consolidation_method", ":method")
            if "default_scope" in cols:
                add("default_scope", "'raw'")
            if "effective_from" in cols:
                add("effective_from", "'2025-01-01'")
            conn.execute(
                text(
                    f"""
                    INSERT INTO consolidation_parameters ({', '.join(insert_cols)})
                    VALUES ({', '.join(insert_vals)})
                    """
                ),
                params,
            )

    def _insert_ownership(self, group_id: int, parent_id: int, child_id: int, pct: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_ownership (
                        group_id, parent_entity_id, child_entity_id, ownership_pct,
                        effective_from, effective_to, status, is_enabled, operator_id
                    ) VALUES (
                        :gid, :pid, :cid, :pct, '2025-01-01', '2025-12-31', 'active', 1, 1
                    )
                    """
                ),
                {"gid": int(group_id), "pid": int(parent_id), "cid": int(child_id), "pct": pct},
            )

    def test_01_full_method_subsidiary_and_none(self):
        gid = self._create_group("F")
        self._grant(gid)
        self._insert_member(gid, 1)
        self._insert_method(gid, "full")
        self._insert_ownership(gid, 1001, 2001, "0.6")
        self._insert_ownership(gid, 1001, 2002, "0.3")

        resp = self.client.get(
            "/api/consolidation/control_decision",
            query_string={"consolidation_group_id": gid, "as_of": "2025-03-01"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        items = (resp.get_json() or {}).get("items") or []
        d = {int(x["child_entity_id"]): x for x in items}
        self.assertEqual(d[2001]["classification"], "subsidiary")
        self.assertTrue(d[2001]["include_in_full"])
        self.assertEqual(d[2002]["classification"], "none")
        self.assertTrue(str(d[2001].get("rationale") or "").strip())

    def test_02_equity_method_associate(self):
        gid = self._create_group("E")
        self._grant(gid)
        self._insert_member(gid, 1)
        self._insert_method(gid, "equity")
        self._insert_ownership(gid, 1002, 3001, "0.3")

        resp = self.client.get(
            "/api/consolidation/control_decision",
            query_string={"consolidation_group_id": gid, "as_of": "2025-03-01"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        items = (resp.get_json() or {}).get("items") or []
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["classification"], "associate")
        self.assertTrue(str(items[0].get("rationale") or "").strip())


if __name__ == "__main__":
    unittest.main()
