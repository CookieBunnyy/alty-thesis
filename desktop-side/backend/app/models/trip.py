"""Tripping schedule: site visits that take buyers to a subdivision / project
(the office whiteboard: date, pick-up, time, subdivision, agent)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

TRIP_STATUSES = ("SCHEDULED", "CONFIRMED", "ONGOING", "DONE", "CANCELLED")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pickup_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "08:30"
    pickup_point: Mapped[str] = mapped_column(String(200), nullable=False)
    subdivision: Mapped[str] = mapped_column(String(200), nullable=False)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="SET NULL"), nullable=True)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"), nullable=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False,
                                          index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False, index=True)
    updated_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    agent = relationship("Agent", lazy="joined", viewonly=True)
    buyers: Mapped[list["TripBuyer"]] = relationship(back_populates="trip", cascade="all, delete-orphan",
                                                     order_by="TripBuyer.id", lazy="selectin")


class TripBuyer(Base):
    """A buyer joining the trip: a client record (has the website account and
    phone) or just a name and phone number."""

    __tablename__ = "trip_buyers"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("clients.client_id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    trip: Mapped[Trip] = relationship(back_populates="buyers")


class TripNotice(Base):
    """A schedule message to a buyer, shown in their website account."""

    __tablename__ = "trip_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
