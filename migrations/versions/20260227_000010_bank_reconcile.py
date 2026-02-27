"""bank reconcile

Revision ID: 20260227_000010
Revises: 20260227_000009
Create Date: 2026-02-27 00:00:10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000010"
down_revision: Union[str, None] = "20260227_000009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.add_column("bank_transactions", sa.Column("match_status", sa.String(16), nullable=False, server_default=sa.text("'unmatched'")))
    op.add_column("bank_transactions", sa.Column("matched_voucher_id", sa.BigInteger, nullable=True))

    op.create_table(
        "bank_reconciliations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("bank_transaction_id", sa.BigInteger, nullable=False),
        sa.Column("voucher_id", sa.BigInteger, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("match_score", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("match_reason", sa.String(255), nullable=True),
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
    op.create_unique_constraint(
        "uq_bank_reconcile_txn", "bank_reconciliations", ["bank_transaction_id"]
    )
    op.create_index(
        "ix_bank_reconcile_status", "bank_reconciliations", ["status"]
    )

    op.create_table(
        "bank_reconciliation_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("bank_transaction_id", sa.BigInteger, nullable=False),
        sa.Column("voucher_id", sa.BigInteger, nullable=True),
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
    op.create_index(
        "ix_bank_reconcile_logs_txn", "bank_reconciliation_logs", ["bank_transaction_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_bank_reconcile_logs_txn", table_name="bank_reconciliation_logs")
    op.drop_table("bank_reconciliation_logs")

    op.drop_index("ix_bank_reconcile_status", table_name="bank_reconciliations")
    op.drop_constraint("uq_bank_reconcile_txn", "bank_reconciliations", type_="unique")
    op.drop_table("bank_reconciliations")

    op.drop_column("bank_transactions", "matched_voucher_id")
    op.drop_column("bank_transactions", "match_status")
