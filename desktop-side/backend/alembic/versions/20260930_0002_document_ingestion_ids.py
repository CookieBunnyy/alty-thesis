"""add external document identifiers and repeat client transactions

Revision ID: 20260930_0002
Revises: d0c5e97e44b1
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_0002"
down_revision: Union[str, None] = "d0c5e97e44b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "property_listings", sa.Column("external_listing_id", sa.String(length=120), nullable=True)
    )
    op.create_index("ix_property_listings_external_listing_id", "property_listings", ["external_listing_id"], unique=True)
    op.add_column("clients", sa.Column("external_client_id", sa.String(length=120), nullable=True))
    op.create_index("ix_clients_external_client_id", "clients", ["external_client_id"], unique=True)
    op.add_column(
        "transactions", sa.Column("external_transaction_id", sa.String(length=120), nullable=True)
    )
    op.create_index("ix_transactions_external_transaction_id", "transactions", ["external_transaction_id"], unique=True)
    op.drop_index("ix_transactions_client_id", table_name="transactions")
    op.create_index("ix_transactions_client_id", "transactions", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_client_id", table_name="transactions")
    op.create_index("ix_transactions_client_id", "transactions", ["client_id"], unique=True)
    op.drop_index("ix_transactions_external_transaction_id", table_name="transactions")
    op.drop_column("transactions", "external_transaction_id")
    op.drop_index("ix_clients_external_client_id", table_name="clients")
    op.drop_column("clients", "external_client_id")
    op.drop_index("ix_property_listings_external_listing_id", table_name="property_listings")
    op.drop_column("property_listings", "external_listing_id")