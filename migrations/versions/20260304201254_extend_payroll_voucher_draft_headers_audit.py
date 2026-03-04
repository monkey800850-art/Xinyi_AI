"""PAYROLL-AUDIT-01: extend payroll voucher draft headers with audit fields"""

from alembic import op
import sqlalchemy as sa

revision = None
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payroll_voucher_draft_headers") as b:
        b.add_column(sa.Column("generated_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("generated_by", sa.String(length=64), nullable=True))
        b.add_column(sa.Column("source_snapshot_json", sa.Text(), nullable=True))
        b.add_column(sa.Column("fingerprint", sa.String(length=64), nullable=True))
    op.create_index("ix_payroll_vdh_fp", "payroll_voucher_draft_headers", ["fingerprint"], unique=False)


def downgrade():
    op.drop_index("ix_payroll_vdh_fp", table_name="payroll_voucher_draft_headers")
    with op.batch_alter_table("payroll_voucher_draft_headers") as b:
        b.drop_column("fingerprint")
        b.drop_column("source_snapshot_json")
        b.drop_column("generated_by")
        b.drop_column("generated_at")
