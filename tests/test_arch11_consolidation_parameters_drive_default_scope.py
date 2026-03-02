import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch11ConsolidationParametersDriveDefaultScopeTest(unittest.TestCase):
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
            def _has_column(column_name: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name = 'consolidation_parameters'
                          AND column_name = :column_name
                        """
                    ),
                    {"column_name": column_name},
                ).fetchone()
                return int(row.cnt or 0) > 0

            if not _has_column("consolidation_method"):
                conn.execute(
                    text(
                        "ALTER TABLE consolidation_parameters ADD COLUMN consolidation_method VARCHAR(16) NOT NULL DEFAULT 'full'"
                    )
                )
            if not _has_column("default_scope"):
                conn.execute(
                    text(
                        "ALTER TABLE consolidation_parameters ADD COLUMN default_scope VARCHAR(16) NOT NULL DEFAULT 'raw'"
                    )
                )
            if not _has_column("effective_from"):
                conn.execute(
                    text("ALTER TABLE consolidation_parameters ADD COLUMN effective_from DATE NULL")
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
            "maker": "arch11",
            "status": "posted",
            "lines": [
                {"summary": "ARCH11借", "subject_code": debit_code, "debit": amount, "credit": "0.00"},
                {"summary": "ARCH11贷", "subject_code": credit_code, "debit": "0.00", "credit": amount},
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
                        '2020-01-01',
                        '2099-12-31',
                        'active',
                        1
                    )
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-ARCH11-{group_id}", "doc_name": "ARCH11 AUTH"},
            )

    def test_01_parameters_default_scope_drives_trial_balance(self):
        book_a = self._create_book("A11")
        book_b = self._create_book("B11")
        debit_a = self._post_voucher(book_a, f"A11-{self.sid}", "100.00")
        debit_b = self._post_voucher(book_b, f"B11-{self.sid}", "200.00")
        self.assertEqual(debit_a, debit_b)

        create_group_resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH11-{self.sid}", "group_name": f"ARCH11组{self.sid}", "group_type": "standard"},
        )
        self.assertEqual(create_group_resp.status_code, 201, create_group_resp.get_data(as_text=True))
        group_id = int(create_group_resp.get_json()["id"])
        self._grant_authorization(group_id)

        for bid in (book_a, book_b):
            m_resp = self.client.post(
                "/api/consolidation/members",
                json={
                    "consolidation_group_id": group_id,
                    "member_book_id": bid,
                    "member_type": "BOOK",
                    "effective_from": "2025-01-01",
                    "effective_to": "2025-12-31",
                    "operator_id": 1,
                },
            )
            self.assertEqual(m_resp.status_code, 201, m_resp.get_data(as_text=True))

        adj_resp = self.client.post(
            "/api/consolidation/adjustments",
            json={
                "consolidation_group_id": group_id,
                "period": "2025-02",
                "operator_id": 1,
                "lines": [{"subject_code": debit_a, "debit": "-50.00", "credit": "0.00"}],
            },
        )
        self.assertEqual(adj_resp.status_code, 201, adj_resp.get_data(as_text=True))

        put_resp = self.client.put(
            "/api/consolidation/parameters",
            json={
                "consolidation_group_id": group_id,
                "start_period": "2025-01",
                "note": "arch11",
                "consolidation_method": "proportion",
                "default_scope": "after_elim",
                "effective_from": "2025-01",
                "operator_id": 1,
            },
        )
        self.assertEqual(put_resp.status_code, 200, put_resp.get_data(as_text=True))

        tb_resp = self.client.get(
            "/api/trial_balance",
            query_string={
                "consolidation_group_id": group_id,
                "start_date": "2025-02-01",
                "end_date": "2025-02-28",
            },
        )
        self.assertEqual(tb_resp.status_code, 200, tb_resp.get_data(as_text=True))
        data = tb_resp.get_json() or {}
        line = next(x for x in data.get("items") or [] if x.get("code") == debit_a)
        self.assertAlmostEqual(float(line.get("period_debit") or 0.0), 250.0, places=2)
        notice = str(data.get("scope_notice") or "")
        self.assertIn("method=proportion", notice)
        self.assertIn("default_scope=after_elim", notice)


if __name__ == "__main__":
    unittest.main()
