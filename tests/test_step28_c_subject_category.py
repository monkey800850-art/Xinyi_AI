import os
import runpy
import sys
import tempfile
import time
import unittest

from sqlalchemy import text

from app.db import get_engine


class Step28CSubjectCategoryTest(unittest.TestCase):
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

    def _create_book(self, name_suffix: str) -> int:
        resp = self.client.post(
            "/books",
            json={"name": f"STEP28_C_{name_suffix}_{self.sid}", "accounting_standard": "enterprise"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        return int(resp.get_json()["book_id"])

    def _post_simple_voucher(self, book_id: int, voucher_no: str):
        payload = {
            "book_id": book_id,
            "voucher_date": "2025-02-18",
            "voucher_word": "记",
            "voucher_no": voucher_no,
            "attachments": 0,
            "maker": "tester",
            "status": "posted",
            "lines": [
                {"summary": "测试收款", "subject_code": "1001", "debit": "100.00", "credit": "0.00"},
                {"summary": "测试收款", "subject_code": "6001", "debit": "0.00", "credit": "100.00"},
            ],
        }
        resp = self.client.post("/api/vouchers", json=payload)
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))

    def test_01_category_consistent_success(self):
        book_id = self._create_book("CONSISTENT")
        self._post_simple_voucher(book_id, f"C{self.sid}01")
        resp = self.client.get(
            "/api/trial_balance",
            query_string={"book_id": book_id, "start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertTrue(any(x["category_code"] == "ASSET" for x in data["category_summary"]))
        self.assertTrue(any(x["category_code"] == "PNL" for x in data["category_summary"]))

    def test_02_import_category_mismatch_warn(self):
        with tempfile.TemporaryDirectory(prefix="step28_c_tpl_") as temp_dir:
            csv_path = os.path.join(temp_dir, "enterprise.csv")
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                f.write("科目编码,科目名称,类别,余额方向,说明\n")
                f.write("1001,库存现金,负债,借,测试不一致\n")
                f.write("6001,主营业务收入,损益,贷,\n")

            old_templates_dir = os.environ.get("TEMPLATES_DIR")
            os.environ["TEMPLATES_DIR"] = temp_dir
            try:
                resp = self.client.post(
                    "/books",
                    json={"name": f"STEP28_C_MISMATCH_{self.sid}", "accounting_standard": "enterprise"},
                )
            finally:
                if old_templates_dir is None:
                    os.environ.pop("TEMPLATES_DIR", None)
                else:
                    os.environ["TEMPLATES_DIR"] = old_templates_dir

        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        payload = resp.get_json()
        category_validation = payload["subject_init_result"]["category_validation"]
        self.assertGreaterEqual(int(category_validation["mismatch_count"]), 1)
        self.assertEqual(category_validation["mode"], "warn_only")

    def test_03_trial_balance_old_data_prefix_fallback_success(self):
        book_id = self._create_book("FALLBACK")
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE subjects SET category='' WHERE book_id=:book_id AND code IN ('1001','6001')"),
                {"book_id": book_id},
            )
        self._post_simple_voucher(book_id, f"C{self.sid}03")
        resp = self.client.get(
            "/api/trial_balance",
            query_string={"book_id": book_id, "start_date": "2025-02-01", "end_date": "2025-02-28"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        item_1001 = next(x for x in data["items"] if x["code"] == "1001")
        self.assertEqual(item_1001["category_code"], "ASSET")
        self.assertEqual(item_1001["category_name"], "资产")
        self.assertEqual(item_1001["category_source"], "prefix_fallback")
        self.assertTrue(any(x["category_code"] == "ASSET" for x in data["category_summary"]))


if __name__ == "__main__":
    unittest.main()
