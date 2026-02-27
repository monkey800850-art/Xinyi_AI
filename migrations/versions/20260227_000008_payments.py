"""payment requests

Revision ID: 20260227_000008
Revises: 20260227_000007
Create Date: 2026-02-27 00:00:08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000008"
down_revision: Union[str, None] = "20260227_000007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("payee_name", sa.String(128), nullable=True),
        sa.Column("payee_account", sa.String(128), nullable=True),
        sa.Column("pay_method", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("related_type", sa.String(32), nullable=True),
        sa.Column("related_id", sa.BigInteger, nullable=True),
        sa.Column("reimbursement_id", sa.BigInteger, nullable=True),
        sa.Column("pay_at", sa.DateTime, nullable=True),
        sa.Column("approve_at", sa.DateTime, nullable=True),
        sa.Column("reject_at", sa.DateTime, nullable=True),
        sa.Column("reject_reason", sa.String(255), nullable=True),
        sa.Column("voucher_id", sa.BigInteger, nullable=True),
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
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_payment_requests_book_status", "payment_requests", ["book_id", "status"])

    op.create_table(
        "payment_request_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("payment_request_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=False),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("operator", sa.String(64), nullable=False),
        sa.Column("operator_role", sa.String(32), nullable=False),
        sa.Column("comment", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_payment_request_logs_pid", "payment_request_logs", ["payment_request_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_request_logs_pid", table_name="payment_request_logs")
    op.drop_table("payment_request_logs")

    op.drop_index("ix_payment_requests_book_status", table_name="payment_requests")
    op.drop_table("payment_requests")
