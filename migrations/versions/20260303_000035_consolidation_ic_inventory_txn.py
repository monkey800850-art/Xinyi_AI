"""
20260303_000035_consolidation_ic_inventory_txn

Create consolidation_ic_inventory_txn for inventory unrealized profit elimination engine.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "20260303_000035"
down_revision: Union[str, None] = "20260303_000034"
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
            CREATE TABLE IF NOT EXISTS consolidation_ic_inventory_txn (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                seller_book_id BIGINT NOT NULL,
                buyer_book_id BIGINT NOT NULL,
                doc_no VARCHAR(64) NOT NULL,
                txn_date DATE NOT NULL,
                item_code VARCHAR(64) NOT NULL,
                qty DECIMAL(18,6) NOT NULL DEFAULT 0,
                sales_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                cost_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                ending_inventory_qty DECIMAL(18,6) NOT NULL DEFAULT 0,
                note VARCHAR(255) NULL,
                created_by BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    if not _index_exists(conn, "consolidation_ic_inventory_txn", "ix_conso_ic_inv_group_date"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_ic_inv_group_date
                ON consolidation_ic_inventory_txn (group_id, txn_date)
                """
            )
        )
    if not _index_exists(conn, "consolidation_ic_inventory_txn", "ix_conso_ic_inv_doc"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_ic_inv_doc
                ON consolidation_ic_inventory_txn (group_id, doc_no, item_code)
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _index_exists(conn, "consolidation_ic_inventory_txn", "ix_conso_ic_inv_doc"):
        conn.execute(text("DROP INDEX ix_conso_ic_inv_doc ON consolidation_ic_inventory_txn"))
    if _index_exists(conn, "consolidation_ic_inventory_txn", "ix_conso_ic_inv_group_date"):
        conn.execute(text("DROP INDEX ix_conso_ic_inv_group_date ON consolidation_ic_inventory_txn"))
    conn.execute(text("DROP TABLE IF EXISTS consolidation_ic_inventory_txn"))
