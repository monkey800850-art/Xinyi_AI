"""vouchers

Revision ID: 20260227_000004
Revises: 20260227_000003
Create Date: 2026-02-27 00:00:04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000004"
down_revision: Union[str, None] = "20260227_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
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
        sa.UniqueConstraint("book_id", "year", "month", name="uq_period_book_year_month"),
        **MYSQL_TABLE_ARGS,
    )

    op.create_table(
        "vouchers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("voucher_date", sa.Date, nullable=False),
        sa.Column("voucher_word", sa.String(16), nullable=True),
        sa.Column("voucher_no", sa.String(32), nullable=True),
        sa.Column("attachments", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("maker", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
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
    op.create_index("ix_vouchers_book_date", "vouchers", ["book_id", "voucher_date"])

    op.create_table(
        "voucher_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("voucher_id", sa.BigInteger, nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False),
        sa.Column("summary", sa.String(255), nullable=True),
        sa.Column("subject_id", sa.BigInteger, nullable=False),
        sa.Column("subject_code", sa.String(64), nullable=False),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("aux_display", sa.String(255), nullable=True),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
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
    op.create_index("ix_voucher_lines_voucher_id", "voucher_lines", ["voucher_id"])
    op.create_index(
        "ix_voucher_lines_subject", "voucher_lines", ["subject_id", "subject_code"]
    )


def downgrade() -> None:
    op.drop_index("ix_voucher_lines_subject", table_name="voucher_lines")
    op.drop_index("ix_voucher_lines_voucher_id", table_name="voucher_lines")
    op.drop_table("voucher_lines")

    op.drop_index("ix_vouchers_book_date", table_name="vouchers")
    op.drop_table("vouchers")

    op.drop_table("accounting_periods")
