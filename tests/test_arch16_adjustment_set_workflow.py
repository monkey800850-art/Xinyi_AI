import json
import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch16AdjustmentSetWorkflowTest(unittest.TestCase):
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
            "maker": "arch16",
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
                {"gid": int(group_id), "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH16 AUTH"},
            )

    def _revoke(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"),
                {"gid": int(group_id)},
            )

    def _append_manual_line(self, group_id: int, set_id: str):
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid
                      AND batch_id=:set_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": int(group_id), "set_id": str(set_id)},
            ).fetchone()
            lines = json.loads(str(row.lines_json or "[]"))
            lines.append(
                {
                    "subject_code": "9999",
                    "debit": "1",
                    "credit": "1",
                    "note": "manual",
                    "set_id": str(set_id),
                    "source": "manual",
                    "rule": "MANUAL",
                    "evidence_ref": "manual",
                    "operator_id": "1",
                }
            )
            conn.execute(
                text("UPDATE consolidation_adjustments SET lines_json=:lines_json WHERE id=:id"),
                {"id": int(row.id), "lines_json": json.dumps(lines, ensure_ascii=False)},
            )

    def _count_transition_audit(self, group_id: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid
                      AND action IN ('adjustment_set_review', 'adjustment_set_lock', 'adjustment_set_reopen')
                    """
                ),
                {"gid": int(group_id)},
            ).fetchone()
        return int(row.c or 0)

    def test_01_adjustment_set_workflow_and_regeneration(self):
        b1 = self._create_book("A16")
        b2 = self._create_book("B16")
        i1, o1 = self._pick_leaf_subject_codes(b1)
        i2, o2 = self._pick_leaf_subject_codes(b2)
        self.assertEqual(i1, i2)
        interco_code = i1

        self._post_voucher(b1, f"A16-{self.sid}", interco_code, o1, "100.00", "0.00")
        self._post_voucher(b2, f"B16-{self.sid}", interco_code, o2, "0.00", "100.00")

        group_resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH16-{self.sid}", "group_name": f"ARCH16组{self.sid}", "group_type": "standard"},
        )
        self.assertEqual(group_resp.status_code, 201, group_resp.get_data(as_text=True))
        gid = int(group_resp.get_json()["id"])
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

        first = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31", "operator_id": 1},
        )
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        first_body = first.get_json() or {}
        set_id = str(first_body.get("adjustment_set_id") or "")
        self.assertTrue(set_id)

        sets_resp = self.client.get(
            "/api/consolidation/adjustment_sets",
            query_string={"consolidation_group_id": gid, "as_of": "2025-03-31"},
        )
        self.assertEqual(sets_resp.status_code, 200, sets_resp.get_data(as_text=True))
        set_items = (sets_resp.get_json() or {}).get("items") or []
        this_set = next((x for x in set_items if str(x.get("set_id") or "") == set_id), None)
        self.assertIsNotNone(this_set)
        self.assertEqual(str(this_set.get("status") or ""), "draft")

        self._revoke(gid)
        forbidden_review = self.client.post(
            f"/api/consolidation/adjustment_sets/{set_id}/review",
            json={"operator_id": 1},
        )
        self.assertEqual(forbidden_review.status_code, 403, forbidden_review.get_data(as_text=True))
        self._grant(gid)

        review = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        self.assertEqual(str(((review.get_json() or {}).get("item") or {}).get("status") or ""), "reviewed")

        blocked_reviewed = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31", "operator_id": 1},
        )
        self.assertEqual(blocked_reviewed.status_code, 409, blocked_reviewed.get_data(as_text=True))

        reopen = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/reopen", json={"operator_id": 1})
        self.assertEqual(reopen.status_code, 200, reopen.get_data(as_text=True))
        self.assertEqual(str(((reopen.get_json() or {}).get("item") or {}).get("status") or ""), "draft")

        self._append_manual_line(gid, set_id)
        self._post_voucher(b1, f"A16-{self.sid}-2", interco_code, o1, "20.00", "0.00")
        self._post_voucher(b2, f"B16-{self.sid}-2", interco_code, o2, "0.00", "20.00")

        rerun = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31", "operator_id": 1},
        )
        self.assertEqual(rerun.status_code, 200, rerun.get_data(as_text=True))
        rerun_body = rerun.get_json() or {}
        self.assertTrue(bool(rerun_body.get("reused_existing_set")))

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT status, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid
                      AND batch_id=:set_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"gid": gid, "set_id": set_id},
            ).fetchone()
        self.assertEqual(str(row.status or ""), "draft")
        lines = json.loads(str(row.lines_json or "[]"))
        generated = [
            x
            for x in lines
            if isinstance(x, dict)
            and str(x.get("source") or "") == "generated"
            and str(x.get("rule") or "") == "ONBOARD_IC"
        ]
        manual = [x for x in lines if isinstance(x, dict) and str(x.get("source") or "") == "manual"]
        self.assertGreaterEqual(len(generated), 2)
        self.assertEqual(len(manual), 1)

        review2 = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review2.status_code, 200, review2.get_data(as_text=True))
        lock_resp = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/lock", json={"operator_id": 1})
        self.assertEqual(lock_resp.status_code, 200, lock_resp.get_data(as_text=True))
        self.assertEqual(str(((lock_resp.get_json() or {}).get("item") or {}).get("status") or ""), "locked")

        blocked_locked = self.client.post(
            "/api/consolidation/onboarding/ic_match",
            json={"consolidation_group_id": gid, "as_of": "2025-03-31", "operator_id": 1},
        )
        self.assertEqual(blocked_locked.status_code, 409, blocked_locked.get_data(as_text=True))

        self.assertGreaterEqual(self._count_transition_audit(gid), 4)


if __name__ == "__main__":
    unittest.main()
