"""PAYROLL-BIZ-03: create payroll voucher draft header/lines tables"""

from alembic import op
import sqlalchemy as sa

revision = None
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payroll_voucher_draft_headers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),

        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("voucher_type", sa.String(length=32), nullable=False),  # accrual/payment
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),

        sa.Column("total_debit", sa.Numeric(18,2), nullable=True),
        sa.Column("total_credit", sa.Numeric(18,2), nullable=True),

        sa.Column("policy_json", sa.Text(), nullable=True),   # mapping snapshot
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_vdh_run_id", "payroll_voucher_draft_headers", ["run_id"], unique=False)
    op.create_index("ix_payroll_vdh_type", "payroll_voucher_draft_headers", ["voucher_type"], unique=False)

    op.create_table(
        "payroll_voucher_draft_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("header_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=True),
        sa.Column("dc", sa.String(length=1), nullable=False),               # D/C
        sa.Column("account_code", sa.String(length=64), nullable=True),     # placeholder
        sa.Column("account_name", sa.String(length=128), nullable=True),    # placeholder
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_payroll_vdl_header_id", "payroll_voucher_draft_lines", ["header_id"], unique=False)


def downgrade():
    op.drop_index("ix_payroll_vdl_header_id", table_name="payroll_voucher_draft_lines")
    op.drop_table("payroll_voucher_draft_lines")
    op.drop_index("ix_payroll_vdh_type", table_name="payroll_voucher_draft_headers")
    op.drop_index("ix_payroll_vdh_run_id", table_name="payroll_voucher_draft_headers")
    op.drop_table("payroll_voucher_draft_headers")
