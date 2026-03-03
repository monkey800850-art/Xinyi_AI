"""
20260303_000038_consolidation_adjustments_up_balance_fields

Add generic UP balance and tax tracking fields on consolidation_adjustments.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000038"
down_revision: Union[str, None] = "20260303_000037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name=:table_name
              AND column_name=:column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return int(row.cnt or 0) > 0


def upgrade() -> None:
    conn = op.get_bind()
    alter_list = [
        ("original_amount", "DECIMAL(18,2) NULL"),
        ("remaining_amount", "DECIMAL(18,2) NULL"),
        ("origin_period_start", "DATE NULL"),
        ("origin_period_end", "DATE NULL"),
        ("original_tax_amount", "DECIMAL(18,2) NULL"),
        ("remaining_tax_amount", "DECIMAL(18,2) NULL"),
        ("tax_rate_snapshot", "DECIMAL(9,6) NULL"),
    ]
    for col, ddl in alter_list:
        if not _has_column(conn, "consolidation_adjustments", col):
            conn.execute(text(f"ALTER TABLE consolidation_adjustments ADD COLUMN {col} {ddl}"))


def downgrade() -> None:
    conn = op.get_bind()
    for col in [
        "tax_rate_snapshot",
        "remaining_tax_amount",
        "original_tax_amount",
        "origin_period_end",
        "origin_period_start",
        "remaining_amount",
        "original_amount",
    ]:
        if _has_column(conn, "consolidation_adjustments", col):
            conn.execute(text(f"ALTER TABLE consolidation_adjustments DROP COLUMN {col}"))
