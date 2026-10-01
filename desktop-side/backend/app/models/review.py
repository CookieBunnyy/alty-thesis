from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.client import Client
    from app.models.transaction import PropertyTransaction


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentReview(Base):
    """A client's rating of the agent who handled one completed transaction.

    One review per transaction (unique ``transaction_id``); the client may
    edit it later, which updates the same row. ``agent_id`` and
    ``client_id`` are copied from the transaction so a client can only rate
    the agent who actually handled their transaction.
    """

    __tablename__ = "agent_reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_reviews_rating"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("transactions.transaction_id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    agent: Mapped[Agent] = relationship("Agent")
    client: Mapped[Client] = relationship("Client")
    transaction: Mapped[PropertyTransaction] = relationship("PropertyTransaction")
