"""payroll mvp tables

Revision ID: 20260303_000042
Revises: 20260303_000041
Create Date: 2026-03-03 12:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000042"
down_revision: Union[str, None] = "20260303_000041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("locked_by", sa.BigInteger, nullable=True),
        sa.Column("locked_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("book_id", "period", name="uq_payroll_period_book_period"),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_payroll_periods_book_status", "payroll_periods", ["book_id", "status"])

    op.create_table(
        "payroll_slips",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("employee_id", sa.BigInteger, nullable=False),
        sa.Column("employee_name", sa.String(64), nullable=True),
        sa.Column("department", sa.String(64), nullable=True),
        sa.Column("attendance_ref", sa.String(64), nullable=True),
        sa.Column("attendance_days", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("absent_days", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("deduction_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("social_insurance", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("housing_fund", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("bonus_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("overtime_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("taxable_base", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("book_id", "period", "employee_id", name="uq_payroll_slip_employee_period"),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_payroll_slips_book_period_status", "payroll_slips", ["book_id", "period", "status"])

    op.create_table(
        "payroll_tax_ledger",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("employee_id", sa.BigInteger, nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("tax_type", sa.String(32), nullable=False),
        sa.Column("taxable_base", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("calc_version", sa.String(32), nullable=True),
        sa.Column("snapshot_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_payroll_tax_ledger_book_period", "payroll_tax_ledger", ["book_id", "period"])


def downgrade() -> None:
    op.drop_index("ix_payroll_tax_ledger_book_period", table_name="payroll_tax_ledger")
    op.drop_table("payroll_tax_ledger")

    op.drop_index("ix_payroll_slips_book_period_status", table_name="payroll_slips")
    op.drop_table("payroll_slips")

    op.drop_index("ix_payroll_periods_book_status", table_name="payroll_periods")
    op.drop_table("payroll_periods")
