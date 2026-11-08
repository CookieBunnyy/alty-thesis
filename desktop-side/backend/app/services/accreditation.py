"""Developer accreditation and marketing approval.

Abellar Realty does not own the properties it sells: developers accredit
Abellar to market them. A listing may be approved for marketing (and shown on
the public website) only while its developer's accreditation of Abellar is
VERIFIED and not expired. When ``ACCREDITATION_REQUIRED`` is off (a setting
for a transition period), approval and the public filter don't check it.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, exists, func, or_, true

from app.core.config import settings
from app.models.partner import Partner
from app.models.property_listing import PropertyListing


def accreditation_of(partner: Partner | None, today: date | None = None) -> dict:
    """Whether a listing with this developer may be marketed, and why not."""
    today = today or date.today()
    if partner is None:
        return {"valid": False, "status": "NO_DEVELOPER", "reason": "No developer is recorded for this listing."}
    if (partner.partner_type or "").upper() != "DEVELOPER":
        return {"valid": False, "status": "NOT_DEVELOPER",
                "reason": f"{partner.name} isn't recorded as a developer."}
    status = (partner.accreditation_status or "NONE").upper()
    base = {"partner_id": partner.id, "developer": partner.name, "reference": partner.accreditation_reference,
            "valid_until": partner.accreditation_valid_until}
    if status != "VERIFIED":
        return {**base, "valid": False, "status": status,
                "reason": f"{partner.name}'s accreditation of Abellar Realty isn't verified ({status.lower()})."}
    if partner.accreditation_valid_until and partner.accreditation_valid_until < today:
        return {**base, "valid": False, "status": "EXPIRED",
                "reason": f"{partner.name}'s accreditation expired on {partner.accreditation_valid_until:%b %d, %Y}."}
    return {**base, "valid": True, "status": "VERIFIED", "reason": None}


def marketing_of(listing: PropertyListing, partner: Partner | None) -> dict:
    """The listing's marketing state as the pages show it."""
    accreditation = accreditation_of(partner)
    approved = listing.marketing_status == "APPROVED"
    return {"status": listing.marketing_status, "approved_by": listing.marketing_approved_by,
            "approved_at": listing.marketing_approved_at, "accreditation": accreditation,
            "can_approve": accreditation["valid"] or not settings.ACCREDITATION_REQUIRED,
            # With the requirement off, every listing is public (as the list filter does).
            "public": not settings.ACCREDITATION_REQUIRED or (approved and accreditation["valid"])}


def marketable_clause():
    """SQL condition: approved for marketing, with currently valid accreditation."""
    if not settings.ACCREDITATION_REQUIRED:
        return true()
    accredited = exists().where(
        Partner.id == PropertyListing.partner_id,
        func.upper(Partner.partner_type) == "DEVELOPER",
        Partner.accreditation_status == "VERIFIED",
        or_(Partner.accreditation_valid_until.is_(None), Partner.accreditation_valid_until >= date.today()),
    )
    return and_(PropertyListing.marketing_status == "APPROVED", accredited)
