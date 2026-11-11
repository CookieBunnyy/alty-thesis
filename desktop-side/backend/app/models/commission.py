"""Commission records and configurable commission structures.

Interview: commission vouchers are the primary documents Abellar keeps;
rental commissions are agreed between the lessor and the broker; the sharing
arrangement between seller and Abellar is not yet validated. So nothing here
has a built-in rate: management records each commission's agreed amount, and
may define structures (per developer, listing or rental) that only suggest it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

COMMISSION_KINDS = ("SALE", "RENTAL")
COMMISSION_BASES = ("PERCENT_OF_PRICE", "FIXED_AMOUNT", "MONTHS_OF_RENT", "AS_AGREED")
COMMISSION_STATUSES = ("UNRELEASED", "PARTIALLY_RELEASED", "RELEASED", "CANCELLED")
APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED")
# How a commission (or one instalment of it) was paid out, as on the voucher.
RELEASE_METHODS = ("ATM", "BANK_TRANSFER", "CHECK", "CASH", "E_WALLET", "OTHER")


class CommissionStructure(Base):
    """A commission arrangement management can apply to new records (optional)."""

    __tablename__ = "commission_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="SALE")
    # What it applies to: a developer, one listing, or neither (general).
    partner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("property_listings.listing_id", ondelete="SET NULL"), nullable=True, index=True)
    basis: Mapped[str] = mapped_column(String(20), nullable=False, default="AS_AGREED")
    rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    months_of_rent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    # The seller's share of the commission, if Abellar defines one (not yet validated).
    seller_share_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class CommissionRecord(Base):
    """One commission: for a sale (linked to its transaction) or a rental."""

    __tablename__ = "commission_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="SALE", index=True)
    transaction_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("agents.agent_id", ondelete="SET NULL"), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("property_listings.listing_id", ondelete="SET NULL"), nullable=True, index=True)
    # Rentals (and properties not listed in ALTY).
    property_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lessor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lessee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    monthly_rent: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    lease_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The amount the commission is based on (sale price, rent...), when known.
    basis_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    structure_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("commission_structures.id", ondelete="SET NULL"), nullable=True)
    rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    seller_share_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    agreement_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agreement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNRELEASED", index=True)
    approval_status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING", index=True)
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    released_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The supporting commission voucher in the document repository.
    voucher_document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class CommissionRelease(Base):
    """One payout of a commission: all at once ("isang bagsakan") or in parts
    (paonti-onti), each with how and through which bank it was paid."""

    __tablename__ = "commission_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commission_records.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    released_on: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    particulars: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
