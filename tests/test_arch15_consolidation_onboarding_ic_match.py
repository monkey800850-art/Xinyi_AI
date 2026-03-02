import json
import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch15ConsolidationOnboardingIcMatchTest(unittest.TestCase):
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
                        operator_id BIGINT NOT NULL DEFAULT 0
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

            def _has_column(name: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name='consolidation_adjustments'
                          AND column_name=:name
                        """
                    ),
                    {"name": name},
                ).fetchone()
                return int(row.cnt or 0) > 0

            if not _has_column("source"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN source VARCHAR(32) NULL"))
            if not _has_column("rule_code"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN rule_code VARCHAR(64) NULL"))
            if not _has_column("evidence_ref"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN evidence_ref VARCHAR(255) NULL"))
            if not _has_column("batch_id"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN batch_id VARCHAR(64) NULL"))
            if not _has_column("tag"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN tag VARCHAR(64) NULL"))

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
                      AND NOT EXISTS (
                        SELECT 1 FROM subjects c
                        WHERE c.book_id=s.book_id
                          AND TRIM(TRAILING '.' FROM COALESCE(c.parent_code,''))=s.code
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

    def _post_voucher(self, book_id: int, voucher_no: str, interco_code: str, other_code: str, debit: str, credit: str):
        payload = {
            "book_id": book_id,
            "voucher_date": "2025-03-10",
            "voucher_word": "记",
            "voucher_no": voucher_no,
            "attachments": 0,
            "maker": "arch15",
            "status": "posted",
            "lines": [
                {
                    "summary": "内部往来",
                    "subject_code": interco_code,
                    "debit": debit,
                    "credit": credit,
                    "aux_type": "entity",
                    "aux_code": "IC-001",
                    "aux_name": "内部往来单位",
                    "aux_display": "IC-001 内部往来单位",
                },
                {
                    "summary": "对冲",
                    "subject_code": other_code,
                    "debit": credit,
                    "credit": debit,
                    "aux_type": "entity",
                    "aux_code": "IC-001",
                    "aux_name": "内部往来单位",
                    "aux_display": "IC-001 内部往来单位",
                },
            ],
        }
        resp = self.client.post("/api/vouchers", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))

    def _grant(self, group_id: int):
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
                    ) VALUES (:gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1)
                    """
                ),
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH15 AUTH"},
            )

    def test_01_ic_match_generates_draft(self):
        b1 = self._create_book("A15")
        b2 = self._create_book("B15")
        i1, o1 = self._pick_leaf_subject_codes(b1)
        i2, o2 = self._pick_leaf_subject_codes(b2)
        self.assertEqual(i1, i2)
        interco_code = i1

        self._post_voucher(b1, f"A15-{self.sid}", interco_code, o1, "100.00", "0.00")
        self._post_voucher(b2, f"B15-{self.sid}", interco_code, o2, "0.00", "100.00")

        group_resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH15-{self.sid}", "group_name": f"ARCH15组{self.sid}", "group_type": "standard"},
        )
        self.assertEqual(group_resp.status_code, 201, group_resp.get_data(as_text=True))
        gid = int(group_resp.get_json()["id"])

        for bid in (b1, b2):
            add_member = self.client.post(
                "/api/consolidation/members",
                json={
                    "consolidation_group_id": gid,
                    "member_book_id": bid,
                    "member_type": "BOOK",
                    "effective_from": "2025-01-01",
                    "effective_to": "2025-12-31",
                    "operator_id": 1,
                },
            )
            self.assertEqual(add_member.status_code, 403, add_member.get_data(as_text=True))

        unauth = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31"},
        )
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))

        self._grant(gid)
        for bid in (b1, b2):
            add_member = self.client.post(
                "/api/consolidation/members",
                json={
                    "consolidation_group_id": gid,
                    "member_book_id": bid,
                    "member_type": "BOOK",
                    "effective_from": "2025-01-01",
                    "effective_to": "2025-12-31",
                    "operator_id": 1,
                },
            )
            self.assertEqual(add_member.status_code, 201, add_member.get_data(as_text=True))

        resp = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31", "operator_id": 1},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("set_id"))
        self.assertGreaterEqual(int((body.get("stats") or {}).get("matched") or 0), 1)
        self.assertEqual(int((body.get("stats") or {}).get("unmatched") or 0), 0)
        self.assertEqual(body.get("unmatched"), [])

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT status, source, tag, rule_code, batch_id, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid
                      AND period='2025-03'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(str(row.status or ""), "draft")
        self.assertEqual(str(row.source or ""), "generated")
        self.assertEqual(str(row.tag or ""), "onboarding_ic")
        self.assertEqual(str(row.rule_code or ""), "IC_MATCH")
        self.assertEqual(str(row.batch_id or ""), str(body.get("set_id") or ""))
        lines = json.loads(str(row.lines_json or "[]"))
        self.assertGreaterEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
