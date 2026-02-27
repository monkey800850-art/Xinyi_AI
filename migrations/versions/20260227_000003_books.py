"""books table

Revision ID: 20260227_000003
Revises: 20260227_000002
Create Date: 2026-02-27 00:00:03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000003"
down_revision: Union[str, None] = "20260227_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("accounting_standard", sa.String(32), nullable=False),
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
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_books_accounting_standard", "books", ["accounting_standard"])


def downgrade() -> None:
    op.drop_index("ix_books_accounting_standard", table_name="books")
    op.drop_table("books")
