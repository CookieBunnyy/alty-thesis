"""The listing agreement a property owner signs with Abellar Realty: the
authority to sell the property, on what terms (one current agreement per
listing; a newer agreement replaces the terms). Recorded from an uploaded
Listing Agreement document."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Section 3 of the agreement: how much of the selling right the owner gives.
RIGHTS_TO_SELL = ("EXCLUSIVE_RIGHT_TO_SELL", "EXCLUSIVE_AGENCY", "OPEN_LISTING")
COMMISSION_TYPES = ("PERCENTAGE", "FIXED")


class ListingAgreement(Base):
    __tablename__ = "listing_agreements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("property_listings.listing_id", ondelete="CASCADE"), nullable=False, unique=True)
    source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agreement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 1. The parties
    seller_name: Mapped[str] = mapped_column(String(200), nullable=False)
    seller_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    broker_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agency_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agency_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 2. The property
    property_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tct_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_declaration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fixtures_excluded: Mapped[str | None] = mapped_column(Text, nullable=True)
    personal_property_included: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 3-7. Selling right, price, period and commission
    rights_to_sell: Mapped[str | None] = mapped_column(String(32), nullable=True)
    listing_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    listing_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    extension_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    commission_rate: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    commission_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    leasing_commission_rate: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    deed_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cooperating_commission_rate: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    # 8-9. Dual agency and what the agency may do to market the property
    dual_agency_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    marketing_permissions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # 26, 28
    governing_law: Mapped[str | None] = mapped_column(String(200), nullable=True)
    additional_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)
