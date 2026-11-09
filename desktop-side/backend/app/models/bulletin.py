"""The office bulletin board, online: announcements (monthly meetings,
updates, project flyers) and memos (sales targets, incentives, sales
notices). Every new post notifies the Management System's users."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

BOARDS = ("ANNOUNCEMENT", "MEMO")
CATEGORIES = {
    "ANNOUNCEMENT": ("MEETING", "UPDATE", "PROJECT", "GENERAL"),
    "MEMO": ("TARGET", "INCENTIVE", "SALES_NOTICE", "GENERAL"),
}


class BulletinPost(Base):
    __tablename__ = "bulletin_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    board: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Meetings: when it happens.
    event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Targets, incentives and promos: the period they cover.
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Targets: the sales goal. Incentives: the reward tiers
    # [{"label": "Bohol", "minimum_sales": 75000000, "reward": "3 days 2 nights for 2"}].
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    tiers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # A flat amount per sale (e.g. "Seller's incentive ₱22,500 for non-RFO units").
    reward_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), nullable=True)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="SET NULL"), nullable=True)
    # Sales notices: the recorded reservation / sale they announce.
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Optional flyer / poster image.
    image_bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    image_mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False)
