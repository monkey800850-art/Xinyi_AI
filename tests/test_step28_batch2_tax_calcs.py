import os
import runpy
import sys
import time
import unittest


class Step28Batch2TaxCalcsTest(unittest.TestCase):
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
        cls.headers = {"X-User": f"tax_{cls.sid}", "X-Role": "accountant"}

    def test_01_bonus_separate_success(self):
        resp = self.client.post(
            "/api/tax/calc/year-end-bonus",
            headers=self.headers,
            json={"bonus_amount": "36000", "tax_mode": "separate", "biz_year": 2025},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertEqual(data["tax_mode"], "separate")
        self.assertAlmostEqual(float(data["tax_amount"]), 1080.0, places=2)
        self.assertIn("separate mode", data["explain"])

    def test_02_bonus_merge_success(self):
        resp = self.client.post(
            "/api/tax/calc/year-end-bonus",
            headers=self.headers,
            json={"bonus_amount": "36000", "tax_mode": "merge", "biz_year": 2025},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertEqual(data["tax_mode"], "merge")
        self.assertAlmostEqual(float(data["tax_amount"]), 1080.0, places=2)
        self.assertIn("simplified", data["explain"])

    def test_03_bonus_invalid_mode_failed(self):
        resp = self.client.post(
            "/api/tax/calc/year-end-bonus",
            headers=self.headers,
            json={"bonus_amount": "36000", "tax_mode": "invalid", "biz_year": 2025},
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.assertIn("tax_mode", resp.get_json()["error"])

    def test_04_labor_service_success(self):
        resp = self.client.post(
            "/api/tax/calc/labor-service",
            headers=self.headers,
            json={"gross_amount": "10000", "period": "2025-02"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        data = resp.get_json()
        self.assertAlmostEqual(float(data["taxable_base"]), 8000.0, places=2)
        self.assertAlmostEqual(float(data["tax_amount"]), 1600.0, places=2)
        self.assertIn("simplified", data["explain"])

    def test_05_labor_service_invalid_amount_failed(self):
        resp = self.client.post(
            "/api/tax/calc/labor-service",
            headers=self.headers,
            json={"gross_amount": "-1", "period": "2025-02"},
        )
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.assertIn("gross_amount", resp.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
