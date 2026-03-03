"""tax enhancements: invoice verification, diff ledger, declaration mappings

Revision ID: 20260303_000045
Revises: 20260303_000044
Create Date: 2026-03-03 18:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000045"
down_revision: Union[str, None] = "20260303_000044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    try:
        row = bind.execute(
            sa.text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).fetchone()
        return int(row.cnt or 0) > 0
    except Exception:
        rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
        names = {str(getattr(r, "name", r[1]) or "").strip().lower() for r in rows}
        return column_name.lower() in names


def _table_exists(bind, table_name: str) -> bool:
    try:
        row = bind.execute(
            sa.text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchone()
        return int(row.cnt or 0) > 0
    except Exception:
        row = bind.execute(
            sa.text(
                """
                SELECT COUNT(*) AS cnt
                FROM sqlite_master
                WHERE type='table' AND name=:table_name
                """
            ),
            {"table_name": table_name},
        ).fetchone()
        return int(getattr(row, "cnt", 0) or 0) > 0


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    try:
        row = bind.execute(
            sa.text(
                """
                SELECT COUNT(*) AS cnt
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = :table_name
                  AND index_name = :index_name
                """
            ),
            {"table_name": table_name, "index_name": index_name},
        ).fetchone()
        return int(row.cnt or 0) > 0
    except Exception:
        rows = bind.execute(sa.text(f"PRAGMA index_list({table_name})")).fetchall()
        names = {str(getattr(r, "name", r[1]) or "").strip().lower() for r in rows}
        return index_name.lower() in names


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "tax_invoices", "verification_status"):
        op.add_column("tax_invoices", sa.Column("verification_status", sa.String(16), nullable=False, server_default=sa.text("'pending'")))
    if not _column_exists(bind, "tax_invoices", "verification_message"):
        op.add_column("tax_invoices", sa.Column("verification_message", sa.String(255), nullable=True))
    if not _column_exists(bind, "tax_invoices", "verified_at"):
        op.add_column("tax_invoices", sa.Column("verified_at", sa.DateTime, nullable=True))

    if not _table_exists(bind, "tax_difference_ledger"):
        op.create_table(
            "tax_difference_ledger",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("period", sa.String(7), nullable=False),
            sa.Column("tax_subject", sa.String(64), nullable=False),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("accounting_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("diff_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("reason_code", sa.String(32), nullable=True),
            sa.Column("remark", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "tax_difference_ledger", "ix_tax_diff_book_period"):
        op.create_index("ix_tax_diff_book_period", "tax_difference_ledger", ["book_id", "period"])

    if not _table_exists(bind, "tax_declaration_mappings"):
        op.create_table(
            "tax_declaration_mappings",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("declaration_code", sa.String(32), nullable=False),
            sa.Column("worksheet_cell", sa.String(32), nullable=False),
            sa.Column("source_type", sa.String(32), nullable=False),
            sa.Column("source_key", sa.String(64), nullable=False),
            sa.Column("expression", sa.String(255), nullable=True),
            sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "tax_declaration_mappings", "ix_tax_decl_map_book_decl"):
        op.create_index("ix_tax_decl_map_book_decl", "tax_declaration_mappings", ["book_id", "declaration_code", "is_enabled"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "tax_declaration_mappings", "ix_tax_decl_map_book_decl"):
        op.drop_index("ix_tax_decl_map_book_decl", table_name="tax_declaration_mappings")
    if _table_exists(bind, "tax_declaration_mappings"):
        op.drop_table("tax_declaration_mappings")

    if _index_exists(bind, "tax_difference_ledger", "ix_tax_diff_book_period"):
        op.drop_index("ix_tax_diff_book_period", table_name="tax_difference_ledger")
    if _table_exists(bind, "tax_difference_ledger"):
        op.drop_table("tax_difference_ledger")

    if _column_exists(bind, "tax_invoices", "verified_at"):
        op.drop_column("tax_invoices", "verified_at")
    if _column_exists(bind, "tax_invoices", "verification_message"):
        op.drop_column("tax_invoices", "verification_message")
    if _column_exists(bind, "tax_invoices", "verification_status"):
        op.drop_column("tax_invoices", "verification_status")
