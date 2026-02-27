"""bank transactions

Revision ID: 20260227_000009
Revises: 20260227_000008
Create Date: 2026-02-27 00:00:09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000009"
down_revision: Union[str, None] = "20260227_000008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("bank_account_id", sa.BigInteger, nullable=False),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("summary", sa.String(255), nullable=True),
        sa.Column("counterparty", sa.String(255), nullable=True),
        sa.Column("balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("serial_no", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(16), nullable=False, server_default=sa.text("'CNY'")),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("import_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_unique_constraint(
        "uq_bank_transactions_hash", "bank_transactions", ["import_hash"]
    )
    op.create_index(
        "ix_bank_transactions_book_account", "bank_transactions", ["book_id", "bank_account_id"]
    )
    op.create_index("ix_bank_transactions_date", "bank_transactions", ["txn_date"])


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_date", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_book_account", table_name="bank_transactions")
    op.drop_constraint("uq_bank_transactions_hash", "bank_transactions", type_="unique")
    op.drop_table("bank_transactions")
