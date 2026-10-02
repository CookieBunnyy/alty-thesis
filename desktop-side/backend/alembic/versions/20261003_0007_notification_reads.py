"""notification read marks

Revision ID: 20261003_0007
Revises: 20261002_0006
Create Date: 2026-10-03 09:00:00.000000

Desktop header notifications are computed from the records on request;
this table only remembers which ones each staff user has read.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261003_0007"
down_revision: Union[str, None] = "20261002_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "notification_reads",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("read_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notification_reads_read_at", "notification_reads", ["read_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_reads_read_at", table_name="notification_reads")
    op.drop_table("notification_reads")
