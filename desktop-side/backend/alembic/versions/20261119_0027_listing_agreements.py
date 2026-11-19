"""listing agreements and other amenities

* listing_agreements: the owner's authority to sell a property and its terms,
  recorded from an uploaded Listing Agreement document (one per listing).
* property_listings.other_amenities: amenities outside the common list,
  typed in as free text ("Other" in the amenities dropdown).

Revision ID: 20261119_0027
Revises: 20261111_0026
Create Date: 2026-11-19 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261119_0027"
down_revision: Union[str, None] = "20261111_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("property_listings", sa.Column("other_amenities", sa.Text(), nullable=True))
    op.create_table(
        "listing_agreements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("source_document_id", sa.String(64), nullable=True),
        sa.Column("agreement_date", sa.Date(), nullable=True),
        sa.Column("seller_name", sa.String(200), nullable=False),
        sa.Column("seller_address", sa.String(500), nullable=True),
        sa.Column("seller_contact", sa.String(100), nullable=True),
        sa.Column("broker_name", sa.String(200), nullable=True),
        sa.Column("agency_name", sa.String(200), nullable=True),
        sa.Column("agency_address", sa.String(500), nullable=True),
        sa.Column("property_address", sa.String(500), nullable=True),
        sa.Column("tct_number", sa.String(100), nullable=True),
        sa.Column("tax_declaration_number", sa.String(100), nullable=True),
        sa.Column("fixtures_excluded", sa.Text(), nullable=True),
        sa.Column("personal_property_included", sa.Text(), nullable=True),
        sa.Column("rights_to_sell", sa.String(32), nullable=True),
        sa.Column("listing_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("listing_start", sa.Date(), nullable=True),
        sa.Column("listing_end", sa.Date(), nullable=True),
        sa.Column("extension_days", sa.Integer(), nullable=True),
        sa.Column("commission_type", sa.String(16), nullable=True),
        sa.Column("commission_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column("commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("leasing_commission_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column("deed_type", sa.String(100), nullable=True),
        sa.Column("cooperating_commission_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column("dual_agency_allowed", sa.Boolean(), nullable=True),
        sa.Column("marketing_permissions", postgresql.JSONB(), nullable=True),
        sa.Column("governing_law", sa.String(200), nullable=True),
        sa.Column("additional_terms", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("listing_agreements")
    op.drop_column("property_listings", "other_amenities")
