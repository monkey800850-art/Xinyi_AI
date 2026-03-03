"""payroll enhancements for cumulative tax, regional policy, masking and disbursement batch

Revision ID: 20260303_000044
Revises: 20260303_000043
Create Date: 2026-03-03 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000044"
down_revision: Union[str, None] = "20260303_000043"
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


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "payroll_slips", "city"):
        op.add_column("payroll_slips", sa.Column("city", sa.String(64), nullable=True))
    if not _column_exists(bind, "payroll_slips", "bank_account"):
        op.add_column("payroll_slips", sa.Column("bank_account", sa.String(128), nullable=True))
    if not _column_exists(bind, "payroll_slips", "tax_method"):
        op.add_column("payroll_slips", sa.Column("tax_method", sa.String(16), nullable=False, server_default=sa.text("'cumulative'")))
    if not _column_exists(bind, "payroll_slips", "ytd_taxable_base"):
        op.add_column("payroll_slips", sa.Column("ytd_taxable_base", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")))
    if not _column_exists(bind, "payroll_slips", "ytd_tax_withheld"):
        op.add_column("payroll_slips", sa.Column("ytd_tax_withheld", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")))

    if not _index_exists(bind, "payroll_slips", "ix_payroll_slips_book_employee_period"):
        op.create_index("ix_payroll_slips_book_employee_period", "payroll_slips", ["book_id", "employee_id", "period"])

    if not _table_exists(bind, "payroll_region_policies"):
        op.create_table(
            "payroll_region_policies",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("city", sa.String(64), nullable=False),
            sa.Column("social_rate", sa.Numeric(10, 6), nullable=False, server_default=sa.text("0")),
            sa.Column("housing_rate", sa.Numeric(10, 6), nullable=False, server_default=sa.text("0")),
            sa.Column("social_base_min", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("social_base_max", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("housing_base_min", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("housing_base_max", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("book_id", "city", name="uq_payroll_region_policy_book_city"),
            **MYSQL_TABLE_ARGS,
        )
        op.create_index("ix_payroll_region_policy_book_status", "payroll_region_policies", ["book_id", "status"])

    if not _table_exists(bind, "payroll_disbursement_batches"):
        op.create_table(
            "payroll_disbursement_batches",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("book_id", sa.BigInteger, nullable=False),
            sa.Column("period", sa.String(7), nullable=False),
            sa.Column("batch_no", sa.String(32), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("total_count", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("book_id", "batch_no", name="uq_payroll_disb_book_batch_no"),
            **MYSQL_TABLE_ARGS,
        )
        op.create_index("ix_payroll_disb_batch_book_period", "payroll_disbursement_batches", ["book_id", "period"])

    if not _table_exists(bind, "payroll_disbursement_batch_items"):
        op.create_table(
            "payroll_disbursement_batch_items",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.BigInteger, nullable=False),
            sa.Column("slip_id", sa.BigInteger, nullable=False),
            sa.Column("employee_id", sa.BigInteger, nullable=False),
            sa.Column("employee_name", sa.String(64), nullable=True),
            sa.Column("bank_account", sa.String(128), nullable=False),
            sa.Column("pay_amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("batch_id", "slip_id", name="uq_payroll_disb_item_batch_slip"),
            **MYSQL_TABLE_ARGS,
        )
        op.create_index("ix_payroll_disb_items_batch", "payroll_disbursement_batch_items", ["batch_id"])


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "payroll_disbursement_batch_items"):
        if _index_exists(bind, "payroll_disbursement_batch_items", "ix_payroll_disb_items_batch"):
            op.drop_index("ix_payroll_disb_items_batch", table_name="payroll_disbursement_batch_items")
        op.drop_table("payroll_disbursement_batch_items")

    if _table_exists(bind, "payroll_disbursement_batches"):
        if _index_exists(bind, "payroll_disbursement_batches", "ix_payroll_disb_batch_book_period"):
            op.drop_index("ix_payroll_disb_batch_book_period", table_name="payroll_disbursement_batches")
        op.drop_table("payroll_disbursement_batches")

    if _table_exists(bind, "payroll_region_policies"):
        if _index_exists(bind, "payroll_region_policies", "ix_payroll_region_policy_book_status"):
            op.drop_index("ix_payroll_region_policy_book_status", table_name="payroll_region_policies")
        op.drop_table("payroll_region_policies")

    if _index_exists(bind, "payroll_slips", "ix_payroll_slips_book_employee_period"):
        op.drop_index("ix_payroll_slips_book_employee_period", table_name="payroll_slips")
    if _column_exists(bind, "payroll_slips", "ytd_tax_withheld"):
        op.drop_column("payroll_slips", "ytd_tax_withheld")
    if _column_exists(bind, "payroll_slips", "ytd_taxable_base"):
        op.drop_column("payroll_slips", "ytd_taxable_base")
    if _column_exists(bind, "payroll_slips", "tax_method"):
        op.drop_column("payroll_slips", "tax_method")
    if _column_exists(bind, "payroll_slips", "bank_account"):
        op.drop_column("payroll_slips", "bank_account")
    if _column_exists(bind, "payroll_slips", "city"):
        op.drop_column("payroll_slips", "city")
