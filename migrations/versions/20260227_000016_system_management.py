"""system management

Revision ID: 20260227_000016
Revises: 20260227_000015
Create Date: 2026-02-27 00:00:16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000016"
down_revision: Union[str, None] = "20260227_000015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "sys_users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("username", name="uq_sys_users_username"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "sys_roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("data_scope", sa.String(32), nullable=False, server_default=sa.text("'ALL'")),
        sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("code", name="uq_sys_roles_code"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "sys_user_roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("role_id", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_sys_user_roles"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "sys_role_permissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.BigInteger, nullable=False),
        sa.Column("perm_key", sa.String(128), nullable=False),
        sa.UniqueConstraint("role_id", "perm_key", name="uq_sys_role_perms"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "sys_rules",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("rule_value", sa.Text, nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("rule_key", name="uq_sys_rules_key"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.BigInteger, nullable=True),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column("operator_role", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_audit_logs_module", "audit_logs", ["module"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_operator", "audit_logs", ["operator"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_operator", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_module", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_table("sys_rules")
    op.drop_table("sys_role_permissions")
    op.drop_table("sys_user_roles")
    op.drop_table("sys_roles")
    op.drop_table("sys_users")
