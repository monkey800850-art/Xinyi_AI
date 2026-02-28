import os
import runpy
import sys
import time
import unittest


class Step28Batch2PlatformSubjectsTest(unittest.TestCase):
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
        cls.h_admin = {"X-User": f"batch2_admin_{cls.sid}", "X-Role": "admin"}
        cls.h_user = {"X-User": f"batch2_user_{cls.sid}", "X-Role": "accountant"}

        resp = cls.client.post(
            "/books",
            json={"name": f"STEP28_B2_{cls.sid}", "accounting_standard": "enterprise"},
        )
        if resp.status_code != 201:
            raise RuntimeError(resp.get_data(as_text=True))
        cls.book_payload = resp.get_json()
        cls.book_id = int(cls.book_payload["book_id"])

    def test_01_init_integrity(self):
        payload = self.book_payload
        self.assertIn("subject_init_result", payload)
        self.assertIn("period_init_result", payload)
        self.assertIn("init_integrity", payload)
        self.assertIn("category_validation", payload["subject_init_result"])

        resp = self.client.get(f"/api/books/{self.book_id}/init-integrity")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertTrue(data["init_integrity"]["ok"])
        self.assertGreaterEqual(int(data["init_integrity"]["subject_count"]), 50)
        self.assertGreaterEqual(int(data["init_integrity"]["period_count"]), 12)

    def test_02_backup_restore_verify(self):
        resp = self.client.get(
            f"/api/books/{self.book_id}/backup-snapshot",
            headers=self.h_admin,
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        snapshot = resp.get_json()
        self.assertEqual(snapshot["snapshot_version"], "book_backup_v1")
        self.assertGreater(snapshot["stats"]["subject_count"], 0)

        resp_ok = self.client.post(
            "/api/books/backup-restore-verify",
            headers=self.h_admin,
            json={"snapshot": snapshot},
        )
        self.assertEqual(resp_ok.status_code, 200, resp_ok.get_data(as_text=True))
        self.assertTrue(resp_ok.get_json()["ok"])

        bad = dict(snapshot)
        bad["periods"] = [{"year": 2025, "month": 13, "status": "open"}]
        resp_bad = self.client.post(
            "/api/books/backup-restore-verify",
            headers=self.h_admin,
            json={"snapshot": bad},
        )
        self.assertEqual(resp_bad.status_code, 400, resp_bad.get_data(as_text=True))
        self.assertFalse(resp_bad.get_json()["ok"])

    def test_03_disable_book_safety_controls(self):
        # wrong role
        resp = self.client.post(
            f"/api/books/{self.book_id}/disable",
            headers=self.h_user,
            json={"confirm_text": f"DISABLE BOOK {self.book_id}"},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))

        # wrong confirm
        resp = self.client.post(
            f"/api/books/{self.book_id}/disable",
            headers=self.h_admin,
            json={"confirm_text": "DISABLE"},
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))

        # right confirm
        resp = self.client.post(
            f"/api/books/{self.book_id}/disable",
            headers=self.h_admin,
            json={"confirm_text": f"DISABLE BOOK {self.book_id}"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["is_enabled"], 0)

    def test_04_trial_balance_category_summary(self):
        # use new active book for report scenario
        resp = self.client.post(
            "/books",
            json={"name": f"STEP28_B2_RPT_{self.sid}", "accounting_standard": "enterprise"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        book_id = int(resp.get_json()["book_id"])

        voucher_payload = {
            "book_id": book_id,
            "voucher_date": "2025-02-18",
            "voucher_word": "记",
            "voucher_no": f"B2{self.sid}",
            "attachments": 0,
            "maker": "tester",
            "status": "posted",
            "lines": [
                {"summary": "测试收款", "subject_code": "1001", "debit": "100.00", "credit": "0.00"},
                {"summary": "测试收款", "subject_code": "6001", "debit": "0.00", "credit": "100.00"},
            ],
        }
        resp = self.client.post("/api/vouchers", json=voucher_payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))

        resp = self.client.get(
            "/api/trial_balance",
            query_string={"book_id": book_id, "start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertIn("category_summary", data)
        self.assertTrue(any(x["category"] == "资产" for x in data["category_summary"]))
        self.assertTrue(any(x["category"] == "损益" for x in data["category_summary"]))
        self.assertTrue(any(float(x["period_debit"]) > 0 for x in data["category_summary"]))


if __name__ == "__main__":
    unittest.main()
