"""create consolidation_authorizations table

Revision ID: 20260302_000025
Revises: 20260301_000024
Create Date: 2026-03-02 00:00:25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_000025"
down_revision: Union[str, None] = "20260301_000021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).fetchone()
    return bool(row)


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
              AND index_name = :index_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "index_name": index_name},
    ).fetchone()
    return bool(row)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "consolidation_authorizations"):
        op.create_table(
            "consolidation_authorizations",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("virtual_subject_id", sa.BigInteger, nullable=False),
            sa.Column("approval_document_number", sa.String(255), nullable=False),
            sa.Column("approval_document_name", sa.String(255), nullable=False),
            sa.Column("effective_start", sa.Date, nullable=False),
            sa.Column("effective_end", sa.Date, nullable=False),
            sa.Column(
                "status",
                sa.Enum("active", "suspended", "revoked", name="enum_consolidation_authorization_status"),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            sa.Column("operator_id", sa.BigInteger, nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(conn, "consolidation_authorizations", "ix_conso_auth_virtual_period"):
        op.create_index(
            "ix_conso_auth_virtual_period",
            "consolidation_authorizations",
            ["virtual_subject_id", "status", "effective_start", "effective_end"],
        )


def downgrade() -> None:
    op.drop_index("ix_conso_auth_virtual_period", table_name="consolidation_authorizations")
    op.drop_table("consolidation_authorizations")
