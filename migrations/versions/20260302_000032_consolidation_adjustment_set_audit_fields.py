"""
20260302_000032_consolidation_adjustment_set_audit_fields

Add set-level audit fields for adjustment_set workflow on consolidation_adjustments.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000032"
down_revision: Union[str, None] = "20260302_000031"
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
    if not _has_column(conn, "consolidation_adjustments", "reviewed_by"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_by BIGINT NULL"))
    if not _has_column(conn, "consolidation_adjustments", "reviewed_at"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN reviewed_at DATETIME NULL"))
    if not _has_column(conn, "consolidation_adjustments", "locked_by"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN locked_by BIGINT NULL"))
    if not _has_column(conn, "consolidation_adjustments", "locked_at"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN locked_at DATETIME NULL"))
    if not _has_column(conn, "consolidation_adjustments", "note"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN note VARCHAR(255) NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "consolidation_adjustments", "note"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN note"))
    if _has_column(conn, "consolidation_adjustments", "locked_at"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN locked_at"))
    if _has_column(conn, "consolidation_adjustments", "locked_by"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN locked_by"))
    if _has_column(conn, "consolidation_adjustments", "reviewed_at"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN reviewed_at"))
    if _has_column(conn, "consolidation_adjustments", "reviewed_by"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN reviewed_by"))
