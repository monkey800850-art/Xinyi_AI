"""PAYROLL-BIZ-02: create payroll voucher drafts table"""

from alembic import op
import sqlalchemy as sa

revision = None
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payroll_voucher_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("voucher_type", sa.String(length=32), nullable=True),  # accrual/payment
        sa.Column("status", sa.String(length=32), nullable=True),        # draft

        sa.Column("total_debit", sa.Numeric(18,2), nullable=True),
        sa.Column("total_credit", sa.Numeric(18,2), nullable=True),

        # Minimal mapping placeholders (later link to chart of accounts)
        sa.Column("accounting_policy_json", sa.Text(), nullable=True),   # mapping snapshot
        sa.Column("lines_json", sa.Text(), nullable=True),               # voucher lines as json

        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_voucher_drafts_run_id", "payroll_voucher_drafts", ["run_id"], unique=False)
    op.create_index("ix_payroll_voucher_drafts_type", "payroll_voucher_drafts", ["voucher_type"], unique=False)


def downgrade():
    op.drop_index("ix_payroll_voucher_drafts_type", table_name="payroll_voucher_drafts")
    op.drop_index("ix_payroll_voucher_drafts_run_id", table_name="payroll_voucher_drafts")
    op.drop_table("payroll_voucher_drafts")
