"""add property-linked clients

Revision ID: c84e9a31d6f2
Revises: 891284426ae5
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84e9a31d6f2"
down_revision: Union[str, None] = "891284426ae5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("client_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=40), nullable=True),
        sa.Column("property_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN ('RESERVED', 'SOLD')",
            name="ck_clients_transaction_type",
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'SOLD')",
            name="ck_clients_status",
        ),
        sa.CheckConstraint(
            "transaction_type = status",
            name="ck_clients_status_matches_transaction_type",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["property_listings.listing_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("client_id"),
        sa.UniqueConstraint("property_id", name="uq_clients_property_id"),
    )
    op.create_index("ix_clients_status", "clients", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_status", table_name="clients")
    op.drop_table("clients")