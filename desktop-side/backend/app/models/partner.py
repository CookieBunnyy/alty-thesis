from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PARTNER_TYPES = ("DEVELOPER", "BROKERAGE", "BANK", "CONTRACTOR", "OTHER")
PARTNER_STATUSES = ("ACTIVE", "INACTIVE")
# The accreditation a developer grants Abellar Realty to market its properties.
ACCREDITATION_STATUSES = ("NONE", "PENDING", "VERIFIED", "EXPIRED", "REVOKED")
# What the accreditation covers (interview 2): every project nationwide, the
# projects in a region, or only named projects / clusters. Usually valid for
# one year and renewed yearly.
ACCREDITATION_SCOPES = ("ALL_PROJECTS", "REGIONAL", "SPECIFIC_PROJECTS")
ACCREDITATION_VALID_MONTHS = 12


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
    # Accreditation of Abellar Realty by this developer. Only VERIFIED and
    # unexpired accreditation lets its listings be approved for marketing.
    accreditation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE",
                                                      server_default="NONE")
    accreditation_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    accreditation_valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    accreditation_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="ALL_PROJECTS",
                                                     server_default="ALL_PROJECTS")
    accreditation_region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Project / cluster names, when the scope is SPECIFIC_PROJECTS.
    accreditation_projects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    accreditation_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    accreditation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    accreditation_verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accreditation_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
