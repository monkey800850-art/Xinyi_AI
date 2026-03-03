"""payroll payment link fields

Revision ID: 20260303_000043
Revises: 20260303_000042
Create Date: 2026-03-03 13:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000043"
down_revision: Union[str, None] = "20260303_000042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "payroll_slips", "payment_status"):
        op.add_column("payroll_slips", sa.Column("payment_status", sa.String(16), nullable=False, server_default=sa.text("'unpaid'")))
    if not _column_exists(bind, "payroll_slips", "payment_request_id"):
        op.add_column("payroll_slips", sa.Column("payment_request_id", sa.BigInteger, nullable=True))
    if not _column_exists(bind, "payroll_slips", "paid_at"):
        op.add_column("payroll_slips", sa.Column("paid_at", sa.DateTime, nullable=True))
    if not _index_exists(bind, "payroll_slips", "ix_payroll_slips_payment_status"):
        op.create_index("ix_payroll_slips_payment_status", "payroll_slips", ["payment_status"])


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "payroll_slips", "ix_payroll_slips_payment_status"):
        op.drop_index("ix_payroll_slips_payment_status", table_name="payroll_slips")
    if _column_exists(bind, "payroll_slips", "paid_at"):
        op.drop_column("payroll_slips", "paid_at")
    if _column_exists(bind, "payroll_slips", "payment_request_id"):
        op.drop_column("payroll_slips", "payment_request_id")
    if _column_exists(bind, "payroll_slips", "payment_status"):
        op.drop_column("payroll_slips", "payment_status")
