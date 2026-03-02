"""
20260303_000036_consolidation_parameters_tax_rate

Add tax_rate field to consolidation_parameters for deferred tax calculations.
"""

from sqlalchemy import text


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


def upgrade(conn):
    if not _has_column(conn, "consolidation_parameters", "tax_rate"):
        conn.execute(
            text(
                """
                ALTER TABLE consolidation_parameters
                ADD COLUMN tax_rate DECIMAL(9,6) NULL
                """
            )
        )


def downgrade(conn):
    if _has_column(conn, "consolidation_parameters", "tax_rate"):
        conn.execute(text("ALTER TABLE consolidation_parameters DROP COLUMN tax_rate"))
