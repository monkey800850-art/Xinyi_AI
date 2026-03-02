import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine
from tests._helpers.book_factory import make_book_payload


class Arch21UpInventoryReversalTest(unittest.TestCase):
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
                ("original_unrealized_profit", "ALTER TABLE consolidation_adjustments ADD COLUMN original_unrealized_profit DECIMAL(18,2) NULL"),
                ("remaining_unrealized_profit", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_unrealized_profit DECIMAL(18,2) NULL"),
                ("period_start", "ALTER TABLE consolidation_adjustments ADD COLUMN period_start DATE NULL"),
                ("period_end", "ALTER TABLE consolidation_adjustments ADD COLUMN period_end DATE NULL"),
                ("original_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN original_amount DECIMAL(18,2) NULL"),
                ("remaining_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_amount DECIMAL(18,2) NULL"),
                ("origin_period_start", "ALTER TABLE consolidation_adjustments ADD COLUMN origin_period_start DATE NULL"),
                ("origin_period_end", "ALTER TABLE consolidation_adjustments ADD COLUMN origin_period_end DATE NULL"),
                ("original_tax_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN original_tax_amount DECIMAL(18,2) NULL"),
                ("remaining_tax_amount", "ALTER TABLE consolidation_adjustments ADD COLUMN remaining_tax_amount DECIMAL(18,2) NULL"),
                ("tax_rate_snapshot", "ALTER TABLE consolidation_adjustments ADD COLUMN tax_rate_snapshot DECIMAL(9,6) NULL"),
            ]:
                if not _has_col("consolidation_adjustments", col):
                    conn.execute(text(ddl))

    def _create_book(self, suffix: str) -> int:
        payload = make_book_payload(self.sid, suffix=suffix)
        resp = self.client.post("/books", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _create_group(self) -> int:
        resp = self.client.post(
            "/api/consolidation/groups",
            json={"group_code": f"ARCH21-{self.sid}-{self._testMethodName[-2:]}", "group_name": f"ARCH21组{self.sid}"},
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
                {"gid": group_id, "doc_no": f"AUTH-{group_id}", "doc_name": "ARCH21 AUTH"},
            )

    def _insert_ic_txn(self, group_id: int, seller: int, buyer: int, txn_date: str, ending_qty: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO consolidation_ic_inventory_txn (
                        group_id, seller_book_id, buyer_book_id, doc_no, txn_date, item_code,
                        qty, sales_amount, cost_amount, ending_inventory_qty, note, created_by
                    ) VALUES (
                        :group_id, :seller, :buyer, 'DOC-ARCH21', :txn_date, 'ITEM-21',
                        10, 100, 80, :ending_qty, 'arch21', 1
                    )
                    """
                ),
                {"group_id": group_id, "seller": seller, "buyer": buyer, "txn_date": txn_date, "ending_qty": ending_qty},
            )

    def test_01_up_inventory_reversal(self):
        seller = self._create_book("A21")
        buyer = self._create_book("B21")
        gid = self._create_group()
        self._grant(gid)

        self._insert_ic_txn(gid, seller, buyer, "2025-03-15", "4")
        base_payload = {"group_id": gid, "start_date": "2025-03-01", "end_date": "2025-03-31", "operator_id": 1}
        gen = self.client.post("/api/consolidation/eliminations/unrealized_profit/inventory/generate", json=base_payload)
        self.assertEqual(gen.status_code, 200, gen.get_data(as_text=True))

        with self.engine.connect() as conn:
            row_before = conn.execute(
                text(
                    """
                    SELECT id, remaining_unrealized_profit, remaining_tax_amount
                    FROM consolidation_adjustments
                    WHERE group_id=:gid AND rule_code='UP_INV'
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"gid": gid},
            ).fetchone()
        self.assertAlmostEqual(float(row_before.remaining_unrealized_profit or 0), 8.0, places=2)
        self.assertAlmostEqual(float(row_before.remaining_tax_amount or 0), 2.0, places=2)

        self._insert_ic_txn(gid, seller, buyer, "2025-04-10", "8")
        rev_payload = {"group_id": gid, "start_date": "2025-04-01", "end_date": "2025-04-30", "operator_id": 1}

        rev = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/reversal/generate",
            json=rev_payload,
        )
        self.assertEqual(rev.status_code, 200, rev.get_data(as_text=True))
        body = rev.get_json() or {}
        self.assertTrue(body.get("ok"))
        self.assertAlmostEqual(float(body.get("reversal_amount") or 0), 4.0, places=2)
        self.assertAlmostEqual(float(body.get("dt_reversal_amount") or 0), 1.0, places=2)
        set_id = str(body.get("adjustment_set_id") or "")
        self.assertTrue(set_id)
        dt_lines = [x for x in (body.get("preview_lines") or []) if str(x.get("rule") or "") == "UP_INV_DTL_REVERSAL"]
        self.assertEqual(len(dt_lines), 2)
        dt_debit = sum(float(x.get("debit") or 0) for x in dt_lines)
        dt_credit = sum(float(x.get("credit") or 0) for x in dt_lines)
        self.assertAlmostEqual(dt_debit, 1.0, places=2)
        self.assertAlmostEqual(dt_credit, 1.0, places=2)

        with self.engine.connect() as conn:
            row_after = conn.execute(
                text(
                    """
                    SELECT remaining_unrealized_profit, remaining_tax_amount
                    FROM consolidation_adjustments
                    WHERE id=:id
                    """
                ),
                {"id": int(row_before.id)},
            ).fetchone()
        self.assertAlmostEqual(float(row_after.remaining_unrealized_profit or 0), 4.0, places=2)
        self.assertAlmostEqual(float(row_after.remaining_tax_amount or 0), 1.0, places=2)

        rerun = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/reversal/generate",
            json=rev_payload,
        )
        self.assertEqual(rerun.status_code, 200, rerun.get_data(as_text=True))
        body2 = rerun.get_json() or {}
        self.assertTrue(bool(body2.get("reused_existing_set")))
        self.assertEqual(str(body2.get("adjustment_set_id") or ""), set_id)

        review = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/review", json={"operator_id": 1})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))

        blocked_reviewed = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/reversal/generate",
            json=rev_payload,
        )
        self.assertEqual(blocked_reviewed.status_code, 409, blocked_reviewed.get_data(as_text=True))

        lock = self.client.post(f"/api/consolidation/adjustment_sets/{set_id}/lock", json={"operator_id": 1})
        self.assertEqual(lock.status_code, 200, lock.get_data(as_text=True))

        blocked_locked = self.client.post(
            "/api/consolidation/eliminations/unrealized_profit/inventory/reversal/generate",
            json=rev_payload,
        )
        self.assertEqual(blocked_locked.status_code, 409, blocked_locked.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
