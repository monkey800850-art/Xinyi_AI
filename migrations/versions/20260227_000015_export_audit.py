"""export audit logs

Revision ID: 20260227_000015
Revises: 20260227_000014
Create Date: 2026-02-27 00:00:15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000015"
down_revision: Union[str, None] = "20260227_000014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MYSQL_TABLE_ARGS = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "export_audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("report_key", sa.String(64), nullable=False),
        sa.Column("book_id", sa.BigInteger, nullable=True),
        sa.Column("filters", sa.Text, nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index("ix_export_audit_report", "export_audit_logs", ["report_key"])
    op.create_index("ix_export_audit_book", "export_audit_logs", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_export_audit_book", table_name="export_audit_logs")
    op.drop_index("ix_export_audit_report", table_name="export_audit_logs")
    op.drop_table("export_audit_logs")
