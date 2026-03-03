"""
20260303_000036_consolidation_parameters_tax_rate

Add tax_rate field to consolidation_parameters for deferred tax calculations.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000036"
down_revision: Union[str, None] = "20260303_000035"
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
    if not _has_column(conn, "consolidation_parameters", "tax_rate"):
        conn.execute(
            text(
                """
                ALTER TABLE consolidation_parameters
                ADD COLUMN tax_rate DECIMAL(9,6) NULL
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "consolidation_parameters", "tax_rate"):
        conn.execute(text("ALTER TABLE consolidation_parameters DROP COLUMN tax_rate"))
