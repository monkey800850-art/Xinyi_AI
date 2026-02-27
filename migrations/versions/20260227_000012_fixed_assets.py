"""fixed assets base

Revision ID: 20260227_000012
Revises: 20260227_000011
Create Date: 2026-02-27 00:00:12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000012"
down_revision: Union[str, None] = "20260227_000011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "asset_categories",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("depreciation_method", sa.String(32), nullable=False, server_default=sa.text("'STRAIGHT_LINE'")),
        sa.Column("default_useful_life_months", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("default_residual_rate", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("expense_subject_code", sa.String(64), nullable=True),
        sa.Column("accumulated_depr_subject_code", sa.String(64), nullable=True),
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
        sa.UniqueConstraint("book_id", "code", name="uq_asset_categories_book_code"),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_asset_categories_book", "asset_categories", ["book_id"])

    op.create_table(
        "fixed_assets",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("asset_code", sa.String(64), nullable=False),
        sa.Column("asset_name", sa.String(255), nullable=False),
        sa.Column("category_id", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("original_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("residual_rate", sa.Numeric(6, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("useful_life_months", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("depreciation_method", sa.String(32), nullable=False, server_default=sa.text("'STRAIGHT_LINE'")),
        sa.Column("start_use_date", sa.Date, nullable=True),
        sa.Column("capitalization_date", sa.Date, nullable=True),
        sa.Column("department_id", sa.BigInteger, nullable=True),
        sa.Column("person_id", sa.BigInteger, nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
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
        sa.UniqueConstraint("book_id", "asset_code", name="uq_fixed_assets_book_code"),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_fixed_assets_book", "fixed_assets", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_fixed_assets_book", table_name="fixed_assets")
    op.drop_table("fixed_assets")

    op.drop_index("ix_asset_categories_book", table_name="asset_categories")
    op.drop_table("asset_categories")
