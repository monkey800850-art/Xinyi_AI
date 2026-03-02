import json
import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch22IcAssetTransferOnboardTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_ic_asset_transfer_events (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        as_of_date DATE NOT NULL,
                        asset_class VARCHAR(32) NOT NULL,
                        seller_book_id BIGINT NOT NULL,
                        buyer_book_id BIGINT NOT NULL,
                        asset_ref VARCHAR(128) NOT NULL,
                        transfer_price DECIMAL(18,2) NOT NULL DEFAULT 0,
                        carrying_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        tax_rate_snapshot DECIMAL(9,6) NOT NULL DEFAULT 0.25,
                        dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        original_gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        remaining_gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        original_dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        remaining_dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        note VARCHAR(255) NULL,
                        created_by BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_by BIGINT NOT NULL DEFAULT 0,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        UNIQUE KEY uq_ic_asset_transfer_identity (group_id, as_of_date, asset_class, seller_book_id, buyer_book_id, asset_ref)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS consolidation_parameters (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        virtual_subject_id INT NOT NULL,
                        parent_subject_type VARCHAR(32) NOT NULL,
                        parent_subject_id INT NOT NULL,
                        child_subject_type VARCHAR(32) NOT NULL,
                        child_subject_id INT NOT NULL,
                        ownership_ratio DECIMAL(9,6) NOT NULL DEFAULT 0,
                        control_type VARCHAR(32) NOT NULL DEFAULT 'control',
                        include_in_consolidation TINYINT NOT NULL DEFAULT 1,
                        effective_start DATE NOT NULL,
                        effective_end DATE NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        operator_id INT NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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

            def _has_col(table_name: str, col: str) -> bool:
                row = conn.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                          AND table_name=:table_name
                          AND column_name=:col
                        """
                    ),
                    {"table_name": table_name, "col": col},
                ).fetchone()
                return int(row.cnt or 0) > 0

            for col, ddl in [
                ("source", "ALTER TABLE consolidation_adjustments ADD COLUMN source VARCHAR(32) NULL"),
                ("rule_code", "ALTER TABLE consolidation_adjustments ADD COLUMN rule_code VARCHAR(64) NULL"),
                ("evidence_ref", "ALTER TABLE consolidation_adjustments ADD COLUMN evidence_ref VARCHAR(255) NULL"),
                ("batch_id", "ALTER TABLE consolidation_adjustments ADD COLUMN batch_id VARCHAR(64) NULL"),
                ("tag", "ALTER TABLE consolidation_adjustments ADD COLUMN tag VARCHAR(64) NULL"),
                ("reviewed_by", "ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_by BIGINT NULL"),
                ("reviewed_at", "ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_at DATETIME NULL"),
                ("locked_by", "ALTER TABLE consolidation_adjustments ADD COLUMN locked_by BIGINT NULL"),
                ("locked_at", "ALTER TABLE consolidation_adjustments ADD COLUMN locked_at DATETIME NULL"),
                ("note", "ALTER TABLE consolidation_adjustments ADD COLUMN note VARCHAR(255) NULL"),
            ]:
                if not _has_col("consolidation_adjustments", col):
                    conn.execute(text(ddl))
            if not _has_col("consolidation_parameters", "tax_rate"):
                conn.execute(text("ALTER TABLE consolidation_parameters ADD COLUMN tax_rate DECIMAL(9,6) NULL"))

    def _create_book(self, suffix: str) -> int:
        payload = make_book_payload(self.sid, suffix=suffix)
        resp = self.client.post("/books", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH22-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH22组{self.sid}"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["id"])

    def _grant(self, gid: int):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_authorizations WHERE virtual_subject_id=:gid"), {"gid": gid})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_authorizations (
                        virtual_subject_id, approval_document_number, approval_document_name,
                        effective_start, effective_end, status, operator_id
                    ) VALUES (:gid, :doc_no, :doc_name, '2020-01-01', '2099-12-31', 'active', 1)
                    """
                ),
                {"gid": gid, "doc_no": f"AUTH-{gid}", "doc_name": "ARCH22 AUTH"},
            )

    def _set_tax_rate(self, gid: int, tax_rate: str):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"), {"gid": gid})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                        virtual_subject_id, parent_subject_type, parent_subject_id,
                        child_subject_type, child_subject_id, ownership_ratio, control_type,
                        include_in_consolidation, effective_start, effective_end,
                        status, operator_id, tax_rate
                    ) VALUES (
                        :gid, 'LEGAL', 1, 'LEGAL', 2, 0.6, 'control',
                        1, '2025-01-01', '2099-12-31',
                        'active', 1, :tax_rate
                    )
                    """
                ),
                {"gid": gid, "tax_rate": tax_rate},
            )

    def _count_audit(self, gid: int) -> int:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_audit_log
                    WHERE group_id=:gid AND action='ic_asset_transfer_generate'
                    """
                ),
                {"gid": gid},
            ).fetchone()
        return int(row.c or 0)

    def test_01_ic_asset_transfer_onboard(self):
        seller = self._create_book("A22")
        buyer = self._create_book("B22")
        gid = self._create_group()
        self._set_tax_rate(gid, "0.20")

        payload = {
            "group_id": gid,
            "as_of": "2025-03-31",
            "asset_class": "FA",
            "seller_book_id": seller,
            "buyer_book_id": buyer,
            "asset_ref": "FA-0001",
            "transfer_price": "120.00",
            "carrying_amount": "100.00",
            "note": "arch22",
            "operator_id": 1,
        }

        unauth = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))

        self._grant(gid)
        before = self._count_audit(gid)
        ok = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(ok.status_code, 200, ok.get_data(as_text=True))
        body = ok.get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertAlmostEqual(float(body.get("gain_loss_amount") or 0), 20.0, places=2)
        self.assertAlmostEqual(float(body.get("dtl_amount") or 0), 4.0, places=2)
        self.assertAlmostEqual(float(body.get("tax_rate") or 0), 0.2, places=4)
        set_id = str(body.get("adjustment_set_id") or "")
        self.assertTrue(set_id)
        self.assertIn(f"ICAST-{gid}-20250331-FA-{seller}-{buyer}-FA-0001", set_id)
        self.assertGreaterEqual(int((body.get("counts") or {}).get("lines") or 0), 4)

        lines = body.get("preview_lines") or []
        self.assertGreaterEqual(len(lines), 4)
        debit_sum = sum(float(x.get("debit") or 0) for x in lines)
        credit_sum = sum(float(x.get("credit") or 0) for x in lines)
        self.assertAlmostEqual(debit_sum, credit_sum, places=2)

        with self.engine.connect() as conn:
            event_row = conn.execute(
                text(
                    """
                    SELECT gain_loss_amount, dtl_amount, tax_rate_snapshot,
                           original_gain_loss_amount, remaining_gain_loss_amount,
                           original_dtl_amount, remaining_dtl_amount,
                           created_by, updated_by, note, created_at
                    FROM consolidation_ic_asset_transfer_events
                    WHERE group_id=:gid AND as_of_date='2025-03-31'
                      AND asset_class='FA' AND seller_book_id=:seller AND buyer_book_id=:buyer
                      AND asset_ref='FA-0001'
                    LIMIT 1
                    """
                ),
                {"gid": gid, "seller": seller, "buyer": buyer},
            ).fetchone()
            adj_row = conn.execute(
                text(
                    """
                    SELECT status, source, rule_code, evidence_ref, batch_id, lines_json
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND batch_id=:set_id
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"gid": gid, "set_id": set_id},
            ).fetchone()
            cnt_row = conn.execute(
                text(
                    """
                    SELECT COUNT(1) AS c
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND batch_id=:set_id
                    """
                ),
                {"gid": gid, "set_id": set_id},
            ).fetchone()

        self.assertIsNotNone(event_row)
        self.assertAlmostEqual(float(event_row.gain_loss_amount or 0), 20.0, places=2)
        self.assertAlmostEqual(float(event_row.dtl_amount or 0), 4.0, places=2)
        self.assertAlmostEqual(float(event_row.tax_rate_snapshot or 0), 0.2, places=4)
        self.assertAlmostEqual(float(event_row.original_gain_loss_amount or 0), 20.0, places=2)
        self.assertAlmostEqual(float(event_row.remaining_gain_loss_amount or 0), 20.0, places=2)
        self.assertAlmostEqual(float(event_row.original_dtl_amount or 0), 4.0, places=2)
        self.assertAlmostEqual(float(event_row.remaining_dtl_amount or 0), 4.0, places=2)
        self.assertEqual(int(event_row.created_by or 0), 1)
        self.assertEqual(int(event_row.updated_by or 0), 1)
        self.assertEqual(str(event_row.note or ""), "arch22")
        self.assertTrue(str(event_row.created_at or ""))

        self.assertEqual(int(cnt_row.c or 0), 1)
        self.assertEqual(str(adj_row.status or ""), "draft")
        self.assertEqual(str(adj_row.source or ""), "generated")
        self.assertEqual(str(adj_row.rule_code or ""), "IC_ASSET_TRANSFER_ONBOARD")
        self.assertEqual(str(adj_row.evidence_ref or ""), set_id)
        self.assertEqual(str(adj_row.batch_id or ""), set_id)
        self.assertGreaterEqual(len(json.loads(str(adj_row.lines_json or "[]"))), 4)

        rerun = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(rerun.status_code, 200, rerun.get_data(as_text=True))
        body2 = rerun.get_json() or {}
        self.assertTrue(bool(body2.get("reused_existing_set")))
        self.assertEqual(str(body2.get("adjustment_set_id") or ""), set_id)

        review = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))

        blocked_reviewed = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(blocked_reviewed.status_code, 409, blocked_reviewed.get_data(as_text=True))

        reopen = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/reopen", json={"operator_id": 1})
        self.assertEqual(reopen.status_code, 200, reopen.get_data(as_text=True))
        rerun2 = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(rerun2.status_code, 200, rerun2.get_data(as_text=True))

        review2 = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review2.status_code, 200, review2.get_data(as_text=True))
        lock = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/lock", json={"operator_id": 1})
        self.assertEqual(lock.status_code, 200, lock.get_data(as_text=True))

        blocked_locked = self.client.post("/api/consolidation/eliminations/ic_asset_transfer/generate", json=payload)
        self.assertEqual(blocked_locked.status_code, 409, blocked_locked.get_data(as_text=True))

        after = self._count_audit(gid)
        self.assertGreaterEqual(after - before, 5)


if __name__ == "__main__":
    unittest.main()
