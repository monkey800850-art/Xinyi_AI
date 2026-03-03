"""
20260302_000031_consolidation_adjustments_generated_fields

Add generated-draft metadata fields for consolidation_adjustments.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000031"
down_revision: Union[str, None] = "20260302_000030"
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
    if not _has_column(conn, "consolidation_adjustments", "source"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN source VARCHAR(32) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "rule_code"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN rule_code VARCHAR(64) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "evidence_ref"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN evidence_ref VARCHAR(255) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "batch_id"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN batch_id VARCHAR(64) NULL"))
    if not _has_column(conn, "consolidation_adjustments", "tag"):
        conn.execute(text("ALTER TABLE consolidation_adjustments ADD COLUMN tag VARCHAR(64) NULL"))


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "consolidation_adjustments", "tag"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN tag"))
    if _has_column(conn, "consolidation_adjustments", "batch_id"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN batch_id"))
    if _has_column(conn, "consolidation_adjustments", "evidence_ref"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN evidence_ref"))
    if _has_column(conn, "consolidation_adjustments", "rule_code"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN rule_code"))
    if _has_column(conn, "consolidation_adjustments", "source"):
        conn.execute(text("ALTER TABLE consolidation_adjustments DROP COLUMN source"))
