"""client accounts and agent reviews

Revision ID: 20261002_0006
Revises: 20260930_0005
Create Date: 2026-10-02 12:00:00.000000

- users.client_id: website client accounts (role "Client") link to their
  client record; staff accounts leave it NULL.
- agent_reviews: one 1-5 star rating (+ optional text) per completed
  transaction, by the transaction's client, for the transaction's agent.
- roles: reference row for the Client role (no desktop access).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0006"
down_revision: Union[str, None] = "20260930_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("client_id", sa.Uuid(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_users_client_id", "users", "clients", ["client_id"], ["client_id"],
                          ondelete="SET NULL")
    op.create_unique_constraint("uq_users_client_id", "users", ["client_id"])

    op.create_table(
        "agent_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=False), sa.ForeignKey("clients.client_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("transaction_id", sa.Uuid(as_uuid=False),
                  sa.ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_reviews_rating"),
        sa.UniqueConstraint("transaction_id", name="uq_agent_reviews_transaction_id"),
    )
    op.create_index("ix_agent_reviews_agent_id", "agent_reviews", ["agent_id"])
    op.create_index("ix_agent_reviews_client_id", "agent_reviews", ["client_id"])
    op.create_index("ix_agent_reviews_created_at", "agent_reviews", ["created_at"])

    connection = op.get_bind()
    exists = connection.execute(sa.text("SELECT 1 FROM roles WHERE name = 'Client'")).first()
    if not exists:
        connection.execute(sa.text(
            "INSERT INTO roles (name, description, created_at) "
            "VALUES ('Client', 'Website client account (no desktop access)', now())"
        ))


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'Client'")
    op.drop_index("ix_agent_reviews_created_at", table_name="agent_reviews")
    op.drop_index("ix_agent_reviews_client_id", table_name="agent_reviews")
    op.drop_index("ix_agent_reviews_agent_id", table_name="agent_reviews")
    op.drop_table("agent_reviews")
    op.drop_constraint("uq_users_client_id", "users", type_="unique")
    op.drop_constraint("fk_users_client_id", "users", type_="foreignkey")
    op.drop_column("users", "client_id")
