from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.client import Client
    from app.models.property_listing import PropertyListing


class PropertyTransaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RESERVED', 'SOLD')",
            name="ck_transactions_type",
        ),
        CheckConstraint(
            "status IN ('RESERVED', 'COMPLETED', 'CANCELLED')",
            name="ck_transactions_status",
        ),
        CheckConstraint("amount >= 0", name="ck_transactions_amount_nonnegative"),
    )

    transaction_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    external_transaction_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True, index=True
    )
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("clients.client_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("agents.agent_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    client: Mapped[Client] = relationship("Client", back_populates="transactions")
    property_listing: Mapped[PropertyListing] = relationship("PropertyListing")
    agent: Mapped[Agent] = relationship("Agent")