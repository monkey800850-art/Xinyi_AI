import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app.services.system_auth_service import AuthError, authenticate_user


class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeConn:
    def __init__(self, user_row=None, role_code="admin"):
        self.user_row = user_row
        self.role_code = role_code
        self.failed_updates = []
        self.success_updates = 0

    def execute(self, stmt, params=None):
        sql = str(stmt).lower()
        params = params or {}
        if "information_schema.columns" in sql:
            return _Result(
                [
                    _Row(column_name="password_hash"),
                    _Row(column_name="failed_attempts"),
                    _Row(column_name="locked_until"),
                ]
            )
        if "from sys_users u" in sql and "where u.username" in sql:
            return _Result([self.user_row] if self.user_row else [])
        if "update sys_users" in sql and "failed_attempts=0" in sql:
            self.success_updates += 1
            return _Result([])
        if "update sys_users" in sql and "set failed_attempts" in sql:
            self.failed_updates.append(params)
            return _Result([])
        if "from sys_user_roles ur" in sql:
            if self.role_code:
                return _Result([_Row(code=self.role_code)])
            return _Result([])
        return _Result([])


class _FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        return self

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class SystemAuthServiceUnitTest(unittest.TestCase):
    def test_login_success(self):
        user_row = _Row(
            id=10,
            username="u1",
            display_name="User 1",
            is_enabled=1,
            password_hash=generate_password_hash("ok-pass"),
            failed_attempts=2,
            locked_until=None,
        )
        conn = _FakeConn(user_row=user_row, role_code="finance")
        with patch("app.services.system_auth_service.get_engine", return_value=_FakeEngine(conn)):
            result = authenticate_user("u1", "ok-pass", max_failed_attempts=5, lock_minutes=15)
        self.assertEqual(result["id"], 10)
        self.assertEqual(result["role"], "finance")
        self.assertEqual(conn.success_updates, 1)

    def test_login_failed_increments_attempts(self):
        user_row = _Row(
            id=11,
            username="u2",
            display_name="User 2",
            is_enabled=1,
            password_hash=generate_password_hash("real-pass"),
            failed_attempts=0,
            locked_until=None,
        )
        conn = _FakeConn(user_row=user_row)
        with patch("app.services.system_auth_service.get_engine", return_value=_FakeEngine(conn)):
            with self.assertRaises(AuthError) as ctx:
                authenticate_user("u2", "bad-pass", max_failed_attempts=5, lock_minutes=15)
        self.assertEqual(str(ctx.exception), "invalid_credentials")
        self.assertEqual(len(conn.failed_updates), 1)
        self.assertEqual(int(conn.failed_updates[0]["failed_attempts"]), 1)

    def test_login_failed_locks_on_threshold(self):
        user_row = _Row(
            id=12,
            username="u3",
            display_name="User 3",
            is_enabled=1,
            password_hash=generate_password_hash("real-pass"),
            failed_attempts=4,
            locked_until=None,
        )
        conn = _FakeConn(user_row=user_row)
        with patch("app.services.system_auth_service.get_engine", return_value=_FakeEngine(conn)):
            with self.assertRaises(AuthError) as ctx:
                authenticate_user("u3", "bad-pass", max_failed_attempts=5, lock_minutes=15)
        self.assertEqual(str(ctx.exception), "account_locked")
        self.assertEqual(len(conn.failed_updates), 1)
        self.assertEqual(int(conn.failed_updates[0]["failed_attempts"]), 5)


if __name__ == "__main__":
    unittest.main()
