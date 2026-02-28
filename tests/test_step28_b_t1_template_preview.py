import os
import runpy
import sys
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Step28B1T1TemplatePreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"
        sys.path.insert(0, "/home/x1560/Xinyi_AI")
        ns = runpy.run_path("/home/x1560/Xinyi_AI/app.py")
        cls.app = ns["create_app"]()
        cls.client = cls.app.test_client()
        cls.sid = str(int(time.time()))[-6:]
        cls.headers = {"X-User": f"step28_{cls.sid}", "X-Role": "accountant"}

        resp = cls.client.post(
            "/books",
            json={"name": f"STEP28_B1_T1_{cls.sid}", "accounting_standard": "enterprise"},
        )
        if resp.status_code != 201:
            raise RuntimeError(resp.get_data(as_text=True))
        cls.book_id = int(resp.get_json()["book_id"])

    def _voucher_count(self) -> int:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(1) AS c FROM vouchers WHERE book_id=:book_id"),
                {"book_id": self.book_id},
            ).fetchone()
        return int(row.c or 0)

    def _audit_count(self, action: str) -> int:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT COUNT(1) AS c FROM audit_logs "
                    "WHERE module='voucher' AND action=:action AND operator=:operator"
                ),
                {"action": action, "operator": self.headers["X-User"]},
            ).fetchone()
        return int(row.c or 0)

    def test_01_preview_bank_fee_success(self):
        before_voucher = self._voucher_count()
        before_audit = self._audit_count("template_preview")
        resp = self.client.post(
            "/api/vouchers/template-preview",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "template_code": "BANK_FEE",
                "params": {
                    "amount": "88.80",
                    "biz_date": "2025-02-10",
                    "summary_text": "银行手续费-建行",
                    "counterparty": "建设银行",
                },
            },
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["template_info"]["code"], "BANK_FEE")
        self.assertEqual(len(payload["voucher_draft"]["lines"]), 2)
        self.assertEqual(payload["voucher_draft"]["lines"][0]["subject_code"], "6602")
        self.assertEqual(payload["voucher_draft"]["lines"][1]["subject_code"], "1002")
        self.assertFalse(payload["audit_hint"]["persisted"])
        self.assertEqual(self._voucher_count(), before_voucher)
        self.assertEqual(self._audit_count("template_preview"), before_audit + 1)

    def test_02_suggest_asset_depreciation_success(self):
        before_voucher = self._voucher_count()
        before_audit = self._audit_count("template_suggest")
        resp = self.client.post(
            "/api/vouchers/template-suggest",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "template_code": "ASSET_DEPRECIATION",
                "params": {
                    "amount": "1200.00",
                    "biz_date": "2025-02-28",
                    "summary_text": "2月固定资产折旧",
                },
            },
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["template_info"]["code"], "ASSET_DEPRECIATION")
        self.assertEqual(payload["voucher_draft"]["lines"][0]["subject_code"], "6602")
        self.assertEqual(payload["voucher_draft"]["lines"][1]["subject_code"], "1602")
        self.assertEqual(self._voucher_count(), before_voucher)
        self.assertEqual(self._audit_count("template_suggest"), before_audit + 1)

    def test_03_invalid_subject_failed(self):
        before_voucher = self._voucher_count()
        resp = self.client.post(
            "/api/vouchers/template-preview",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "template_code": "EXPENSE_REIMBURSEMENT_PAYMENT",
                "params": {
                    "amount": "300.00",
                    "biz_date": "2025-02-20",
                    "summary_text": "费用报销付款-测试",
                    "debit_subject_code": "999999",
                    "credit_subject_code": "1002",
                },
            },
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertFalse(payload["success"])
        self.assertTrue(any("subject_not_found:999999" in e["message"] for e in payload["errors"]))
        self.assertEqual(self._voucher_count(), before_voucher)

    def test_04_period_closed_failed(self):
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO accounting_periods (book_id, year, month, status)
                    VALUES (:book_id, 2025, 2, 'closed')
                    ON DUPLICATE KEY UPDATE status='closed'
                    """
                ),
                {"book_id": self.book_id},
            )

        before_voucher = self._voucher_count()
        resp = self.client.post(
            "/api/vouchers/template-preview",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "template_code": "BANK_FEE",
                "params": {"amount": "100.00", "biz_date": "2025-02-15"},
            },
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        payload = resp.get_json()
        self.assertFalse(payload["success"])
        self.assertTrue(any(e["field"] == "biz_date" for e in payload["errors"]))
        self.assertEqual(self._voucher_count(), before_voucher)


if __name__ == "__main__":
    unittest.main()
