from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditEvent(Base):
    """System-wide audit trail (logins, document processing, entity changes)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Username, or SYSTEM / WEBSITE for non-user actors.
    actor_label: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="SUCCESS")
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
