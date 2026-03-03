"""asset enhancements for impairment/disposal/inventory/revaluation and draft journals

Revision ID: 20260303_000046
Revises: 20260303_000045
Create Date: 2026-03-03 22:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000046"
down_revision: Union[str, None] = "20260303_000045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


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

    if not _table_exists(bind, "asset_impairments"):
        op.create_table(
            "asset_impairments",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("asset_id", sa.BigInteger, nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("impairment_date", sa.Date, nullable=False),
            sa.Column("book_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("current_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("impairment_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("reason", sa.String(255), nullable=True),
            sa.Column("evidence_ref", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_impairments", "ix_asset_impairments_book_date"):
        op.create_index("ix_asset_impairments_book_date", "asset_impairments", ["book_id", "impairment_date"])

    if not _table_exists(bind, "asset_disposals"):
        op.create_table(
            "asset_disposals",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("asset_id", sa.BigInteger, nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("disposal_date", sa.Date, nullable=False),
            sa.Column("disposal_method", sa.String(16), nullable=False),
            sa.Column("disposal_income", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("disposal_cost", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("book_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("gain_loss", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_disposals", "ix_asset_disposals_book_date"):
        op.create_index("ix_asset_disposals_book_date", "asset_disposals", ["book_id", "disposal_date"])

    if not _table_exists(bind, "asset_inventory_checks"):
        op.create_table(
            "asset_inventory_checks",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("check_date", sa.Date, nullable=False),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_inventory_checks", "ix_asset_inventory_checks_book_date"):
        op.create_index("ix_asset_inventory_checks_book_date", "asset_inventory_checks", ["book_id", "check_date"])

    if not _table_exists(bind, "asset_inventory_check_lines"):
        op.create_table(
            "asset_inventory_check_lines",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("check_id", sa.BigInteger, nullable=False),
            sa.Column("asset_id", sa.BigInteger, nullable=False),
            sa.Column("is_found", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("discrepancy_reason", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_inventory_check_lines", "ix_asset_inventory_check_lines_check"):
        op.create_index("ix_asset_inventory_check_lines_check", "asset_inventory_check_lines", ["check_id"])

    if not _table_exists(bind, "asset_revaluations"):
        op.create_table(
            "asset_revaluations",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("asset_id", sa.BigInteger, nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("revaluation_date", sa.Date, nullable=False),
            sa.Column("old_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("new_value", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("delta_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("reason", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_revaluations", "ix_asset_revaluations_book_date"):
        op.create_index("ix_asset_revaluations_book_date", "asset_revaluations", ["book_id", "revaluation_date"])

    if not _table_exists(bind, "asset_journal_drafts"):
        op.create_table(
            "asset_journal_drafts",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("asset_id", sa.BigInteger, nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("rule_code", sa.String(64), nullable=False),
            sa.Column("reference_id", sa.BigInteger, nullable=True),
            sa.Column("debit_subject_code", sa.String(64), nullable=False),
            sa.Column("credit_subject_code", sa.String(64), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "asset_journal_drafts", "ix_asset_journal_drafts_book_action"):
        op.create_index("ix_asset_journal_drafts_book_action", "asset_journal_drafts", ["book_id", "action"])


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "asset_journal_drafts"):
        if _index_exists(bind, "asset_journal_drafts", "ix_asset_journal_drafts_book_action"):
            op.drop_index("ix_asset_journal_drafts_book_action", table_name="asset_journal_drafts")
        op.drop_table("asset_journal_drafts")

    if _table_exists(bind, "asset_revaluations"):
        if _index_exists(bind, "asset_revaluations", "ix_asset_revaluations_book_date"):
            op.drop_index("ix_asset_revaluations_book_date", table_name="asset_revaluations")
        op.drop_table("asset_revaluations")

    if _table_exists(bind, "asset_inventory_check_lines"):
        if _index_exists(bind, "asset_inventory_check_lines", "ix_asset_inventory_check_lines_check"):
            op.drop_index("ix_asset_inventory_check_lines_check", table_name="asset_inventory_check_lines")
        op.drop_table("asset_inventory_check_lines")

    if _table_exists(bind, "asset_inventory_checks"):
        if _index_exists(bind, "asset_inventory_checks", "ix_asset_inventory_checks_book_date"):
            op.drop_index("ix_asset_inventory_checks_book_date", table_name="asset_inventory_checks")
        op.drop_table("asset_inventory_checks")

    if _table_exists(bind, "asset_disposals"):
        if _index_exists(bind, "asset_disposals", "ix_asset_disposals_book_date"):
            op.drop_index("ix_asset_disposals_book_date", table_name="asset_disposals")
        op.drop_table("asset_disposals")

    if _table_exists(bind, "asset_impairments"):
        if _index_exists(bind, "asset_impairments", "ix_asset_impairments_book_date"):
            op.drop_index("ix_asset_impairments_book_date", table_name="asset_impairments")
        op.drop_table("asset_impairments")
