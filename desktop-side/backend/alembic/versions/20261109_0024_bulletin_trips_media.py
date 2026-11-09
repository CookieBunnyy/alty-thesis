"""bulletin board (announcements, memos), tripping schedule, floor plan and
amenity images, listings added in the Management System

Revision ID: 20261109_0024
Revises: 20261109_0023
Create Date: 2026-11-09 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261109_0024"
down_revision: Union[str, None] = "20261109_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("property_media", sa.Column("caption", sa.String(160), nullable=True))
    op.add_column("property_listings", sa.Column(
        "submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    op.create_table(
        "bulletin_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board", sa.String(20), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("event_at", sa.DateTime(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("target_amount", sa.Numeric(16, 2), nullable=True),
        sa.Column("tiers", sa.JSON(), nullable=True),
        sa.Column("reward_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("image_bucket", sa.String(120), nullable=True),
        sa.Column("image_path", sa.String(300), nullable=True),
        sa.Column("image_mime", sa.String(80), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bulletin_posts_board", "bulletin_posts", ["board"])
    op.create_index("ix_bulletin_posts_created_at", "bulletin_posts", ["created_at"])

    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_date", sa.Date(), nullable=False),
        sa.Column("pickup_time", sa.String(5), nullable=False),
        sa.Column("pickup_point", sa.String(200), nullable=False),
        sa.Column("subdivision", sa.String(200), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("partner_id", sa.Integer(), sa.ForeignKey("partners.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_name", sa.String(200), nullable=True),
    )
    op.create_index("ix_trips_trip_date", "trips", ["trip_date"])
    op.create_index("ix_trips_agent_id", "trips", ["agent_id"])
    op.create_index("ix_trips_status", "trips", ["status"])
    op.create_index("ix_trips_updated_at", "trips", ["updated_at"])

    op.create_table(
        "trip_buyers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=False), sa.ForeignKey("clients.client_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_trip_buyers_trip_id", "trip_buyers", ["trip_id"])
    op.create_index("ix_trip_buyers_client_id", "trip_buyers", ["client_id"])

    op.create_table(
        "trip_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trip_id", sa.Integer(), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Uuid(as_uuid=False), sa.ForeignKey("clients.client_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_by_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_trip_notices_trip_id", "trip_notices", ["trip_id"])
    op.create_index("ix_trip_notices_client_id", "trip_notices", ["client_id"])


def downgrade() -> None:
    op.drop_table("trip_notices")
    op.drop_table("trip_buyers")
    op.drop_table("trips")
    op.drop_table("bulletin_posts")
    op.drop_column("property_listings", "submitted_by_user_id")
    op.drop_column("property_media", "caption")
