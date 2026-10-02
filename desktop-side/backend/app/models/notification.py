from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationRead(Base):
    """Which notifications a staff user has already read.

    Notifications themselves are not stored: they are computed from the
    records (documents, transactions, reviews, …) on every request, and each
    has a stable ``key``. Only the "read" marks are kept here.
    """

    __tablename__ = "notification_reads"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, index=True)
