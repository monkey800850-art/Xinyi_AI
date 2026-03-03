"""
20260303_000034_consolidation_acquisition_events

Create acquisition events table for purchase method draft generation.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000034"
down_revision: Union[str, None] = "20260302_000033"
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
            CREATE TABLE IF NOT EXISTS consolidation_acquisition_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                acquiree_book_id BIGINT NOT NULL DEFAULT 0,
                acquiree_entity_id BIGINT NOT NULL DEFAULT 0,
                acquisition_date DATE NOT NULL,
                consideration_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                acquired_pct DECIMAL(9,6) NOT NULL DEFAULT 0,
                fv_net_assets DECIMAL(18,2) NOT NULL DEFAULT 0,
                fv_adjustments_json JSON NULL,
                deferred_tax_json JSON NULL,
                notes VARCHAR(255) NULL,
                created_by BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by BIGINT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_conso_acq_event_identity (group_id, acquisition_date, acquiree_book_id, acquiree_entity_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    if not _index_exists(conn, "consolidation_acquisition_events", "ix_conso_acq_event_group_date"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_acq_event_group_date
                ON consolidation_acquisition_events (group_id, acquisition_date)
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "consolidation_acquisition_events", "ix_conso_acq_event_group_date"):
        conn.execute(text("DROP INDEX ix_conso_acq_event_group_date ON consolidation_acquisition_events"))
    conn.execute(text("DROP TABLE IF EXISTS consolidation_acquisition_events"))
