"""
20260303_000037_consolidation_adjustments_up_tracking

Add cross-period unrealized profit tracking fields on consolidation_adjustments.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000037"
down_revision: Union[str, None] = "20260303_000036"
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
    if not _has_column(conn, "consolidation_adjustments", "original_unrealized_profit"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN original_unrealized_profit DECIMAL(18,2) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "remaining_unrealized_profit"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN remaining_unrealized_profit DECIMAL(18,2) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "period_start"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN period_start DATE NULL"))
    if not _has_column(conn, "consolidation_adjustments", "period_end"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN period_end DATE NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "consolidation_adjustments", "period_end"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN period_end"))
    if _has_column(conn, "consolidation_adjustments", "period_start"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN period_start"))
    if _has_column(conn, "consolidation_adjustments", "remaining_unrealized_profit"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN remaining_unrealized_profit"))
    if _has_column(conn, "consolidation_adjustments", "original_unrealized_profit"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN original_unrealized_profit"))
