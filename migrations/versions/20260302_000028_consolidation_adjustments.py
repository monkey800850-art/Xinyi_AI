"""
20260302_000028_consolidation_adjustments

Create consolidation_adjustments table for manual elimination entries.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000028"
down_revision: Union[str, None] = "20260302_000027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_adjustments (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                period VARCHAR(7) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'active',
                operator_id BIGINT NOT NULL,
                lines_json JSON NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS consolidation_adjustments"))
