import os
import runpy
import sys
import time
import unittest
from datetime import date

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch09ConsolidationScopeEffectiveMembersTest(unittest.TestCase):
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
            has_legacy_book = conn.execute(
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
            if int(has_legacy_book.cnt or 0) == 0:
                conn.execute(
                    text("ALTER TABLE consolidation_group_members ADD COLUMN book_id BIGINT NULL")
                )

    def _create_book(self, suffix: str) -> int:
        payload = make_book_payload(self.sid, suffix=suffix)
        resp = self.client.post("/books", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _pick_leaf_subject_codes(self, book_id: int):
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT s.code
                    FROM subjects s
                    WHERE s.book_id=:book_id
                      AND s.is_enabled=1
                      AND COALESCE(s.requires_auxiliary, 0) = 0
                      AND COALESCE(s.requires_bank_account_aux, 0) = 0
                      AND NOT EXISTS (
                        SELECT 1
                        FROM subjects c
                        WHERE c.book_id=s.book_id
                          AND TRIM(TRAILING '.' FROM COALESCE(c.parent_code, '')) = s.code
                      )
                    ORDER BY s.code ASC
                    LIMIT 2
                    """
                ),
                {"book_id": book_id},
            ).fetchall()
        if len(rows) < 2:
            raise AssertionError("leaf_subjects_not_enough")
        return str(rows[0].code), str(rows[1].code)

    def _post_voucher(self, book_id: int, voucher_no: str, amount: str) -> str:
        debit_code, credit_code = self._pick_leaf_subject_codes(book_id)
        payload = {
            "book_id": book_id,
            "voucher_date": "2025-02-20",
            "voucher_word": "记",
            "voucher_no": voucher_no,
            "attachments": 0,
            "maker": "arch09",
            "status": "posted",
            "lines": [
                {"summary": "ARCH09借", "subject_code": debit_code, "debit": amount, "credit": "0.00"},
                {"summary": "ARCH09贷", "subject_code": credit_code, "debit": "0.00", "credit": amount},
            ],
        }
        resp = self.client.post("/api/vouchers", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return debit_code

    def _grant_authorization(self, group_id: int):
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
                        :gid, :doc_no, :doc_name, :start_date, '2099-12-31', 'active', 1
                    )
                    """
                ),
                {
                    "gid": int(group_id),
                    "doc_no": f"AUTH-ARCH09-{group_id}",
                    "doc_name": "ARCH09 AUTH",
                    "start_date": "2025-01-01",
                },
            )

    def _insert_group_member(self, group_id: int, book_id: int, effective_from: str, effective_to: str):
        with self.engine.begin() as conn:
            mcols = {
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
            cols = ["group_id"]
            vals = [":group_id"]
            params = {"group_id": int(group_id)}
            if "member_book_id" in mcols:
                cols.append("member_book_id")
                vals.append(":book_id")
                params["book_id"] = int(book_id)
            if "book_id" in mcols:
                cols.append("book_id")
                vals.append(":legacy_book_id")
                params["legacy_book_id"] = int(book_id)
            if "member_type" in mcols:
                cols.append("member_type")
                vals.append("'BOOK'")
            if "effective_from" in mcols:
                cols.append("effective_from")
                vals.append(":effective_from")
                params["effective_from"] = effective_from
            if "effective_to" in mcols:
                cols.append("effective_to")
                vals.append(":effective_to")
                params["effective_to"] = effective_to
            if "status" in mcols:
                cols.append("status")
                vals.append("'active'")
            if "is_enabled" in mcols:
                cols.append("is_enabled")
                vals.append("1")

            conn.execute(
                text(
                    f"""
                    INSERT INTO consolidation_group_members ({', '.join(cols)})
                    VALUES ({', '.join(vals)})
                    """
                ),
                params,
            )

    def test_01_consolidation_group_only_sums_effective_members(self):
        book_a = self._create_book("A09")
        book_b = self._create_book("B09")
        debit_a = self._post_voucher(book_a, f"A09-{self.sid}", "100.00")
        debit_b = self._post_voucher(book_b, f"B09-{self.sid}", "200.00")
        self.assertEqual(debit_a, debit_b)

        create_group_resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH09-{self.sid}", "group_name": f"ARCH09组{self.sid}", "group_type": "standard"},
        )
        self.assertEqual(create_group_resp.status_code, 201, create_group_resp.get_data(as_text=True))
        group_id = int(create_group_resp.get_json()["id"])

        self._insert_group_member(group_id, book_a, "2025-01-01", "2025-12-31")
        self._insert_group_member(group_id, book_b, "2026-01-01", "2026-12-31")
        self._grant_authorization(group_id)

        resp = self.client.get(
            "/api/trial_balance",
            query_string={
                "consolidation_group_id": group_id,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertEqual(data.get("query_mode"), "consolidation_group")
        self.assertEqual(int(data.get("consolidation_group_id")), group_id)
        debit_line = next(x for x in data.get("items") or [] if x.get("code") == debit_a)
        self.assertAlmostEqual(float(debit_line.get("period_debit") or 0.0), 100.0, places=2)
        notice = str(data.get("scope_notice") or "")
        self.assertIn("仅汇总未抵销", notice)
        self.assertIn("有效成员 1", notice)


if __name__ == "__main__":
    unittest.main()
