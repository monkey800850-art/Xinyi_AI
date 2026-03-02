import json
import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Arch18PurchaseMethodGenerateTest(unittest.TestCase):
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
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_acquisition_events (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        acquiree_book_id BIGINT NOT NULL DEFAULT 0,
                        acquiree_entity_id BIGINT NOT NULL DEFAULT 0,
                        acquisition_date DATE NOT NULL,
                        consideration_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        acquired_pct DECIMAL(9,6) NOT NULL DEFAULT 0,
                        fv_net_assets DECIMAL(18,2) NOT NULL DEFAULT 0,
                        fv_adjustments_json JSON NULL,
                        deferred_tax_json JSON NULL,
                        notes VARCHAR(255) NULL,
                        created_by BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_by BIGINT NOT NULL DEFAULT 0,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_conso_acq_event_identity (group_id, acquisition_date, acquiree_book_id, acquiree_entity_id)
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
            if not _has_column("reviewed_by"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_by BIGINT NULL"))
            if not _has_column("reviewed_at"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_at DATETIME NULL"))
            if not _has_column("locked_by"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN locked_by BIGINT NULL"))
            if not _has_column("locked_at"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN locked_at DATETIME NULL"))
            if not _has_column("note"):
                conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN note VARCHAR(255) NULL"))

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH18-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH18组{self.sid}"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, group_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"), {"gid": group_id})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (:gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1)
                    """
                ),
                {"gid": group_id, "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH18 AUTH"},
            )

    def _count_audit(self, group_id: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid
                      AND action='purchase_method_generate'
                    """
                ),
                {"gid": group_id},
            ).fetchone()
        return int(row.c or 0)

    def test_01_purchase_method_generate_workflow(self):
        gid = self._create_group()
        payload = {
            "consolidation_group_id": gid,
            "acquiree_entity_id": 3001,
            "acquisition_date": "2025-03-31",
            "consideration_amount": "120.00",
            "acquired_pct": "0.6",
            "fv_net_assets": "150.00",
            "fv_adjustments_json": {"inventory_stepup": 10},
            "deferred_tax_json": {"dtl": 2},
            "notes": "arch18",
            "operator_id": 1,
        }

        unauth = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))

        self._grant(gid)
        before = self._count_audit(gid)
        first = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        first_body = first.get_json() or {}
        self.assertTrue(first_body.get("ok"))
        set_id = str(first_body.get("adjustment_set_id") or "")
        self.assertTrue(set_id)
        self.assertGreaterEqual(int((first_body.get("counts") or {}).get("lines") or 0), 4)
        self.assertTrue(isinstance(first_body.get("preview_lines"), list))

        second = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_body = second.get_json() or {}
        self.assertEqual(str(second_body.get("adjustment_set_id") or ""), set_id)
        self.assertTrue(bool(second_body.get("reused_existing_set")))

        with self.engine.connect() as conn:
            adj = conn.execute(
                text(
                    """
                    SELECT id, status, source, rule_code, evidence_ref, batch_id, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND batch_id=:batch_id
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"gid": gid, "batch_id": set_id},
            ).fetchone()
            cnt = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND batch_id=:batch_id
                    """
                ),
                {"gid": gid, "batch_id": set_id},
            ).fetchone()
            evt = conn.execute(
                text(
                    """
                    SELECT created_by, updated_by, notes, created_at, updated_at
                    FROM consolidation_acquisition_events
                    WHERE group_id=:gid AND acquisition_date='2025-03-31' AND acquiree_entity_id=3001
                    LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
        self.assertEqual(int(cnt.c or 0), 1)
        self.assertEqual(str(adj.status or ""), "draft")
        self.assertEqual(str(adj.source or ""), "generated")
        self.assertEqual(str(adj.rule_code or ""), "PPA_PURCHASE_METHOD")
        self.assertEqual(str(adj.evidence_ref or ""), set_id)
        self.assertEqual(str(adj.batch_id or ""), set_id)
        lines = json.loads(str(adj.lines_json or "[]"))
        self.assertTrue(len(lines) >= 4)
        line_map = {str(line.get("subject_code") or ""): line for line in lines}
        self.assertIn("PPA_DEFERRED_TAX_LIABILITY", line_map)
        self.assertEqual(str(line_map["PPA_DEFERRED_TAX_LIABILITY"].get("credit") or ""), "2.00")
        self.assertIn("PPA_BARGAIN_GAIN", line_map)
        self.assertEqual(str(line_map["PPA_BARGAIN_GAIN"].get("credit") or ""), "28.00")
        self.assertEqual(int(evt.created_by or 0), 1)
        self.assertEqual(int(evt.updated_by or 0), 1)
        self.assertEqual(str(evt.notes or ""), "arch18")
        self.assertTrue(str(evt.created_at or ""))
        self.assertTrue(str(evt.updated_at or ""))

        review = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        blocked_reviewed = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(blocked_reviewed.status_code, 409, blocked_reviewed.get_data(as_text=True))

        reopen = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/reopen", json={"operator_id": 1})
        self.assertEqual(reopen.status_code, 200, reopen.get_data(as_text=True))
        rerun = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(rerun.status_code, 200, rerun.get_data(as_text=True))

        review2 = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review2.status_code, 200, review2.get_data(as_text=True))
        lock = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/lock", json={"operator_id": 1})
        self.assertEqual(lock.status_code, 200, lock.get_data(as_text=True))
        blocked_locked = self.client.post("/api/consolidation/purchase_method/generate", json=payload)
        self.assertEqual(blocked_locked.status_code, 409, blocked_locked.get_data(as_text=True))

        after = self._count_audit(gid)
        self.assertGreaterEqual(after - before, 5)


if __name__ == "__main__":
    unittest.main()
