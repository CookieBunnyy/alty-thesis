"""partner logos (shown on the public home page)

Revision ID: 20261012_0012
Revises: 20261011_0011
Create Date: 2026-10-12 09:00:00.000000

- partners.logo_bucket / logo_path / logo_updated_at: the partner's logo,
  stored like profile photos (Supabase storage or local files).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261012_0012"
down_revision: Union[str, None] = "20261011_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("logo_bucket", sa.String(length=120), nullable=True))
    op.add_column("partners", sa.Column("logo_path", sa.String(length=300), nullable=True))
    op.add_column("partners", sa.Column("logo_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("partners", "logo_updated_at")
    op.drop_column("partners", "logo_path")
    op.drop_column("partners", "logo_bucket")
