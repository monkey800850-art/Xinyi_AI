import os
import runpy
import sys
import unittest


class Arch07SystemConsolidationPageSmokeTest(unittest.TestCase):
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

    def test_01_system_consolidation_page_contains_params_region(self):
        resp = self.client.get("/system/consolidation")
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        html = resp.get_data(as_text=True)
        self.assertIn("conso-params-card", html)
        self.assertIn("合并参数", html)


if __name__ == "__main__":
    unittest.main()
