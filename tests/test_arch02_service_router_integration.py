from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.system_service import list_roles
from app.services.trial_balance_service import get_trial_balance


class _FakeResult(list):
    def fetchall(self):
        return self


class _FakeConn:
    def __init__(self, rows_by_call):
        self._rows_by_call = rows_by_call
        self._idx = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _sql, _params=None):
        rows = self._rows_by_call[self._idx]
        self._idx += 1
        return _FakeResult(rows)


class _FakeProvider:
    def __init__(self, conn):
        self._conn = conn
        self.calls = []

    def connect(self, tenant_id=None, book_id=None):
        self.calls.append({"tenant_id": tenant_id, "book_id": book_id})
        return self._conn


class Arch02ServiceRouterIntegrationTest(unittest.TestCase):
    def test_01_list_roles_via_provider(self):
        conn = _FakeConn(
            [
                [
                    SimpleNamespace(
                        id=1,
                        code="admin",
                        name="管理员",
                        description="",
                        data_scope="ALL",
                        is_enabled=1,
                    )
                ],
                [SimpleNamespace(role_id=1, perm_key="system.roles.read")],
            ]
        )
        provider = _FakeProvider(conn)
        with patch("app.services.system_service.get_connection_provider", return_value=provider):
            data = list_roles({"tenant_id": "T001"})

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["tenant_id"], "T001")
        self.assertIsNone(provider.calls[0]["book_id"])
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["code"], "admin")
        self.assertEqual(data["items"][0]["permissions"], ["system.roles.read"])

    def test_02_trial_balance_via_provider(self):
        conn = _FakeConn(
            [
                [
                    SimpleNamespace(id=9, name="账套9", is_enabled=1, book_code="BOOK-0009"),
                ],
                [],
                [],
                [],
                [
                    SimpleNamespace(
                        id=1,
                        code="1001",
                        name="库存现金",
                        category="资产",
                        level=1,
                        parent_code="",
                        balance_direction="DEBIT",
                    ),
                    SimpleNamespace(
                        id=2,
                        code="6001",
                        name="主营业务收入",
                        category="损益",
                        level=1,
                        parent_code="",
                        balance_direction="CREDIT",
                    ),
                ],
                [
                    SimpleNamespace(code="1001", debit_sum="100.00", credit_sum="0.00"),
                    SimpleNamespace(code="6001", debit_sum="0.00", credit_sum="100.00"),
                ],
            ]
        )
        provider = _FakeProvider(conn)
        with patch("app.services.trial_balance_service.get_connection_provider", return_value=provider):
            data = get_trial_balance(
                {
                    "tenant_id": "T001",
                    "book_id": "9",
                    "start_date": "2025-02-01",
                    "end_date": "2025-02-28",
                }
            )

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["tenant_id"], "T001")
        self.assertEqual(provider.calls[0]["book_id"], 9)
        self.assertEqual(data["book_id"], 9)
        self.assertEqual(data.get("scope_type"), "single")
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(any(x["category_code"] == "ASSET" for x in data["category_summary"]))
        self.assertTrue(any(x["category_code"] == "PNL" for x in data["category_summary"]))


if __name__ == "__main__":
    unittest.main()
