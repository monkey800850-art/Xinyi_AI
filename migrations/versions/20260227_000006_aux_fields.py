"""voucher lines aux fields

Revision ID: 20260227_000006
Revises: 20260227_000005
Create Date: 2026-02-27 00:00:06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_000006"
down_revision: Union[str, None] = "20260227_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("voucher_lines", sa.Column("aux_type", sa.String(32), nullable=True))
    op.add_column("voucher_lines", sa.Column("aux_id", sa.BigInteger, nullable=True))
    op.add_column("voucher_lines", sa.Column("aux_code", sa.String(64), nullable=True))
    op.add_column("voucher_lines", sa.Column("aux_name", sa.String(255), nullable=True))
    op.create_index(
        "ix_voucher_lines_aux", "voucher_lines", ["aux_type", "aux_code"]
    )


def downgrade() -> None:
    op.drop_index("ix_voucher_lines_aux", table_name="voucher_lines")
    op.drop_column("voucher_lines", "aux_name")
    op.drop_column("voucher_lines", "aux_code")
    op.drop_column("voucher_lines", "aux_id")
    op.drop_column("voucher_lines", "aux_type")
