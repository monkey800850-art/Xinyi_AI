import unittest
from unittest.mock import patch

from app.services.consolidation_query_service import ConsolidationQueryService


class _FakeRepo:
    def fetch_consolidated_data(self, limit=20):
        return {
            "items": [{"id": 1, "group_code": "G-001", "group_name": "示例组"}],
            "count": 1,
            "limit": limit,
        }


class Arch03LayeringTest(unittest.TestCase):
    def test_service_calls_repo(self):
        svc = ConsolidationQueryService(repo=_FakeRepo())
        result = svc.get_consolidated_data(limit=10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["group_code"], "G-001")

    def test_route_uses_service_layer(self):
        import runpy
        import sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        ns = runpy.run_path(str(repo_root / "app.py"))
        with patch.dict(ns["create_app"].__globals__, {"test_db_connection": lambda: ("127.0.0.1", "3306", "xinyi_ai")}):
            app = ns["create_app"]()
        app.testing = True
        client = app.test_client()

        with patch("app.routes.consolidation.consolidation_query_service.get_consolidated_data") as mock_get:
            mock_get.return_value = {"items": [{"id": 2, "group_code": "G-002", "group_name": "层次组"}], "count": 1}
            resp = client.get("/consolidation/consolidated-data")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["items"][0]["group_code"], "G-002")


if __name__ == "__main__":
    unittest.main()
