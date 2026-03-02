import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch05ConsolidationReportsTest(unittest.TestCase):
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
        cls._ensure_consolidation_tables()

    @classmethod
    def _ensure_consolidation_tables(cls):
        with cls.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_groups (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_code VARCHAR(64) NOT NULL,
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
                    CREATE TABLE IF NOT EXISTS consolidation_group_members (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        member_book_id BIGINT NULL,
                        member_entity_id BIGINT NULL,
                        member_type VARCHAR(16) NOT NULL DEFAULT 'BOOK',
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        is_enabled TINYINT NOT NULL DEFAULT 1,
                        effective_from DATE NULL,
                        effective_to DATE NULL
                    )
                    """
                )
            )
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
                        is_enabled TINYINT NOT NULL DEFAULT 1
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
                        is_enabled TINYINT NOT NULL DEFAULT 1
                    )
                    """
                )
            )

    def _create_book(self, suffix: str) -> int:
        payload = make_book_payload(self.sid, suffix=suffix)
        resp = self.client.post(
            "/books",
            json=payload,
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _post_voucher(self, book_id: int, voucher_no: str, amount: str):
        debit_code, credit_code = self._pick_leaf_subject_codes(book_id)
        payload = {
            "book_id": book_id,
            "voucher_date": "2025-02-20",
            "voucher_word": "记",
            "voucher_no": voucher_no,
            "attachments": 0,
            "maker": "arch05",
            "status": "posted",
            "lines": [
                {"summary": "ARCH05借", "subject_code": debit_code, "debit": amount, "credit": "0.00"},
                {"summary": "ARCH05贷", "subject_code": credit_code, "debit": "0.00", "credit": amount},
            ],
        }
        resp = self.client.post("/api/vouchers", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return debit_code

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

    def _create_consolidation_group(self, group_code: str, group_name: str, book_ids):
        with self.engine.begin() as conn:
            gcols = {
                str(r[0] or "").strip().lower()
                for r in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = 'consolidation_groups'
                        """
                    )
                ).fetchall()
            }
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
            if "group_type" in gcols:
                insert_group_sql = """
                    INSERT INTO consolidation_groups (group_code, group_name, group_type, status, is_enabled)
                    VALUES (:group_code, :group_name, 'standard', 'active', 1)
                """
            else:
                insert_group_sql = """
                    INSERT INTO consolidation_groups (group_code, group_name, status, is_enabled)
                    VALUES (:group_code, :group_name, 'active', 1)
                """
            result = conn.execute(
                text(insert_group_sql),
                {"group_code": group_code, "group_name": group_name},
            )
            gid = int(result.lastrowid)
            for bid in book_ids:
                has_book_id = "book_id" in mcols
                has_member_book_id = "member_book_id" in mcols
                if has_book_id and has_member_book_id:
                    member_book_col = "book_id, member_book_id"
                    member_book_val = ":book_id, :book_id"
                else:
                    member_book_col = "member_book_id" if has_member_book_id else "book_id"
                    member_book_val = ":book_id"
                member_entity_part = ", member_entity_id" if "member_entity_id" in mcols else ""
                member_entity_val = ", NULL" if "member_entity_id" in mcols else ""
                member_type_part = ", member_type" if "member_type" in mcols else ""
                member_type_val = ", 'BOOK'" if "member_type" in mcols else ""
                from_col = "effective_from" if "effective_from" in mcols else ("valid_from" if "valid_from" in mcols else "")
                to_col = "effective_to" if "effective_to" in mcols else ("valid_to" if "valid_to" in mcols else "")
                period_cols = f", {from_col}, {to_col}" if from_col and to_col else ""
                period_vals = ", '2025-01-01', NULL" if from_col and to_col else ""
                conn.execute(
                    text(
                        f"""
                        INSERT INTO consolidation_group_members (
                            group_id, {member_book_col}{member_entity_part}{member_type_part}{period_cols}, status, is_enabled
                        )
                        VALUES (
                            :gid, {member_book_val}{member_entity_val}{member_type_val}{period_vals}, 'active', 1
                        )
                        """
                    ),
                    {"gid": gid, "book_id": int(bid)},
                )
        return gid

    def test_01_trial_balance_single_and_consolidation_modes(self):
        book_a = self._create_book("A")
        book_b = self._create_book("B")
        debit_code_a = self._post_voucher(book_a, f"A{self.sid}", "100.00")
        debit_code_b = self._post_voucher(book_b, f"B{self.sid}", "200.00")
        self.assertEqual(debit_code_a, debit_code_b)
        gid = self._create_consolidation_group(f"G{self.sid}", f"ARCH05组{self.sid}", [book_a, book_b])

        single = self.client.get(
            "/api/trial_balance",
            query_string={"book_id": book_a, "start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        self.assertEqual(single.status_code, 200, single.get_data(as_text=True))
        s_data = single.get_json()
        s_1001 = next(x for x in s_data["items"] if x["code"] == debit_code_a)
        self.assertEqual(s_data["query_mode"], "single_book")
        self.assertEqual(s_data.get("book_view_mode"), "legal_natural")
        self.assertAlmostEqual(float(s_1001["period_debit"]), 100.0, places=2)

        merged = self.client.get(
            "/api/trial_balance",
            query_string={"consolidation_group_id": gid, "start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        self.assertEqual(merged.status_code, 200, merged.get_data(as_text=True))
        m_data = merged.get_json()
        m_1001 = next(x for x in m_data["items"] if x["code"] == debit_code_a)
        self.assertEqual(m_data["query_mode"], "consolidation_group")
        self.assertEqual(int(m_data["consolidation_group_id"]), gid)
        self.assertIn("仅汇总未抵销", m_data.get("scope_notice", ""))
        self.assertAlmostEqual(float(m_1001["period_debit"]), 300.0, places=2)

    def test_02_subject_ledger_single_and_consolidation_modes(self):
        book_a = self._create_book("L1")
        book_b = self._create_book("L2")
        debit_code_a = self._post_voucher(book_a, f"L1{self.sid}", "88.00")
        debit_code_b = self._post_voucher(book_b, f"L2{self.sid}", "66.00")
        self.assertEqual(debit_code_a, debit_code_b)
        gid = self._create_consolidation_group(f"LG{self.sid}", f"ARCH05账组{self.sid}", [book_a, book_b])

        single = self.client.get(
            "/api/subject_ledger",
            query_string={
                "book_id": book_a,
                "subject_code": debit_code_a,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
            },
        )
        self.assertEqual(single.status_code, 200, single.get_data(as_text=True))
        s_data = single.get_json()
        self.assertEqual(s_data["query_mode"], "single_book")
        self.assertEqual(len(s_data["items"]), 1)

        merged = self.client.get(
            "/api/subject_ledger",
            query_string={
                "consolidation_group_id": gid,
                "subject_code": debit_code_a,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
            },
        )
        self.assertEqual(merged.status_code, 200, merged.get_data(as_text=True))
        m_data = merged.get_json()
        self.assertEqual(m_data["query_mode"], "consolidation_group")
        self.assertIn("仅汇总未抵销", m_data.get("scope_notice", ""))
        self.assertGreaterEqual(len(m_data["items"]), 2)


if __name__ == "__main__":
    unittest.main()
