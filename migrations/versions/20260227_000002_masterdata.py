"""masterdata tables

Revision ID: 20260227_000002
Revises: 20260227_000001
Create Date: 2026-02-27 00:00:02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000002"
down_revision: Union[str, None] = "20260227_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _base_columns():
    return [
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.BigInteger, nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_enabled", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    ]


def _add_common_indexes(table_name: str):
    op.create_unique_constraint(
        f"uq_{table_name}_book_id_code", table_name, ["book_id", "code"]
    )
    op.create_index(
        f"ix_{table_name}_book_id_name", table_name, ["book_id", "name"]
    )
    op.create_index(
        f"ix_{table_name}_book_id_is_enabled", table_name, ["book_id", "is_enabled"]
    )


def upgrade() -> None:
    # subjects
    op.create_table(
        "subjects",
        *_base_columns(),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("balance_direction", sa.String(16), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("template_type", sa.String(32), nullable=True),
        sa.Column("level", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("parent_code", sa.String(64), nullable=True),
        sa.Column(
            "requires_auxiliary",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "requires_bank_account_aux",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "supports_foreign_currency",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("subjects")

    # entities
    op.create_table(
        "entities",
        *_base_columns(),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("entities")

    # persons
    op.create_table(
        "persons",
        *_base_columns(),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("persons")

    # projects
    op.create_table(
        "projects",
        *_base_columns(),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("projects")

    # departments
    op.create_table(
        "departments",
        *_base_columns(),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("departments")

    # bank_accounts
    op.create_table(
        "bank_accounts",
        *_base_columns(),
        **MYSQL_TABLE_ARGS,
    )
    _add_common_indexes("bank_accounts")


def downgrade() -> None:
    for table_name in [
        "bank_accounts",
        "departments",
        "projects",
        "persons",
        "entities",
        "subjects",
    ]:
        op.drop_index(f"ix_{table_name}_book_id_is_enabled", table_name=table_name)
        op.drop_index(f"ix_{table_name}_book_id_name", table_name=table_name)
        op.drop_constraint(
            f"uq_{table_name}_book_id_code", table_name=table_name, type_="unique"
        )
        op.drop_table(table_name)
