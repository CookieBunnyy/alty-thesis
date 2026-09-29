from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.property_listing import PropertyListing
    from app.models.transaction import PropertyTransaction


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RESERVED', 'SOLD')",
            name="ck_clients_transaction_type",
        ),
        CheckConstraint(
            "status IN ('RESERVED', 'SOLD', 'CANCELLED')",
            name="ck_clients_status",
        ),
    )

    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    external_client_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("agents.agent_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    property_listing: Mapped[PropertyListing] = relationship(
        "PropertyListing", lazy="joined"
    )
    agent: Mapped[Agent] = relationship("Agent", lazy="joined")
    transactions: Mapped[list[PropertyTransaction]] = relationship(
        "PropertyTransaction", back_populates="client", lazy="selectin"
    )