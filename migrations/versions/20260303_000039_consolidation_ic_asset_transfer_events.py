"""
20260303_000039_consolidation_ic_asset_transfer_events

Create intercompany asset transfer event table for onboarding elimination.
"""

from sqlalchemy import text


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


def upgrade(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS consolidation_ic_asset_transfer_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                as_of_date DATE NOT NULL,
                asset_class VARCHAR(32) NOT NULL,
                seller_book_id BIGINT NOT NULL,
                buyer_book_id BIGINT NOT NULL,
                asset_ref VARCHAR(128) NOT NULL,
                transfer_price DECIMAL(18,2) NOT NULL DEFAULT 0,
                carrying_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                tax_rate_snapshot DECIMAL(9,6) NOT NULL DEFAULT 0.25,
                dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                original_gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                remaining_gain_loss_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                original_dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                remaining_dtl_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                note VARCHAR(255) NULL,
                created_by BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by BIGINT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_ic_asset_transfer_identity (group_id, as_of_date, asset_class, seller_book_id, buyer_book_id, asset_ref)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    if not _index_exists(conn, "consolidation_ic_asset_transfer_events", "ix_ic_asset_transfer_group_date"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_ic_asset_transfer_group_date
                ON consolidation_ic_asset_transfer_events (group_id, as_of_date)
                """
            )
        )


def downgrade(conn):
    if _index_exists(conn, "consolidation_ic_asset_transfer_events", "ix_ic_asset_transfer_group_date"):
        conn.execute(text("DROP INDEX ix_ic_asset_transfer_group_date ON consolidation_ic_asset_transfer_events"))
    conn.execute(text("DROP TABLE IF EXISTS consolidation_ic_asset_transfer_events"))
