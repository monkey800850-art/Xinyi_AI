"""perf index tuning for top sql

Revision ID: 20260303_000049
Revises: 20260303_000048
Create Date: 2026-03-03 23:58:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000049"
down_revision: Union[str, None] = "20260303_000048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
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


def _column_exists(bind, table_name: str, column_name: str) -> bool:
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


def _index_exists(bind, table_name: str, index_name: str) -> bool:
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


def _create_index_if_missing(bind, table_name: str, index_name: str, columns: list[str]) -> None:
    if _table_exists(bind, table_name) and not _index_exists(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if _table_exists(bind, table_name) and _index_exists(bind, table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    _create_index_if_missing(bind, "reimbursements", "ix_reimbursements_book_id_id", ["book_id", "id"])
    _create_index_if_missing(bind, "payment_requests", "ix_payment_requests_book_id_id", ["book_id", "id"])
    _create_index_if_missing(bind, "bank_transactions", "ix_bank_transactions_book_match_id", ["book_id", "match_status", "id"])
    _create_index_if_missing(bind, "consolidation_adjustments", "ix_conso_adj_group_period_id", ["group_id", "period", "id"])
    _create_index_if_missing(
        bind, "consolidation_adjustments", "ix_conso_adj_group_period_batch", ["group_id", "period", "batch_id"]
    )
    _create_index_if_missing(bind, "vouchers", "ix_vouchers_book_status_date_id", ["book_id", "status", "voucher_date", "id"])

    if (
        _table_exists(bind, "tax_invoices")
        and _column_exists(bind, "tax_invoices", "book_id")
        and _column_exists(bind, "tax_invoices", "verification_status")
        and not _index_exists(bind, "tax_invoices", "ix_tax_invoices_book_verify")
    ):
        op.create_index("ix_tax_invoices_book_verify", "tax_invoices", ["book_id", "verification_status"])


def downgrade() -> None:
    bind = op.get_bind()
    _drop_index_if_exists(bind, "tax_invoices", "ix_tax_invoices_book_verify")
    _drop_index_if_exists(bind, "vouchers", "ix_vouchers_book_status_date_id")
    _drop_index_if_exists(bind, "consolidation_adjustments", "ix_conso_adj_group_period_batch")
    _drop_index_if_exists(bind, "consolidation_adjustments", "ix_conso_adj_group_period_id")
    _drop_index_if_exists(bind, "bank_transactions", "ix_bank_transactions_book_match_id")
    _drop_index_if_exists(bind, "payment_requests", "ix_payment_requests_book_id_id")
    _drop_index_if_exists(bind, "reimbursements", "ix_reimbursements_book_id_id")
