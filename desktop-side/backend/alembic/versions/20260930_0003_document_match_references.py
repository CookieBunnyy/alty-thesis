"""add extracted entity references to documents

Revision ID: 20260930_0003
Revises: 20260930_0002
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_0003"
down_revision: Union[str, None] = "20260930_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("property_listing_id", sa.Integer(), nullable=True))
    op.add_column(
        "documents", sa.Column("property_listing_external_id", sa.String(length=120), nullable=True)
    )
    op.add_column("documents", sa.Column("property_listing_title", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("transaction_reference", sa.String(length=120), nullable=True))
    op.add_column(
        "documents", sa.Column("related_party_external_id", sa.String(length=120), nullable=True)
    )
    op.create_foreign_key(
        "fk_documents_property_listing_id",
        "documents",
        "property_listings",
        ["property_listing_id"],
        ["listing_id"],
    )
    op.create_index(
        "ix_documents_property_listing_id",
        "documents",
        ["property_listing_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_property_listing_id", table_name="documents")
    op.drop_constraint("fk_documents_property_listing_id", "documents", type_="foreignkey")
    op.drop_column("documents", "related_party_external_id")
    op.drop_column("documents", "transaction_reference")
    op.drop_column("documents", "property_listing_title")
    op.drop_column("documents", "property_listing_external_id")
    op.drop_column("documents", "property_listing_id")