"""asset card enhance

Revision ID: 20260227_000017
Revises: 20260227_000016
Create Date: 2026-02-27 00:00:17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_000017"
down_revision: Union[str, None] = "20260227_000016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("fixed_assets", sa.Column("specification_model", sa.String(128), nullable=True))
    op.add_column("fixed_assets", sa.Column("unit", sa.String(32), nullable=True))
    op.add_column("fixed_assets", sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default=sa.text("1")))
    op.add_column("fixed_assets", sa.Column("location", sa.String(128), nullable=True))
    op.add_column("fixed_assets", sa.Column("purchase_date", sa.Date, nullable=True))
    op.add_column("fixed_assets", sa.Column("is_depreciable", sa.SmallInteger, nullable=False, server_default=sa.text("1")))


def downgrade() -> None:
    op.drop_column("fixed_assets", "is_depreciable")
    op.drop_column("fixed_assets", "purchase_date")
    op.drop_column("fixed_assets", "location")
    op.drop_column("fixed_assets", "quantity")
    op.drop_column("fixed_assets", "unit")
    op.drop_column("fixed_assets", "specification_model")
