import os
import runpy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


class Sec04RbacGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SECRET_KEY"] = "sec04-test-secret"
        os.environ["AUTH_ENABLE_RBAC"] = "1"

    def _build_client(self):
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        ns = runpy.run_path(str(repo_root / "app.py"))
        patch_values = {"test_db_connection": lambda: ("127.0.0.1", "3306", "xinyi_ai")}
        with patch.dict(ns["create_app"].__globals__, patch_values):
            app = ns["create_app"]()
            app.testing = True
            return app.test_client()

    def test_01_protected_api_requires_login(self):
        client = self._build_client()
        resp = client.get("/api/not-found")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "unauthorized")

    def test_02_login_endpoint_is_rbac_exempt(self):
        client = self._build_client()
        resp = client.post("/api/auth/login", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "validation_error")

    def test_03_role_without_permission_is_forbidden(self):
        client = self._build_client()
        with client.session_transaction() as sess:
            sess["auth_ctx"] = {"username": "finance_user", "role": "finance"}
            sess["auth_expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        resp = client.get("/api/not-found")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["error"], "forbidden")

    def test_04_admin_role_bypass_rbac(self):
        client = self._build_client()
        with client.session_transaction() as sess:
            sess["auth_ctx"] = {"username": "admin_user", "role": "admin"}
            sess["auth_expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        resp = client.get("/api/not-found")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
