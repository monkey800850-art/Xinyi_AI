"""asset depreciation

Revision ID: 20260227_000013
Revises: 20260227_000012
Create Date: 2026-02-27 00:00:13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000013"
down_revision: Union[str, None] = "20260227_000012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "depreciation_batches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("method", sa.String(32), nullable=False, server_default=sa.text("'STRAIGHT_LINE'")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
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
        sa.UniqueConstraint("book_id", "period_year", "period_month", name="uq_depr_batch_book_period"),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_depr_batch_book_period",
        "depreciation_batches",
        ["book_id", "period_year", "period_month"],
    )

    op.create_table(
        "depreciation_lines",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.BigInteger, nullable=False),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("asset_id", sa.BigInteger, nullable=False),
        sa.Column("asset_code", sa.String(64), nullable=False),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("category_id", sa.BigInteger, nullable=False),
        sa.Column("depreciation_method", sa.String(32), nullable=False),
        sa.Column("original_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("residual_rate", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("useful_life_months", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("monthly_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("expense_subject_code", sa.String(64), nullable=True),
        sa.Column("accumulated_depr_subject_code", sa.String(64), nullable=True),
        sa.Column("start_use_date", sa.Date, nullable=True),
        sa.Column("capitalization_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'SUCCESS'")),
        sa.Column("error_message", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_depr_lines_batch", "depreciation_lines", ["batch_id"])
    op.create_index("ix_depr_lines_asset", "depreciation_lines", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_depr_lines_asset", table_name="depreciation_lines")
    op.drop_index("ix_depr_lines_batch", table_name="depreciation_lines")
    op.drop_table("depreciation_lines")

    op.drop_index("ix_depr_batch_book_period", table_name="depreciation_batches")
    op.drop_table("depreciation_batches")
