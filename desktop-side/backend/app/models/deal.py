"""A buyer's deal from first inquiry to closing (Abellar's confirmed workflow):

inquiry -> viewing (physical or virtual) -> reservation -> developer
processing -> closing; or lost when the buyer doesn't proceed.

Reservations and sales themselves stay in ``transactions`` (recorded from
documents); a deal links to them and keeps the stages around them.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

DEAL_STAGES = ("INQUIRY", "VIEWING", "RESERVED", "DEVELOPER_PROCESSING", "CLOSED")
DEAL_CLOSED = ("CLOSED", "LOST")
VIEWING_TYPES = ("PHYSICAL", "VIRTUAL")
DEVELOPER_STATUSES = ("NOT_STARTED", "SUBMITTED", "IN_PROCESS", "APPROVED", "RETURNED")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("property_listings.listing_id", ondelete="SET NULL"), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default="INQUIRY", index=True)
    inquiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    viewing_type: Mapped[str | None] = mapped_column(String(12), nullable=True)
    viewing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reservation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reservation_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # RESERVED / CANCELLED / COMPLETED
    developer_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NOT_STARTED")
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reservation_transaction_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True)
    sale_transaction_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class DealEvent(Base):
    """One change to a deal (stage moves and edits), oldest first."""

    __tablename__ = "deal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False,
                                         index=True)
    from_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    changes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
