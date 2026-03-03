"""
20260302_000033_consolidation_group_types

Create consolidation_group_types table for consolidation type contract.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000033"
down_revision: Union[str, None] = "20260302_000032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    row = conn.execute(
        text(
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


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_group_types (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                consolidation_type VARCHAR(32) NOT NULL,
                note VARCHAR(255) NULL,
                created_by BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by BIGINT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_conso_group_types_group (group_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    if not _index_exists(conn, "consolidation_group_types", "ix_conso_group_types_type"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_group_types_type
                ON consolidation_group_types (consolidation_type, updated_at)
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "consolidation_group_types", "ix_conso_group_types_type"):
        conn.execute(text("DROP INDEX ix_conso_group_types_type ON consolidation_group_types"))
    conn.execute(text("DROP TABLE IF EXISTS consolidation_group_types"))
