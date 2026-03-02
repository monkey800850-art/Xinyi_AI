"""
20260302_000030_consolidation_ownership

Create consolidation_ownership table with period and identity indexes.
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
            CREATE TABLE IF NOT EXISTS consolidation_ownership (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                group_id BIGINT NOT NULL,
                parent_entity_id BIGINT NOT NULL,
                child_entity_id BIGINT NOT NULL,
                ownership_pct DECIMAL(9,6) NOT NULL,
                effective_from DATE NOT NULL,
                effective_to DATE NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'active',
                is_enabled TINYINT NOT NULL DEFAULT 1,
                operator_id BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    if not _index_exists(conn, "consolidation_ownership", "ix_conso_ownership_group_asof"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_ownership_group_asof
                ON consolidation_ownership (group_id, effective_from, effective_to)
                """
            )
        )
    if not _index_exists(conn, "consolidation_ownership", "ix_conso_ownership_identity"):
        conn.execute(
            text(
                """
                CREATE INDEX ix_conso_ownership_identity
                ON consolidation_ownership (group_id, parent_entity_id, child_entity_id)
                """
            )
        )


def downgrade(conn):
    if _index_exists(conn, "consolidation_ownership", "ix_conso_ownership_identity"):
        conn.execute(text("DROP INDEX ix_conso_ownership_identity ON consolidation_ownership"))
    if _index_exists(conn, "consolidation_ownership", "ix_conso_ownership_group_asof"):
        conn.execute(text("DROP INDEX ix_conso_ownership_group_asof ON consolidation_ownership"))
    conn.execute(text("DROP TABLE IF EXISTS consolidation_ownership"))
