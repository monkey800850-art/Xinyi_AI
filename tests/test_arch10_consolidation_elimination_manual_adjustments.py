import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch10ConsolidationEliminationManualAdjustmentsTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_adjustments (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        period VARCHAR(7) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'active',
                        operator_id BIGINT NOT NULL,
                        lines_json JSON NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
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
            "maker": "arch10",
            "status": "posted",
            "lines": [
                {"summary": "ARCH10借", "subject_code": debit_code, "debit": amount, "credit": "0.00"},
                {"summary": "ARCH10贷", "subject_code": credit_code, "debit": "0.00", "credit": amount},
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
                        '2025-01-01',
                        '2099-12-31',
                        'active',
                        1
                    )
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-ARCH10-{group_id}", "doc_name": "ARCH10 AUTH"},
            )

    def test_01_after_elim_applies_manual_adjustments(self):
        book_a = self._create_book("A10")
        book_b = self._create_book("B10")
        debit_a = self._post_voucher(book_a, f"A10-{self.sid}", "100.00")
        debit_b = self._post_voucher(book_b, f"B10-{self.sid}", "200.00")
        self.assertEqual(debit_a, debit_b)

        create_group_resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH10-{self.sid}", "group_name": f"ARCH10组{self.sid}", "group_type": "standard"},
        )
        self.assertEqual(create_group_resp.status_code, 201, create_group_resp.get_data(as_text=True))
        group_id = int(create_group_resp.get_json()["id"])
        self._grant_authorization(group_id)

        m1 = self.client.post(
            "/api/consolidation/members",
            json={
                "consolidation_group_id": group_id,
                "member_book_id": book_a,
                "member_type": "BOOK",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
                "operator_id": 1,
            },
        )
        self.assertEqual(m1.status_code, 201, m1.get_data(as_text=True))
        m2 = self.client.post(
            "/api/consolidation/members",
            json={
                "consolidation_group_id": group_id,
                "member_book_id": book_b,
                "member_type": "BOOK",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
                "operator_id": 1,
            },
        )
        self.assertEqual(m2.status_code, 201, m2.get_data(as_text=True))

        raw_resp = self.client.get(
            "/api/trial_balance",
            query_string={
                "consolidation_group_id": group_id,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
                "scope": "raw",
            },
        )
        self.assertEqual(raw_resp.status_code, 200, raw_resp.get_data(as_text=True))
        raw_data = raw_resp.get_json() or {}
        raw_line = next(x for x in raw_data.get("items") or [] if x.get("code") == debit_a)
        self.assertAlmostEqual(float(raw_line.get("period_debit") or 0.0), 300.0, places=2)
        self.assertIn("仅汇总未抵销", str(raw_data.get("scope_notice") or ""))

        create_adj_resp = self.client.post(
            "/api/consolidation/adjustments",
            json={
                "consolidation_group_id": group_id,
                "period": "2025-02",
                "operator_id": 1,
                "lines": [
                    {"subject_code": debit_a, "debit": "-50.00", "credit": "0.00", "note": "manual elim"},
                ],
            },
        )
        self.assertEqual(create_adj_resp.status_code, 201, create_adj_resp.get_data(as_text=True))

        list_adj_resp = self.client.get(
            "/api/consolidation/adjustments",
            query_string={"consolidation_group_id": group_id, "period": "2025-02"},
        )
        self.assertEqual(list_adj_resp.status_code, 200, list_adj_resp.get_data(as_text=True))
        self.assertGreaterEqual(len((list_adj_resp.get_json() or {}).get("items") or []), 1)

        after_resp = self.client.get(
            "/api/trial_balance",
            query_string={
                "consolidation_group_id": group_id,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
                "scope": "after_elim",
            },
        )
        self.assertEqual(after_resp.status_code, 200, after_resp.get_data(as_text=True))
        after_data = after_resp.get_json() or {}
        after_line = next(x for x in after_data.get("items") or [] if x.get("code") == debit_a)
        self.assertAlmostEqual(float(after_line.get("period_debit") or 0.0), 250.0, places=2)
        self.assertIn("汇总+抵销后", str(after_data.get("scope_notice") or ""))


if __name__ == "__main__":
    unittest.main()
