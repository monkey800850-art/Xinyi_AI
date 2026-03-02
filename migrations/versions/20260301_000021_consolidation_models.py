"""consolidation relation models

Revision ID: 20260301_000021
Revises: 20260301_000020
Create Date: 2026-03-01 00:00:21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260301_000021"
down_revision: Union[str, None] = "20260301_000020"
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
    if not _table_exists(conn, "legal_entities"):
        op.create_table(
            "legal_entities",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("entity_code", sa.String(64), nullable=False),
            sa.Column("entity_name", sa.String(128), nullable=False),
            sa.Column("entity_kind", sa.String(16), nullable=False, server_default=sa.text("'legal'")),
            sa.Column("book_id", sa.BigInteger, nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("entity_code", name="uq_legal_entities_code"),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(conn, "legal_entities", "ix_legal_entities_status"):
        op.create_index("ix_legal_entities_status", "legal_entities", ["status", "is_enabled"])
    if not _index_exists(conn, "legal_entities", "ix_legal_entities_book"):
        op.create_index("ix_legal_entities_book", "legal_entities", ["book_id"])

    if not _table_exists(conn, "virtual_entities"):
        op.create_table(
            "virtual_entities",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("virtual_code", sa.String(64), nullable=False),
            sa.Column("virtual_name", sa.String(128), nullable=False),
            sa.Column("book_id", sa.BigInteger, nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("virtual_code", name="uq_virtual_entities_code"),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(conn, "virtual_entities", "ix_virtual_entities_status"):
        op.create_index("ix_virtual_entities_status", "virtual_entities", ["status", "is_enabled"])
    if not _index_exists(conn, "virtual_entities", "ix_virtual_entities_book"):
        op.create_index("ix_virtual_entities_book", "virtual_entities", ["book_id"])

    if not _table_exists(conn, "consolidation_groups"):
        op.create_table(
            "consolidation_groups",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("group_code", sa.String(64), nullable=False),
            sa.Column("group_name", sa.String(128), nullable=False),
            sa.Column("group_type", sa.String(32), nullable=False, server_default=sa.text("'standard'")),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("group_code", name="uq_consolidation_groups_code"),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(conn, "consolidation_groups", "ix_consolidation_groups_status"):
        op.create_index("ix_consolidation_groups_status", "consolidation_groups", ["status", "is_enabled"])

    if not _table_exists(conn, "consolidation_group_members"):
        op.create_table(
            "consolidation_group_members",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("group_id", sa.BigInteger, nullable=False),
            sa.Column("member_book_id", sa.BigInteger, nullable=True),
            sa.Column("member_entity_id", sa.BigInteger, nullable=True),
            sa.Column("member_type", sa.String(16), nullable=False),
            sa.Column("effective_from", sa.Date, nullable=True),
            sa.Column("effective_to", sa.Date, nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "updated_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "group_id",
                "member_type",
                "member_book_id",
                "member_entity_id",
                "effective_from",
                "effective_to",
                name="uq_conso_group_member_period",
            ),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(conn, "consolidation_group_members", "ix_conso_member_group_period"):
        op.create_index(
            "ix_conso_member_group_period",
            "consolidation_group_members",
            ["group_id", "effective_from", "effective_to", "is_enabled"],
        )
    if not _index_exists(conn, "consolidation_group_members", "ix_conso_member_identity"):
        op.create_index(
            "ix_conso_member_identity",
            "consolidation_group_members",
            ["group_id", "member_type", "member_book_id", "member_entity_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_conso_member_identity", table_name="consolidation_group_members")
    op.drop_index("ix_conso_member_group_period", table_name="consolidation_group_members")
    op.drop_constraint("uq_conso_group_member_period", "consolidation_group_members", type_="unique")
    op.drop_table("consolidation_group_members")

    op.drop_index("ix_consolidation_groups_status", table_name="consolidation_groups")
    op.drop_constraint("uq_consolidation_groups_code", "consolidation_groups", type_="unique")
    op.drop_table("consolidation_groups")

    op.drop_index("ix_virtual_entities_book", table_name="virtual_entities")
    op.drop_index("ix_virtual_entities_status", table_name="virtual_entities")
    op.drop_constraint("uq_virtual_entities_code", "virtual_entities", type_="unique")
    op.drop_table("virtual_entities")

    op.drop_index("ix_legal_entities_book", table_name="legal_entities")
    op.drop_index("ix_legal_entities_status", table_name="legal_entities")
    op.drop_constraint("uq_legal_entities_code", "legal_entities", type_="unique")
    op.drop_table("legal_entities")
