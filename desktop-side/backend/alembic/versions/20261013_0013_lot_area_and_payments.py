"""lot area on listings; payments recorded against reservations

Revision ID: 20261013_0013
Revises: 20261012_0012
Create Date: 2026-10-13 09:00:00.000000

- property_listings.lot_area_sqm: the lot's size in square metres (shown as
  m² or hectares). Not part of the central listings sync.
- transaction_payments: down payments and monthly payments received for a
  reservation (the reservation fee itself is the reservation's amount).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_0013"
down_revision: Union[str, None] = "20261012_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("property_listings", sa.Column("lot_area_sqm", sa.Numeric(14, 2), nullable=True))
    op.create_check_constraint("ck_property_listings_lot_area_positive", "property_listings",
                               "lot_area_sqm IS NULL OR lot_area_sqm > 0")
    op.create_table(
        "transaction_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Uuid(as_uuid=False),
                  sa.ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("recorded_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transaction_payments_amount_positive"),
    )
    op.create_index("ix_transaction_payments_transaction_id", "transaction_payments", ["transaction_id"])


def downgrade() -> None:
    op.drop_index("ix_transaction_payments_transaction_id", table_name="transaction_payments")
    op.drop_table("transaction_payments")
    op.drop_constraint("ck_property_listings_lot_area_positive", "property_listings", type_="check")
    op.drop_column("property_listings", "lot_area_sqm")
