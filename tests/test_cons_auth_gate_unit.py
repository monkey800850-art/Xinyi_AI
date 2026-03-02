import unittest

from app.services.consolidation_authorization_service import (
    ConsolidationAuthorizationError,
    assert_virtual_authorized,
)


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, active_row=None, latest_row=None):
        self.active_row = active_row
        self.latest_row = latest_row
        self.calls = 0

    def execute(self, sql, params=None):
        self.calls += 1
        if self.calls == 1:
            return _FakeResult([self.active_row] if self.active_row else [])
        return _FakeResult([self.latest_row] if self.latest_row else [])


class _Row:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class ConsolidationAuthorizationGateUnitTest(unittest.TestCase):
    def test_01_active_authorization_pass(self):
        conn = _FakeConn(active_row=_Row(id=1))
        assert_virtual_authorized(conn, 1, __import__("datetime").date(2026, 3, 2))

    def test_02_missing_authorization_blocked(self):
        conn = _FakeConn(active_row=None, latest_row=None)
        with self.assertRaises(ConsolidationAuthorizationError) as ctx:
            assert_virtual_authorized(conn, 1, __import__("datetime").date(2026, 3, 2))
        self.assertEqual(str(ctx.exception), "authorization_missing")

    def test_03_suspended_authorization_blocked(self):
        conn = _FakeConn(active_row=None, latest_row=_Row(status="suspended"))
        with self.assertRaises(ConsolidationAuthorizationError) as ctx:
            assert_virtual_authorized(conn, 1, __import__("datetime").date(2026, 3, 2))
        self.assertEqual(str(ctx.exception), "authorization_suspended")

    def test_04_revoked_authorization_blocked(self):
        conn = _FakeConn(active_row=None, latest_row=_Row(status="revoked"))
        with self.assertRaises(ConsolidationAuthorizationError) as ctx:
            assert_virtual_authorized(conn, 1, __import__("datetime").date(2026, 3, 2))
        self.assertEqual(str(ctx.exception), "authorization_revoked")

    def test_05_expired_authorization_blocked(self):
        conn = _FakeConn(active_row=None, latest_row=_Row(status="active"))
        with self.assertRaises(ConsolidationAuthorizationError) as ctx:
            assert_virtual_authorized(conn, 1, __import__("datetime").date(2026, 3, 2))
        self.assertEqual(str(ctx.exception), "authorization_expired")


if __name__ == "__main__":
    unittest.main()

