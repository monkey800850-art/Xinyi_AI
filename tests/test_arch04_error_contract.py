import os
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.errors import APIError


class Arch04ErrorContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["APP_ENV"] = "test"
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        os.environ["SECRET_KEY"] = "test-secret"
        os.environ["AUTH_ENABLE_RBAC"] = "0"

        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        ns = runpy.run_path(str(repo_root / "app.py"))
        with patch.dict(ns["create_app"].__globals__, {"test_db_connection": lambda: ("127.0.0.1", "3306", "xinyi_ai")}):
            cls.app = ns["create_app"]()
        cls.app.testing = True

        @cls.app.get("/api/_raise_api_error")
        def _raise_api_error():
            raise APIError(code="validation_error", message="validation_error", details={"field": "name"}, status_code=400)

        @cls.app.get("/api/_raise_unexpected")
        def _raise_unexpected():
            raise ValueError("boom")

        cls.client = cls.app.test_client()

    def test_01_api_error_contract(self):
        resp = self.client.get("/api/_raise_api_error", headers={"X-Request-Id": "RID-001"})
        self.assertEqual(resp.status_code, 400)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "validation_error")
        self.assertEqual(payload["error"]["details"]["field"], "name")
        self.assertEqual(payload["audit"]["request_id"], "RID-001")
        self.assertEqual(payload["audit"]["path"], "/api/_raise_api_error")

    def test_02_unexpected_error_contract(self):
        resp = self.client.get("/api/_raise_unexpected", headers={"X-Request-Id": "RID-002"})
        self.assertEqual(resp.status_code, 500)
        payload = resp.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertEqual(payload["audit"]["request_id"], "RID-002")
        self.assertEqual(payload["audit"]["path"], "/api/_raise_unexpected")


if __name__ == "__main__":
    unittest.main()
