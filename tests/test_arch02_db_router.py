import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.db_router import (
    ConnectionProvider,
    DbRouter,
    clear_request_route_context,
    get_request_route_context,
    resolve_route_hints,
    set_request_route_context,
)


class Arch02DbRouterTest(unittest.TestCase):
    def setUp(self):
        os.environ["DB_HOST"] = "127.0.0.1"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_NAME"] = "xinyi_ai"
        os.environ["DB_USER"] = "root"
        os.environ["DB_PASSWORD"] = "88888888"
        os.environ["DB_ROUTER_MODE"] = "single"
        os.environ["DB_ROUTER_MISS_STRATEGY"] = "fallback"
        clear_request_route_context()

    def tearDown(self):
        clear_request_route_context()

    def test_01_request_context_and_hint_merge(self):
        set_request_route_context(tenant_id="TENANT_A", book_id="12")
        ctx = get_request_route_context()
        self.assertEqual(ctx.tenant_id, "TENANT_A")
        self.assertEqual(ctx.book_id, 12)

        hint = resolve_route_hints()
        self.assertEqual(hint.tenant_id, "TENANT_A")
        self.assertEqual(hint.book_id, 12)

        override = resolve_route_hints(book_id=99)
        self.assertEqual(override.book_id, 99)
        self.assertEqual(override.tenant_id, "TENANT_A")

    def test_02_single_mode_route_fallback(self):
        router = DbRouter()
        decision = router.resolve_route(tenant_id="TENANT_A", book_id=8)
        self.assertEqual(decision.mode, "single")
        self.assertEqual(decision.tenant_id, "TENANT_A")
        self.assertEqual(decision.book_id, 8)
        self.assertTrue(decision.datasource.endswith("/xinyi_ai"))
        self.assertEqual(decision.schema_name, "xinyi_ai")

    def test_03_connection_provider_engine_cache(self):
        provider = ConnectionProvider(DbRouter())
        e1 = provider.get_engine(tenant_id="TENANT_A", book_id=8)
        e2 = provider.get_engine(tenant_id="TENANT_A", book_id=8)
        self.assertIs(e1, e2)

    def test_04_compat_route_mapping_found(self):
        os.environ["DB_ROUTER_MODE"] = "compat"
        router = DbRouter()
        row = SimpleNamespace(
            driver="mysql+pymysql",
            host="127.0.0.1",
            port="3306",
            db_name="xinyi_ai",
            username="root",
            password="88888888",
            charset="utf8mb4",
            schema_name="tenant_a_schema",
        )
        with patch.object(router, "_query_mapping", return_value=row):
            decision = router.resolve_route(tenant_id="TENANT_A", book_id=8)
        self.assertEqual(decision.mode, "compat")
        self.assertEqual(decision.schema_name, "tenant_a_schema")
        self.assertEqual(decision.datasource, "127.0.0.1:3306/xinyi_ai")

    def test_05_compat_route_mapping_not_found_fallback(self):
        os.environ["DB_ROUTER_MODE"] = "compat"
        os.environ["DB_ROUTER_MISS_STRATEGY"] = "fallback"
        router = DbRouter()
        with patch.object(router, "_query_mapping", return_value=None):
            decision = router.resolve_route(tenant_id="NO_MAPPING", book_id=8)
        self.assertEqual(decision.mode, "compat")
        self.assertTrue(decision.datasource.endswith("/xinyi_ai"))

    def test_06_compat_route_mapping_not_found_strict(self):
        os.environ["DB_ROUTER_MODE"] = "compat"
        os.environ["DB_ROUTER_MISS_STRATEGY"] = "strict"
        router = DbRouter()
        with patch.object(router, "_query_mapping", return_value=None):
            with self.assertRaises(RuntimeError):
                router.resolve_route(tenant_id="NO_MAPPING", book_id=8)


if __name__ == "__main__":
    unittest.main()
