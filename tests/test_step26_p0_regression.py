import os
import runpy
import sys
import time
import unittest


class Step26P0RegressionTest(unittest.TestCase):
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

    def test_s5_s6_regression(self):
        h_admin = {"X-User": f"reg_admin_{self.sid}", "X-Role": "admin"}

        # bootstrap book + subjects
        resp = self.client.post(
            "/books",
            json={
                "name": f"REG_STEP26_{self.sid}",
                "accounting_standard": "enterprise",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        book_id = resp.get_json()["book_id"]

        # category
        resp = self.client.post(
            "/api/assets/categories",
            headers=h_admin,
            json={
                "book_id": book_id,
                "code": f"REG_CAT_{self.sid}",
                "name": "REG设备",
                "depreciation_method": "STRAIGHT_LINE",
                "default_useful_life_months": 60,
                "default_residual_rate": 5,
                "expense_subject_code": "6602",
                "accumulated_depr_subject_code": "1602",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        category_id = resp.get_json()["id"]

        # asset A: will run depreciation
        resp = self.client.post(
            "/api/assets",
            headers=h_admin,
            json={
                "book_id": book_id,
                "asset_code": f"REG_FA_A_{self.sid}",
                "asset_name": "REG A",
                "category_id": category_id,
                "status": "ACTIVE",
                "original_value": 12000,
                "residual_rate": 5,
                "residual_value": 600,
                "useful_life_months": 60,
                "depreciation_method": "STRAIGHT_LINE",
                "purchase_date": "2025-01-01",
                "start_use_date": "2025-01-01",
                "capitalization_date": "2025-01-01",
                "is_depreciable": 1,
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        asset_a_id = resp.get_json()["id"]

        # asset B: no depreciation line yet (future start date)
        resp = self.client.post(
            "/api/assets",
            headers=h_admin,
            json={
                "book_id": book_id,
                "asset_code": f"REG_FA_B_{self.sid}",
                "asset_name": "REG B",
                "category_id": category_id,
                "status": "ACTIVE",
                "original_value": 8000,
                "residual_rate": 5,
                "residual_value": 400,
                "useful_life_months": 60,
                "depreciation_method": "STRAIGHT_LINE",
                "purchase_date": "2025-03-01",
                "start_use_date": "2025-03-01",
                "capitalization_date": "2025-03-01",
                "is_depreciable": 1,
            },
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))

        # run depreciation for 2025-02 (only asset A should be posted)
        resp = self.client.post(
            "/api/assets/depreciation",
            headers=h_admin,
            json={"book_id": book_id, "year": 2025, "month": 2, "voucher_status": "draft"},
        )
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))

        # S5 regression: changes list should not 500
        resp = self.client.post(
            f"/api/assets/{asset_a_id}/change",
            headers=h_admin,
            json={
                "change_type": "TRANSFER",
                "change_date": "2025-02-15",
                "to_department_id": 2001,
                "note": "reg transfer",
            },
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))

        resp = self.client.get(
            "/api/assets/changes",
            query_string={"book_id": book_id, "asset_code": f"REG_FA_A_{self.sid}"},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertGreaterEqual(len(resp.get_json()["items"]), 1)

        # S6 regression: ledger should not 500 and B should still exist with accum_depr=0
        resp = self.client.get(
            "/api/assets/ledger",
            query_string={"book_id": book_id, "dep_year": 2025, "dep_month": 2},
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        items = resp.get_json()["items"]
        self.assertGreaterEqual(len(items), 2)

        item_map = {x["asset_code"]: x for x in items}
        asset_b_code = f"REG_FA_B_{self.sid}"
        self.assertIn(asset_b_code, item_map)
        self.assertEqual(float(item_map[asset_b_code]["accumulated_depr"]), 0.0)


if __name__ == "__main__":
    unittest.main()
