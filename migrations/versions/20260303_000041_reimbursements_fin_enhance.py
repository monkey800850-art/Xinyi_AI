"""reimbursements finance enhance

Revision ID: 20260303_000041
Revises: 20260303_000040
Create Date: 2026-03-03 12:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000041"
down_revision: Union[str, None] = "20260303_000040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "reimbursements", "budget_check"):
        op.add_column("reimbursements", sa.Column("budget_check", sa.SmallInteger, nullable=False, server_default=sa.text("0")))
    if not _column_exists(bind, "reimbursements", "attachment_check"):
        op.add_column("reimbursements", sa.Column("attachment_check", sa.SmallInteger, nullable=False, server_default=sa.text("0")))
    if not _column_exists(bind, "reimbursements", "approval_sla"):
        op.add_column("reimbursements", sa.Column("approval_sla", sa.DateTime, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "reimbursements", "approval_sla"):
        op.drop_column("reimbursements", "approval_sla")
    if _column_exists(bind, "reimbursements", "attachment_check"):
        op.drop_column("reimbursements", "attachment_check")
    if _column_exists(bind, "reimbursements", "budget_check"):
        op.drop_column("reimbursements", "budget_check")
