from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import text
from werkzeug.security import check_password_hash

from app.db import get_engine


class AuthError(RuntimeError):
    def __init__(self, message: str, detail: Dict[str, object] | None = None):
        super().__init__(message)
        self.detail = detail or {}


def _extract_column_value(row) -> str:
    mapping = getattr(row, "_mapping", None)
    if mapping is None and isinstance(row, dict):
        mapping = row
    if mapping is not None:
        for k, v in dict(mapping).items():
            key = str(k or "").strip().lower()
            if key in ("column_name", "name", "field"):
                return str(v or "").strip().lower()
    for attr in ("column_name", "COLUMN_NAME", "name", "Name", "field", "Field"):
        if hasattr(row, attr):
            return str(getattr(row, attr) or "").strip().lower()
    if isinstance(row, (tuple, list)) and row:
        return str(row[0] or "").strip().lower()
    return ""


def _get_table_columns(conn, table_name: str) -> set[str]:
    try:
        rows = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()
        cols = {_extract_column_value(r) for r in rows}
        cols = {c for c in cols if c}
        if cols:
            return cols
    except Exception:
        pass
    try:
        rows = conn.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
        cols = {_extract_column_value(r) for r in rows}
        cols = {c for c in cols if c}
        if cols:
            return cols
    except Exception:
        pass
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    cols = {_extract_column_value(r) for r in rows}
    return {c for c in cols if c}


def authenticate_user(
    username: str,
    password: str,
    max_failed_attempts: int = 5,
    lock_minutes: int = 15,
) -> Dict[str, object]:
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        raise AuthError("validation_error", {"field": "username/password"})

    engine = get_engine()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        cols = _get_table_columns(conn, "sys_users")
        required_cols = {"password_hash", "failed_attempts", "locked_until"}
        if not required_cols.issubset(cols):
            raise AuthError("auth_schema_not_ready")

        row = conn.execute(
            text(
                """
                SELECT u.id, u.username, u.display_name, u.is_enabled,
                       u.password_hash, u.failed_attempts, u.locked_until
                FROM sys_users u
                WHERE u.username=:username
                LIMIT 1
                """
            ),
            {"username": username},
        ).fetchone()
        if not row:
            raise AuthError("invalid_credentials")

        if int(row.is_enabled or 0) != 1:
            raise AuthError("user_disabled")

        locked_until = row.locked_until
        if locked_until and locked_until > now:
            raise AuthError("account_locked", {"locked_until": str(locked_until)})

        pwd_hash = str(row.password_hash or "").strip()
        if not pwd_hash or not check_password_hash(pwd_hash, password):
            failed_attempts = int(row.failed_attempts or 0) + 1
            next_locked_until = None
            if failed_attempts >= max_failed_attempts:
                next_locked_until = now + timedelta(minutes=max(1, int(lock_minutes or 15)))
            conn.execute(
                text(
                    """
                    UPDATE sys_users
                    SET failed_attempts=:failed_attempts,
                        locked_until=:locked_until,
                        updated_at=NOW()
                    WHERE id=:id
                    """
                ),
                {
                    "id": int(row.id),
                    "failed_attempts": failed_attempts,
                    "locked_until": next_locked_until,
                },
            )
            if next_locked_until:
                raise AuthError(
                    "account_locked",
                    {"locked_until": str(next_locked_until), "failed_attempts": failed_attempts},
                )
            raise AuthError(
                "invalid_credentials",
                {
                    "failed_attempts": failed_attempts,
                    "remaining_attempts": max(0, int(max_failed_attempts) - failed_attempts),
                },
            )

        conn.execute(
            text(
                """
                UPDATE sys_users
                SET failed_attempts=0,
                    locked_until=NULL,
                    last_login_at=NOW(),
                    updated_at=NOW()
                WHERE id=:id
                """
            ),
            {"id": int(row.id)},
        )

        role_row = conn.execute(
            text(
                """
                SELECT r.code
                FROM sys_user_roles ur
                JOIN sys_roles r ON r.id = ur.role_id
                WHERE ur.user_id=:uid
                  AND r.is_enabled=1
                ORDER BY ur.id ASC
                LIMIT 1
                """
            ),
            {"uid": int(row.id)},
        ).fetchone()

        return {
            "id": int(row.id),
            "username": str(row.username or ""),
            "display_name": str(row.display_name or ""),
            "role": str(role_row.code or "") if role_row else "",
        }
