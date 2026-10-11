"""staff email, password recovery and sign-in throttling

Revision ID: 20261011_0011
Revises: 20261008_0010
Create Date: 2026-10-11 09:00:00.000000

- users.email: a staff account's registered email (password recovery).
  Unique ignoring case; client accounts keep their email as the username.
- users.session_version: bumped when the password changes; access tokens
  carry it, so tokens issued before the change stop working.
- users.password_changed_at: when the password last changed.
- password_reset_tokens: single-use reset tokens, stored as SHA-256 hashes.
- auth_attempts: sign-in and recovery attempts (hashed keys) shared by every
  API instance, for rate limits and cooldowns that survive restarts.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261011_0011"
down_revision: Union[str, None] = "20261008_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    op.create_index("ux_users_email_lower", "users", [sa.text("lower(email)")], unique=True,
                    postgresql_where=sa.text("email IS NOT NULL"))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_attempts_lookup", "auth_attempts", ["scope", "key_hash", "created_at"])
    op.create_index("ix_auth_attempts_created_at", "auth_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_attempts_created_at", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_lookup", table_name="auth_attempts")
    op.drop_table("auth_attempts")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ux_users_email_lower", table_name="users")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "session_version")
    op.drop_column("users", "email")
