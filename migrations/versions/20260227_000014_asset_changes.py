"""asset changes

Revision ID: 20260227_000014
Revises: 20260227_000013
Create Date: 2026-02-27 00:00:14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000014"
down_revision: Union[str, None] = "20260227_000013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "asset_changes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("asset_id", sa.BigInteger, nullable=False),
        sa.Column("asset_code", sa.String(64), nullable=False),
        sa.Column("change_type", sa.String(16), nullable=False),
        sa.Column("change_date", sa.Date, nullable=False),
        sa.Column("from_department_id", sa.BigInteger, nullable=True),
        sa.Column("to_department_id", sa.BigInteger, nullable=True),
        sa.Column("from_person_id", sa.BigInteger, nullable=True),
        sa.Column("to_person_id", sa.BigInteger, nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_asset_changes_book", "asset_changes", ["book_id"])
    op.create_index("ix_asset_changes_type", "asset_changes", ["change_type"])
    op.create_index("ix_asset_changes_date", "asset_changes", ["change_date"])


def downgrade() -> None:
    op.drop_index("ix_asset_changes_date", table_name="asset_changes")
    op.drop_index("ix_asset_changes_type", table_name="asset_changes")
    op.drop_index("ix_asset_changes_book", table_name="asset_changes")
    op.drop_table("asset_changes")
