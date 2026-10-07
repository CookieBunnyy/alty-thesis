from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.client import Client
    from app.models.property_listing import PropertyListing


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PropertyTransaction(Base):
    """One business event (reservation or sale) in a client's history.

    A reservation followed by a sale is two rows; the reservation is kept
    (its status becomes COMPLETED) when the sale is recorded.
    """

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
        # Idempotency backstop: one live reservation/sale per client+property+type.
        Index(
            "uq_transactions_active_client_property_type",
            "client_id",
            "property_id",
            "transaction_type",
            unique=True,
            postgresql_where=text("status <> 'CANCELLED'"),
        ),
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
    # Why it was cancelled, by whom and when (ALTY only; not synced).
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, default="DOCUMENT", server_default="SYNC"
    )
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PENDING", server_default="SYNCED"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    client: Mapped[Client] = relationship("Client", back_populates="transactions")
    property_listing: Mapped[PropertyListing] = relationship("PropertyListing")
    agent: Mapped[Agent] = relationship("Agent")
