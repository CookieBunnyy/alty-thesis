"""second interview: voucher fields, commission payouts, accreditation scope,
steps after the reservation, financing, listing computation details

* document_schemas: the commission voucher's fields, as Abellar listed them
  (only when no fields were set up yet).
* commission_releases: each payout (lump sum or in parts) with how / which bank.
* agents.commission_visible: sellers see their own commissions by default.
* partners: accreditation scope (all projects, regional, specific projects).
* deals: financing type, equity terms and the post-reservation milestones.
* property_listings: RFO / pre-selling, financing accepted, reservation fee,
  equity terms (sample computation).

Revision ID: 20261111_0026
Revises: 20261110_0025
Create Date: 2026-11-11 12:00:00.000000
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261111_0026"
down_revision: Union[str, None] = "20261110_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

VOUCHER_FIELDS = [
    {"key": "agent_name", "label": "Agent name", "aliases": ["Agent", "Name of agent", "Seller", "Payee", "Pay to"],
     "type": "text", "required": True},
    {"key": "voucher_date", "label": "Date", "aliases": ["Voucher date", "Date prepared", "Date issued"],
     "type": "date", "required": True},
    {"key": "tcp", "label": "TCP", "aliases": ["Total contract price", "Contract price", "Selling price"],
     "type": "money", "required": True},
    {"key": "particulars", "label": "Particulars", "aliases": ["Description", "Details", "Remarks"],
     "type": "text", "required": True},
    {"key": "amount", "label": "Amount", "aliases": ["Amount paid", "Total amount", "Gross amount"],
     "type": "money", "required": True},
    {"key": "payment_method", "label": "Mode of payment",
     "aliases": ["Paid through", "Payment method", "Paid via", "Payment mode", "Mode"], "type": "text",
     "required": True},
    {"key": "commission_amount", "label": "Commission amount",
     "aliases": ["Commission", "Net commission", "Commission due"], "type": "money", "required": True},
    {"key": "bank_name", "label": "Bank name", "aliases": ["Bank", "Bank / branch"], "type": "text",
     "required": True},
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE document_schemas SET fields = CAST(:f AS json), updated_by = 'Interview (voucher details)' "
                         "WHERE document_type = 'COMMISSION_VOUCHER' AND CAST(fields AS text) IN ('[]', 'null')"),
                 {"f": json.dumps(VOUCHER_FIELDS)})

    op.create_table(
        "commission_releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("commission_records.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("released_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(20), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("particulars", sa.String(500), nullable=True),
        sa.Column("recorded_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_commission_releases_record_id", "commission_releases", ["record_id"])
    # Earlier payouts become one release each (method unknown).
    bind.execute(sa.text("INSERT INTO commission_releases (record_id, amount, released_on, recorded_by) "
                         "SELECT id, released_amount, COALESCE(released_on, record_date), 'Earlier record' "
                         "FROM commission_records WHERE released_amount > 0"))

    op.alter_column("agents", "commission_visible", server_default=sa.text("true"))
    bind.execute(sa.text("UPDATE agents SET commission_visible = true"))

    op.add_column("partners", sa.Column("accreditation_scope", sa.String(20), nullable=False,
                                        server_default="ALL_PROJECTS"))
    op.add_column("partners", sa.Column("accreditation_region", sa.String(200), nullable=True))
    op.add_column("partners", sa.Column("accreditation_projects", sa.JSON(), nullable=False, server_default="[]"))

    op.add_column("deals", sa.Column("financing_type", sa.String(12), nullable=True))
    op.add_column("deals", sa.Column("equity_terms_months", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("milestones", sa.JSON(), nullable=False, server_default="{}"))

    op.add_column("property_listings", sa.Column("property_status", sa.String(16), nullable=True))
    op.add_column("property_listings", sa.Column("financing_options", postgresql.JSONB(), nullable=True))
    op.add_column("property_listings", sa.Column("reservation_fee", sa.Numeric(14, 2), nullable=True))
    op.add_column("property_listings", sa.Column("equity_terms_months", sa.Integer(), nullable=True))


def downgrade() -> None:
    for column in ("equity_terms_months", "reservation_fee", "financing_options", "property_status"):
        op.drop_column("property_listings", column)
    for column in ("milestones", "equity_terms_months", "financing_type"):
        op.drop_column("deals", column)
    for column in ("accreditation_projects", "accreditation_region", "accreditation_scope"):
        op.drop_column("partners", column)
    op.alter_column("agents", "commission_visible", server_default=sa.text("false"))
    op.drop_index("ix_commission_releases_record_id", table_name="commission_releases")
    op.drop_table("commission_releases")
