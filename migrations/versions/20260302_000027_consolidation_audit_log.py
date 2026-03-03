"""
20260302_000027_consolidation_audit_log

Create minimal consolidation_audit_log table for onboarding and read-gate audits.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000027"
down_revision: Union[str, None] = "20260302_000026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_audit_log (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                operator_id BIGINT NULL,
                action VARCHAR(64) NOT NULL,
                group_id BIGINT NULL,
                payload_json JSON NULL,
                result_status VARCHAR(16) NOT NULL,
                result_code INT NOT NULL,
                note VARCHAR(255) NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS consolidation_audit_log"))
