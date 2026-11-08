"""commission records and configurable commission structures

Revision ID: 20261108_0020
Revises: 20261108_0019
Create Date: 2026-11-08 13:00:00.000000

Interview: commission vouchers are the main documents Abellar keeps; rental
commissions are agreed between lessor and broker; the seller/Abellar sharing
arrangement isn't validated yet. No rate is seeded.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0020"
down_revision: Union[str, None] = "20261108_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "commission_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="SALE"),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("basis", sa.String(20), nullable=False, server_default="AS_AGREED"),
        sa.Column("rate_percent", sa.Numeric(7, 3), nullable=True),
        sa.Column("fixed_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("months_of_rent", sa.Numeric(5, 2), nullable=True),
        sa.Column("seller_share_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_commission_structures_partner_id", "commission_structures", ["partner_id"])
    op.create_index("ix_commission_structures_listing_id", "commission_structures", ["listing_id"])
    op.create_table(
        "commission_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False, server_default="SALE"),
        sa.Column("transaction_id", sa.Uuid(as_uuid=False),
                  sa.ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("property_description", sa.String(500), nullable=True),
        sa.Column("lessor_name", sa.String(200), nullable=True),
        sa.Column("lessee_name", sa.String(200), nullable=True),
        sa.Column("monthly_rent", sa.Numeric(14, 2), nullable=True),
        sa.Column("lease_term_months", sa.Integer(), nullable=True),
        sa.Column("basis_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("commission_structures.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("rate_percent", sa.Numeric(7, 3), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("seller_share_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("agreement_reference", sa.String(120), nullable=True),
        sa.Column("agreement_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="UNRELEASED"),
        sa.Column("approval_status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("released_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("released_on", sa.Date(), nullable=True),
        sa.Column("voucher_document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("record_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("kind", "transaction_id", "agent_id", "listing_id", "status", "approval_status",
                   "voucher_document_id"):
        op.create_index(f"ix_commission_records_{column}", "commission_records", [column])


def downgrade() -> None:
    for column in ("voucher_document_id", "approval_status", "status", "listing_id", "agent_id", "transaction_id",
                   "kind"):
        op.drop_index(f"ix_commission_records_{column}", table_name="commission_records")
    op.drop_table("commission_records")
    op.drop_index("ix_commission_structures_listing_id", table_name="commission_structures")
    op.drop_index("ix_commission_structures_partner_id", table_name="commission_structures")
    op.drop_table("commission_structures")
