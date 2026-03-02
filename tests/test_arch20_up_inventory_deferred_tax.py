import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch20UpInventoryDeferredTaxTest(unittest.TestCase):
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
                    CREATE TABLE IF NOT EXISTS consolidation_ic_inventory_txn (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        group_id BIGINT NOT NULL,
                        seller_book_id BIGINT NOT NULL,
                        buyer_book_id BIGINT NOT NULL,
                        doc_no VARCHAR(64) NOT NULL,
                        txn_date DATE NOT NULL,
                        item_code VARCHAR(64) NOT NULL,
                        qty DECIMAL(18,6) NOT NULL DEFAULT 0,
                        sales_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        cost_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                        ending_inventory_qty DECIMAL(18,6) NOT NULL DEFAULT 0,
                        note VARCHAR(255) NULL,
                        created_by BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
            json={"group_code": f"ARCH20-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH20组{self.sid}"},
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
                {"gid": group_id, "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH20 AUTH"},
            )

    def _insert_ic_txn_and_tax_rate(self, group_id: int, seller: int, buyer: int):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_ic_inventory_txn (
                        group_id, seller_book_id, buyer_book_id, doc_no, txn_date, item_code,
                        qty, sales_amount, cost_amount, ending_inventory_qty, note, created_by
                    ) VALUES (
                        :group_id, :seller, :buyer, 'DOC-ARCH20', '2025-03-20', 'ITEM-20',
                        10, 100, 80, 4, 'arch20', 1
                    )
                    """
                ),
                {"group_id": group_id, "seller": seller, "buyer": buyer},
            )
            conn.execute(text("DELETE FROM consolidation_parameters WHERE virtual_subject_id=:gid"), {"gid": group_id})
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_parameters (
                        virtual_subject_id, parent_subject_type, parent_subject_id,
                        child_subject_type, child_subject_id, ownership_ratio, control_type,
                        include_in_consolidation, effective_start, effective_end,
                        status, operator_id, tax_rate
                    ) VALUES (
                        :gid, 'LEGAL', 1,
                        'LEGAL', 2, 0.6, 'control',
                        1, '2025-01-01', '2099-12-31',
                        'active', 1, 0.20
                    )
                    """
                ),
                {"gid": group_id},
            )

    def test_01_up_inventory_deferred_tax(self):
        seller = self._create_book("A20")
        buyer = self._create_book("B20")
        gid = self._create_group()
        self._insert_ic_txn_and_tax_rate(gid, seller, buyer)

        payload = {
            "group_id": gid,
            "start_date": "2025-03-01",
            "end_date": "2025-03-31",
            "operator_id": 1,
        }

        unauth = self.client.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate", json=payload)
        self.assertEqual(unauth.status_code, 403, unauth.get_data(as_text=True))

        self._grant(gid)
        ok = self.client.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate", json=payload)
        self.assertEqual(ok.status_code, 200, ok.get_data(as_text=True))
        body = ok.get_json() or {}
        self.assertAlmostEqual(float(body.get("total_unrealized_profit") or 0), 8.0, places=2)
        self.assertAlmostEqual(float(body.get("tax_rate") or 0), 0.2, places=4)
        self.assertAlmostEqual(float(body.get("dt_amount") or 0), 1.6, places=2)

        set_id = str(body.get("adjustment_set_id") or "")
        self.assertTrue(set_id)
        lines = body.get("preview_lines") or []
        dt_lines = [x for x in lines if str(x.get("rule") or "") == "UP_INV_DT"]
        self.assertEqual(len(dt_lines), 2)
        dt_debit = sum(float(x.get("debit") or 0) for x in dt_lines)
        dt_credit = sum(float(x.get("credit") or 0) for x in dt_lines)
        self.assertAlmostEqual(dt_debit, 1.6, places=2)
        self.assertAlmostEqual(dt_credit, 1.6, places=2)

        rerun = self.client.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate", json=payload)
        self.assertEqual(rerun.status_code, 200, rerun.get_data(as_text=True))
        body2 = rerun.get_json() or {}
        self.assertTrue(bool(body2.get("reused_existing_set")))
        self.assertEqual(str(body2.get("adjustment_set_id") or ""), set_id)

        review = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))

        blocked_reviewed = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/generate",
            json=payload,
        )
        self.assertEqual(blocked_reviewed.status_code, 409, blocked_reviewed.get_data(as_text=True))

        reopen = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/reopen", json={"operator_id": 1})
        self.assertEqual(reopen.status_code, 200, reopen.get_data(as_text=True))
        ok2 = self.client.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate", json=payload)
        self.assertEqual(ok2.status_code, 200, ok2.get_data(as_text=True))

        review2 = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review2.status_code, 200, review2.get_data(as_text=True))
        lock = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/lock", json={"operator_id": 1})
        self.assertEqual(lock.status_code, 200, lock.get_data(as_text=True))

        blocked_locked = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/generate",
            json=payload,
        )
        self.assertEqual(blocked_locked.status_code, 409, blocked_locked.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
