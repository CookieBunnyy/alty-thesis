"""Which sellers market which listing (distributed by Admin / Marketing staff)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ListingAssignment(Base):
    __tablename__ = "listing_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("property_listings.listing_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # Set when the seller stops marketing the listing (the row is kept as history).
    removed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
