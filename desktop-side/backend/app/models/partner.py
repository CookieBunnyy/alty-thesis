from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PARTNER_TYPES = ("DEVELOPER", "BROKERAGE", "BANK", "CONTRACTOR", "OTHER")
PARTNER_STATUSES = ("ACTIVE", "INACTIVE")


class Partner(Base):
    """A developer or other partner company Abellar Realty works with."""

    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    contact_person: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Logo for the public home page's partners strip (see services/partner_logos).
    logo_bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    logo_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
