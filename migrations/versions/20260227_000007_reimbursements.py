"""reimbursements

Revision ID: 20260227_000007
Revises: 20260227_000006
Create Date: 2026-02-27 00:00:07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000007"
down_revision: Union[str, None] = "20260227_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "reimbursements",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("applicant", sa.String(64), nullable=True),
        sa.Column("department", sa.String(64), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("submit_at", sa.DateTime, nullable=True),
        sa.Column("approve_at", sa.DateTime, nullable=True),
        sa.Column("reject_at", sa.DateTime, nullable=True),
        sa.Column("reject_reason", sa.String(255), nullable=True),
        sa.Column("attachment_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("attachments", sa.Text, nullable=True),
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
    op.create_index("ix_reimbursements_book_status", "reimbursements", ["book_id", "status"])

    op.create_table(
        "reimbursement_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("reimbursement_id", sa.BigInteger, nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False),
        sa.Column("expense_date", sa.Date, nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
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
    op.create_index("ix_reimbursement_items_rid", "reimbursement_items", ["reimbursement_id"])

    op.create_table(
        "reimbursement_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("reimbursement_id", sa.BigInteger, nullable=False),
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
    op.create_index("ix_reimbursement_logs_rid", "reimbursement_logs", ["reimbursement_id"])


def downgrade() -> None:
    op.drop_index("ix_reimbursement_logs_rid", table_name="reimbursement_logs")
    op.drop_table("reimbursement_logs")

    op.drop_index("ix_reimbursement_items_rid", table_name="reimbursement_items")
    op.drop_table("reimbursement_items")

    op.drop_index("ix_reimbursements_book_status", table_name="reimbursements")
    op.drop_table("reimbursements")
