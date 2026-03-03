"""consolidation enhancements: disclosure checks and audit indexes

Revision ID: 20260303_000047
Revises: 20260303_000046
Create Date: 2026-03-03 23:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260303_000047"
down_revision: Union[str, None] = "20260303_000046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _table_exists(bind, table_name: str) -> bool:
    row = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchone()
    return int(row.cnt or 0) > 0


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    row = bind.execute(
        sa.text(
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
    bind = op.get_bind()
    if not _table_exists(bind, "consolidation_disclosure_checks"):
        op.create_table(
            "consolidation_disclosure_checks",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("group_id", sa.BigInteger, nullable=False),
            sa.Column("period", sa.String(7), nullable=False),
            sa.Column("batch_id", sa.String(64), nullable=False),
            sa.Column("check_code", sa.String(64), nullable=False),
            sa.Column("check_result", sa.String(16), nullable=False),
            sa.Column("check_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("threshold_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("note", sa.String(255), nullable=True),
            sa.Column("operator_id", sa.BigInteger, nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("group_id", "period", "batch_id", "check_code", name="uq_conso_disclosure_check"),
            **MYSQL_TABLE_ARGS,
        )

    if not _table_exists(bind, "consolidation_audit_indexes"):
        op.create_table(
            "consolidation_audit_indexes",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("group_id", sa.BigInteger, nullable=False),
            sa.Column("period", sa.String(7), nullable=False),
            sa.Column("batch_id", sa.String(64), nullable=False),
            sa.Column("report_code", sa.String(64), nullable=False),
            sa.Column("item_code", sa.String(128), nullable=False),
            sa.Column("item_label", sa.String(255), nullable=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("evidence_ref", sa.String(255), nullable=False),
            sa.Column("source_batch_id", sa.String(64), nullable=True),
            sa.Column("operator_id", sa.BigInteger, nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            **MYSQL_TABLE_ARGS,
        )
    if not _index_exists(bind, "consolidation_audit_indexes", "ix_conso_audit_idx_gp_batch"):
        op.create_index(
            "ix_conso_audit_idx_gp_batch",
            "consolidation_audit_indexes",
            ["group_id", "period", "batch_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "consolidation_audit_indexes"):
        if _index_exists(bind, "consolidation_audit_indexes", "ix_conso_audit_idx_gp_batch"):
            op.drop_index("ix_conso_audit_idx_gp_batch", table_name="consolidation_audit_indexes")
        op.drop_table("consolidation_audit_indexes")
    if _table_exists(bind, "consolidation_disclosure_checks"):
        op.drop_table("consolidation_disclosure_checks")
