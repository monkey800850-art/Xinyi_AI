"""
20260303_000040_sys_users_auth_fields

Add authentication fields for sys_users:
- password_hash
- failed_attempts
- locked_until
- last_login_at
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000040"
down_revision: Union[str, None] = "20260303_000039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return int(row.cnt or 0) > 0


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "sys_users", "password_hash"):
        conn.execute(text("ALTER TABLE sys_users ADD COLUMN password_hash VARCHAR(255) NULL"))
    if not _column_exists(conn, "sys_users", "failed_attempts"):
        conn.execute(text("ALTER TABLE sys_users ADD COLUMN failed_attempts INT NOT NULL DEFAULT 0"))
    if not _column_exists(conn, "sys_users", "locked_until"):
        conn.execute(text("ALTER TABLE sys_users ADD COLUMN locked_until DATETIME NULL"))
    if not _column_exists(conn, "sys_users", "last_login_at"):
        conn.execute(text("ALTER TABLE sys_users ADD COLUMN last_login_at DATETIME NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "sys_users", "last_login_at"):
        conn.execute(text("ALTER TABLE sys_users DROP COLUMN last_login_at"))
    if _column_exists(conn, "sys_users", "locked_until"):
        conn.execute(text("ALTER TABLE sys_users DROP COLUMN locked_until"))
    if _column_exists(conn, "sys_users", "failed_attempts"):
        conn.execute(text("ALTER TABLE sys_users DROP COLUMN failed_attempts"))
    if _column_exists(conn, "sys_users", "password_hash"):
        conn.execute(text("ALTER TABLE sys_users DROP COLUMN password_hash"))
