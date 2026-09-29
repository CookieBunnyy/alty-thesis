"""preserve document rows when a property listing is deleted

Revision ID: 20260930_0004
Revises: 20260930_0003
Create Date: 2026-09-30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260930_0004"
down_revision: Union[str, None] = "20260930_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_documents_property_listing_id",
        "documents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_documents_property_listing_id",
        "documents",
        "property_listings",
        ["property_listing_id"],
        ["listing_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_property_listing_id",
        "documents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_documents_property_listing_id",
        "documents",
        "property_listings",
        ["property_listing_id"],
        ["listing_id"],
    )