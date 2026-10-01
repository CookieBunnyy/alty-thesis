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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


CLIENT_STATUSES = ("PROSPECT", "RESERVED", "SOLD", "CANCELLED")


class Client(Base):
    """A buyer/client derived from documents or website submissions.

    A client may exist before any transaction (Buyer Document), so the
    property, agent and transaction summary columns are nullable. The
    authoritative transaction history lives in ``transactions``; the
    ``transaction_type``/``status`` columns summarize the latest one.
    """

    __tablename__ = "clients"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('RESERVED', 'SOLD')",
            name="ck_clients_transaction_type",
        ),
        CheckConstraint(
            "status IN ('PROSPECT', 'RESERVED', 'SOLD', 'CANCELLED')",
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
    occupation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    civil_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    preferred_contact: Mapped[str | None] = mapped_column(String(60), nullable=True)
    purpose_of_purchase: Mapped[str | None] = mapped_column(String(160), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("agents.agent_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transaction_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PROSPECT", index=True
    )
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, default="DOCUMENT", server_default="SYNC"
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

    property_listing: Mapped[PropertyListing | None] = relationship(
        "PropertyListing", lazy="joined"
    )
    agent: Mapped[Agent | None] = relationship("Agent", lazy="joined")
    transactions: Mapped[list[PropertyTransaction]] = relationship(
        "PropertyTransaction", back_populates="client", lazy="selectin"
    )
