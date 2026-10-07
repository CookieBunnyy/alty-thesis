"""why a transaction was cancelled

Revision ID: 20261007_0009
Revises: 20261007_0008
Create Date: 2026-10-07 16:00:00.000000

- transactions.cancellation_reason / cancelled_at / cancelled_by: recorded
  whenever a reservation is cancelled (by a staff action, a property status
  change, or the central database). Kept in ALTY; not pushed to Supabase.
  Transactions cancelled before this change have no recorded reason.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_0009"
down_revision: Union[str, None] = "20261007_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("transactions", sa.Column("cancelled_by", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "cancelled_by")
    op.drop_column("transactions", "cancelled_at")
    op.drop_column("transactions", "cancellation_reason")
