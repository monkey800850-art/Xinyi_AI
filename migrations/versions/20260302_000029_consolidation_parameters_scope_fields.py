"""
20260302_000029_consolidation_parameters_scope_fields

Add method/scope/effective_from fields to consolidation_parameters.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000029"
down_revision: Union[str, None] = "20260302_000028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    row = conn.execute(
        text(
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
    conn = op.get_bind()
    if not _has_column(conn, "consolidation_parameters", "consolidation_method"):
        conn.execute(
            text(
                """
                ALTER TABLE consolidation_parameters
                ADD COLUMN consolidation_method VARCHAR(16) NOT NULL DEFAULT 'full'
                """
            )
        )
    if not _has_column(conn, "consolidation_parameters", "default_scope"):
        conn.execute(
            text(
                """
                ALTER TABLE consolidation_parameters
                ADD COLUMN default_scope VARCHAR(16) NOT NULL DEFAULT 'raw'
                """
            )
        )
    if not _has_column(conn, "consolidation_parameters", "effective_from"):
        conn.execute(
            text(
                """
                ALTER TABLE consolidation_parameters
                ADD COLUMN effective_from DATE NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE consolidation_parameters
                SET effective_from = COALESCE(effective_start, '2000-01-01')
                WHERE effective_from IS NULL
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "consolidation_parameters", "effective_from"):
        conn.execute(text("ALTER TABLE consolidation_parameters DROP COLUMN effective_from"))
    if _has_column(conn, "consolidation_parameters", "default_scope"):
        conn.execute(text("ALTER TABLE consolidation_parameters DROP COLUMN default_scope"))
    if _has_column(conn, "consolidation_parameters", "consolidation_method"):
        conn.execute(text("ALTER TABLE consolidation_parameters DROP COLUMN consolidation_method"))
