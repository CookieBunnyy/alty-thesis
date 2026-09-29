"""add client email and transaction records

Revision ID: d0c5e97e44b1
Revises: f71bd47a9c01
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0c5e97e44b1"
down_revision: Union[str, None] = "f71bd47a9c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("email", sa.String(length=255), nullable=True))
    op.drop_constraint(
        "ck_clients_status_matches_transaction_type",
        "clients",
        type_="check",
    )
    op.drop_constraint("ck_clients_status", "clients", type_="check")
    op.create_check_constraint(
        "ck_clients_status",
        "clients",
        "status IN ('RESERVED', 'SOLD', 'CANCELLED')",
    )

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=32), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN ('RESERVED', 'SOLD')",
            name="ck_transactions_type",
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'COMPLETED', 'CANCELLED')",
            name="ck_transactions_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_transactions_amount_nonnegative"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.agent_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.client_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["property_listings.listing_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index("ix_transactions_client_id", "transactions", ["client_id"], unique=True)
    op.create_index("ix_transactions_property_id", "transactions", ["property_id"])
    op.create_index("ix_transactions_agent_id", "transactions", ["agent_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.execute(
        sa.text(
            """
            INSERT INTO transactions (
                transaction_id, client_id, property_id, agent_id,
                transaction_type, transaction_date, amount, status,
                notes, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                client.client_id,
                client.property_id,
                client.agent_id,
                client.transaction_type,
                COALESCE(client.transaction_date, client.created_at),
                COALESCE(listing.price_total, 0),
                CASE
                    WHEN client.transaction_type = 'SOLD' THEN 'COMPLETED'
                    ELSE 'RESERVED'
                END,
                NULL,
                client.created_at,
                client.updated_at
            FROM clients AS client
            JOIN property_listings AS listing
              ON listing.listing_id = client.property_id
            ON CONFLICT (client_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_agent_id", table_name="transactions")
    op.drop_index("ix_transactions_property_id", table_name="transactions")
    op.drop_index("ix_transactions_client_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_column("clients", "email")
