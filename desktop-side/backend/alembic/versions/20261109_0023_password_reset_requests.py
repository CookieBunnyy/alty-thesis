"""staff password reset requests approved by the Administrator

Revision ID: 20261109_0023
Revises: 20261109_0022
Create Date: 2026-11-09 09:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261109_0023"
down_revision: Union[str, None] = "20261109_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by_name", sa.String(200), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_requests_user_id", "password_reset_requests", ["user_id"])
    op.create_index("ix_password_reset_requests_status", "password_reset_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_requests_status", table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_user_id", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
