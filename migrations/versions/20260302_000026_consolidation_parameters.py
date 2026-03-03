"""
20260302_000026_consolidation_parameters

Create consolidation_parameters table (ownership/control/include scope).
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260302_000026"
down_revision: Union[str, None] = "20260302_000025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS consolidation_parameters (
            id INT AUTO_INCREMENT PRIMARY KEY,
            virtual_subject_id INT NOT NULL,

            parent_subject_type VARCHAR(32) NOT NULL,
            parent_subject_id INT NOT NULL,
            child_subject_type VARCHAR(32) NOT NULL,
            child_subject_id INT NOT NULL,

            ownership_ratio DECIMAL(9,6) NOT NULL DEFAULT 0,
            control_type VARCHAR(32) NOT NULL DEFAULT 'control',
            include_in_consolidation TINYINT NOT NULL DEFAULT 1,

            effective_start DATE NOT NULL,
            effective_end DATE NOT NULL,

            status VARCHAR(32) NOT NULL DEFAULT 'active',
            operator_id INT NOT NULL,

            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP TABLE IF EXISTS consolidation_parameters"))
