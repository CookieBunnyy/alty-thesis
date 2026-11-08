"""deal pipeline: inquiry to closing

Revision ID: 20261108_0019
Revises: 20261108_0018
Create Date: 2026-11-08 12:00:00.000000

Interview workflow: property information shared -> viewing (physical or
virtual) -> buyer decides -> reservation -> developer processing -> closing.
- deals: one buyer's deal for one property with the seller handling it.
- deal_events: every stage change and edit (the deal's history).
Existing reservations and sales are linked into deals: one deal per client
and property, at RESERVED, or CLOSED when sold.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0019"
down_revision: Union[str, None] = "20261108_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Uuid(as_uuid=False), sa.ForeignKey("clients.client_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("stage", sa.String(24), nullable=False, server_default="INQUIRY"),
        sa.Column("inquiry_date", sa.Date(), nullable=True),
        sa.Column("viewing_type", sa.String(12), nullable=True),
        sa.Column("viewing_at", sa.DateTime(), nullable=True),
        sa.Column("reservation_date", sa.Date(), nullable=True),
        sa.Column("reservation_status", sa.String(16), nullable=True),
        sa.Column("developer_status", sa.String(16), nullable=False, server_default="NOT_STARTED"),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("reservation_transaction_id", sa.Uuid(as_uuid=False),
                  sa.ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True),
        sa.Column("sale_transaction_id", sa.Uuid(as_uuid=False),
                  sa.ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for column in ("client_id", "agent_id", "listing_id", "stage"):
        op.create_index(f"ix_deals_{column}", "deals", [column])
    op.create_table(
        "deal_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(24), nullable=True),
        sa.Column("to_stage", sa.String(24), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_deal_events_deal_id", "deal_events", ["deal_id"])

    # Existing reservations and sales become deals (one per client and property).
    op.execute("""
        INSERT INTO deals (client_id, agent_id, listing_id, stage, reservation_date, reservation_status,
                           closing_date, reservation_transaction_id, sale_transaction_id, created_by,
                           created_at, updated_at)
        SELECT r.client_id, COALESCE(s.agent_id, r.agent_id), r.property_id,
               CASE WHEN s.transaction_id IS NOT NULL THEN 'CLOSED'
                    WHEN r.status = 'CANCELLED' THEN 'LOST' ELSE 'RESERVED' END,
               (r.transaction_date AT TIME ZONE 'UTC')::date, r.status,
               (s.transaction_date AT TIME ZONE 'UTC')::date, r.transaction_id, s.transaction_id,
               'Migration', now(), now()
        FROM transactions r
        LEFT JOIN LATERAL (
            SELECT t.transaction_id, t.agent_id, t.transaction_date FROM transactions t
            WHERE t.transaction_type = 'SOLD' AND t.status = 'COMPLETED'
              AND t.client_id = r.client_id AND t.property_id = r.property_id
            ORDER BY t.transaction_date LIMIT 1) s ON TRUE
        WHERE r.transaction_type = 'RESERVED'
    """)
    op.execute("""
        INSERT INTO deals (client_id, agent_id, listing_id, stage, closing_date, sale_transaction_id,
                           created_by, created_at, updated_at)
        SELECT t.client_id, t.agent_id, t.property_id, 'CLOSED', (t.transaction_date AT TIME ZONE 'UTC')::date,
               t.transaction_id, 'Migration', now(), now()
        FROM transactions t
        WHERE t.transaction_type = 'SOLD' AND t.status = 'COMPLETED'
          AND NOT EXISTS (SELECT 1 FROM deals d WHERE d.sale_transaction_id = t.transaction_id)
    """)


def downgrade() -> None:
    op.drop_index("ix_deal_events_deal_id", table_name="deal_events")
    op.drop_table("deal_events")
    for column in ("stage", "listing_id", "agent_id", "client_id"):
        op.drop_index(f"ix_deals_{column}", table_name="deals")
    op.drop_table("deals")
