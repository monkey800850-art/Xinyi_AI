"""dashboard role todo reminders

Revision ID: 20260303_000048
Revises: 20260303_000047
Create Date: 2026-03-03 23:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000048"
down_revision: Union[str, None] = "20260303_000047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _table_exists(bind, table_name: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchone()
    return int(row.cnt or 0) > 0


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND index_name = :index_name
            """
        ),
        {"table_name": table_name, "index_name": index_name},
    ).fetchone()
    return int(row.cnt or 0) > 0


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "dashboard_task_reminders"):
        op.create_table(
            "dashboard_task_reminders",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("role_code", sa.String(32), nullable=False),
            sa.Column("task_code", sa.String(64), nullable=False),
            sa.Column("assignee", sa.String(64), nullable=True),
            sa.Column("message", sa.String(255), nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'sent'")),
            sa.Column("reminder_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("operator", sa.String(64), nullable=True),
            sa.Column("operator_role", sa.String(64), nullable=True),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "dashboard_task_reminders", "ix_dash_reminders_task_day"):
        op.create_index("ix_dash_reminders_task_day", "dashboard_task_reminders", ["task_code", "reminder_at"])
    if not _index_exists(bind, "dashboard_task_reminders", "ix_dash_reminders_role"):
        op.create_index("ix_dash_reminders_role", "dashboard_task_reminders", ["role_code"])


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "dashboard_task_reminders"):
        if _index_exists(bind, "dashboard_task_reminders", "ix_dash_reminders_role"):
            op.drop_index("ix_dash_reminders_role", table_name="dashboard_task_reminders")
        if _index_exists(bind, "dashboard_task_reminders", "ix_dash_reminders_task_day"):
            op.drop_index("ix_dash_reminders_task_day", table_name="dashboard_task_reminders")
        op.drop_table("dashboard_task_reminders")
