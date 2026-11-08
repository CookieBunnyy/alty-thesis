"""developer accreditation, marketing approval, listing assignments

Revision ID: 20261108_0017
Revises: 20261108_0016
Create Date: 2026-11-08 10:00:00.000000

Interview: Abellar Realty is accredited by developers to market their
properties (Developer -> Abellar -> Sellers -> Buyers).
- partners.accreditation_*: the accreditation a developer granted Abellar.
- property_listings.project_name / floor_area_sqm; marketing_status (DRAFT /
  APPROVED / WITHDRAWN) with who approved it. Existing listings start as
  DRAFT: nothing is approved without verified accreditation.
- property_media.media_kind: PHOTO or PERSPECTIVE (project images).
- listing_assignments: which sellers market which listing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0017"
down_revision: Union[str, None] = "20261108_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("partners", sa.Column("accreditation_status", sa.String(20), nullable=False, server_default="NONE"))
    op.add_column("partners", sa.Column("accreditation_reference", sa.String(120), nullable=True))
    op.add_column("partners", sa.Column("accreditation_valid_from", sa.Date(), nullable=True))
    op.add_column("partners", sa.Column("accreditation_valid_until", sa.Date(), nullable=True))
    op.add_column("partners", sa.Column("accreditation_notes", sa.Text(), nullable=True))
    op.add_column("partners", sa.Column("accreditation_verified_by", sa.String(200), nullable=True))
    op.add_column("partners", sa.Column("accreditation_verified_at", sa.DateTime(), nullable=True))

    op.add_column("property_listings", sa.Column("project_name", sa.String(200), nullable=True))
    op.add_column("property_listings", sa.Column("floor_area_sqm", sa.Numeric(14, 2), nullable=True))
    op.add_column("property_listings", sa.Column("marketing_status", sa.String(20), nullable=False,
                                                 server_default="DRAFT"))
    op.add_column("property_listings", sa.Column("marketing_approved_by", sa.String(200), nullable=True))
    op.add_column("property_listings", sa.Column("marketing_approved_at", sa.DateTime(), nullable=True))
    op.create_index("ix_property_listings_marketing_status", "property_listings", ["marketing_status"])

    op.add_column("property_media", sa.Column("media_kind", sa.String(20), nullable=False, server_default="PHOTO"))

    op.create_table(
        "listing_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by", sa.String(200), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("removed_by", sa.String(200), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_listing_assignments_listing_id", "listing_assignments", ["listing_id"])
    op.create_index("ix_listing_assignments_agent_id", "listing_assignments", ["agent_id"])
    # One active assignment per seller and listing.
    op.create_index("uq_listing_assignments_active", "listing_assignments", ["listing_id", "agent_id"], unique=True,
                    postgresql_where=sa.text("removed_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_listing_assignments_active", table_name="listing_assignments")
    op.drop_index("ix_listing_assignments_agent_id", table_name="listing_assignments")
    op.drop_index("ix_listing_assignments_listing_id", table_name="listing_assignments")
    op.drop_table("listing_assignments")
    op.drop_column("property_media", "media_kind")
    op.drop_index("ix_property_listings_marketing_status", table_name="property_listings")
    for column in ("marketing_approved_at", "marketing_approved_by", "marketing_status", "floor_area_sqm",
                   "project_name"):
        op.drop_column("property_listings", column)
    for column in ("accreditation_verified_at", "accreditation_verified_by", "accreditation_notes",
                   "accreditation_valid_until", "accreditation_valid_from", "accreditation_reference",
                   "accreditation_status"):
        op.drop_column("partners", column)
