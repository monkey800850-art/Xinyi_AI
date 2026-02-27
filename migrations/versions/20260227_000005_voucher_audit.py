"""voucher audit logs

Revision ID: 20260227_000005
Revises: 20260227_000004
Create Date: 2026-02-27 00:00:05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000005"
down_revision: Union[str, None] = "20260227_000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "voucher_audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("voucher_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=False),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("operator", sa.String(64), nullable=False),
        sa.Column("operator_role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_voucher_audit_voucher", "voucher_audit_logs", ["voucher_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_voucher_audit_voucher", table_name="voucher_audit_logs")
    op.drop_table("voucher_audit_logs")
