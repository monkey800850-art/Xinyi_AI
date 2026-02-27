"""tax module

Revision ID: 20260227_000011
Revises: 20260227_000010
Create Date: 2026-02-27 00:00:11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000011"
down_revision: Union[str, None] = "20260227_000010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "tax_rules",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("tax_type", sa.String(32), nullable=False),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("reduction_type", sa.String(32), nullable=True),
        sa.Column("reduction_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column("effective_to", sa.Date, nullable=True),
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
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_tax_rules_region_type", "tax_rules", ["region", "tax_type"])

    op.create_table(
        "tax_invoices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("invoice_code", sa.String(64), nullable=True),
        sa.Column("invoice_no", sa.String(64), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("seller_name", sa.String(128), nullable=True),
        sa.Column("buyer_name", sa.String(128), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
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
    op.create_unique_constraint("uq_tax_invoices_hash", "tax_invoices", ["import_hash"])
    op.create_index("ix_tax_invoices_book_date", "tax_invoices", ["book_id", "invoice_date"])

    op.create_table(
        "tax_alerts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.String(255), nullable=False),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_tax_alerts_book", "tax_alerts", ["book_id", "alert_type"])


def downgrade() -> None:
    op.drop_index("ix_tax_alerts_book", table_name="tax_alerts")
    op.drop_table("tax_alerts")

    op.drop_index("ix_tax_invoices_book_date", table_name="tax_invoices")
    op.drop_constraint("uq_tax_invoices_hash", "tax_invoices", type_="unique")
    op.drop_table("tax_invoices")

    op.drop_index("ix_tax_rules_region_type", table_name="tax_rules")
    op.drop_table("tax_rules")
