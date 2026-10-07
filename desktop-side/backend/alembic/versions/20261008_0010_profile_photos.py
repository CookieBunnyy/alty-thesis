"""profile photos for agents and staff accounts

Revision ID: 20261008_0010
Revises: 20261007_0009
Create Date: 2026-10-08 09:00:00.000000

- agents.photo_bucket / photo_path / photo_updated_at: the agent's profile
  photo (shown to staff and on the public website). Kept in ALTY; not part of
  the Supabase agent record.
- users.photo_bucket / photo_path / photo_updated_at: a staff account's own
  photo (only shown to signed-in staff).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_0010"
down_revision: Union[str, None] = "20261007_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

TABLES = ("agents", "users")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("photo_bucket", sa.String(length=120), nullable=True))
        op.add_column(table, sa.Column("photo_path", sa.String(length=300), nullable=True))
        op.add_column(table, sa.Column("photo_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "photo_updated_at")
        op.drop_column(table, "photo_path")
        op.drop_column(table, "photo_bucket")
