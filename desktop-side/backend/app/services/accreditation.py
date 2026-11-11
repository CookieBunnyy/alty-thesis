"""Developer accreditation and marketing approval.

Abellar Realty does not own the properties it sells: developers accredit
Abellar to market them. A listing may be approved for marketing (and shown on
the public website) only while its developer's accreditation of Abellar is
VERIFIED and not expired. When ``ACCREDITATION_REQUIRED`` is off (a setting
for a transition period), approval and the public filter don't check it.

Second interview: an accreditation covers either every project (nationwide),
the projects in a region, or only named projects / clusters; it usually
expires after a year and is renewed yearly. A listing under a
project-specific accreditation must be one of the named projects.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, column, exists, func, or_, select, true

from app.core.config import settings
from app.models.partner import Partner
from app.models.property_listing import PropertyListing


def covers_project(partner: Partner, project_name: str | None) -> bool:
    """A project-specific accreditation covers only the named projects."""
    if (partner.accreditation_scope or "ALL_PROJECTS") != "SPECIFIC_PROJECTS":
        return True
    wanted = " ".join((project_name or "").split()).casefold()
    return bool(wanted) and any(" ".join(str(p).split()).casefold() == wanted
                                for p in (partner.accreditation_projects or []))


def accreditation_of(partner: Partner | None, today: date | None = None,
                     listing: PropertyListing | None = None) -> dict:
    """Whether a listing with this developer may be marketed, and why not."""
    today = today or date.today()
    if partner is None:
        return {"valid": False, "status": "NO_DEVELOPER", "reason": "No developer is recorded for this listing."}
    if (partner.partner_type or "").upper() != "DEVELOPER":
        return {"valid": False, "status": "NOT_DEVELOPER",
                "reason": f"{partner.name} isn't recorded as a developer."}
    status = (partner.accreditation_status or "NONE").upper()
    base = {"partner_id": partner.id, "developer": partner.name, "reference": partner.accreditation_reference,
            "valid_until": partner.accreditation_valid_until, "scope": partner.accreditation_scope or "ALL_PROJECTS",
            "region": partner.accreditation_region, "projects": partner.accreditation_projects or []}
    if status != "VERIFIED":
        return {**base, "valid": False, "status": status,
                "reason": f"{partner.name}'s accreditation of Abellar Realty isn't verified ({status.lower()})."}
    if partner.accreditation_valid_until and partner.accreditation_valid_until < today:
        return {**base, "valid": False, "status": "EXPIRED",
                "reason": f"{partner.name}'s accreditation expired on {partner.accreditation_valid_until:%b %d, %Y}."}
    if listing is not None and not covers_project(partner, listing.project_name):
        named = ", ".join(partner.accreditation_projects or []) or "no projects yet"
        return {**base, "valid": False, "status": "PROJECT_NOT_COVERED",
                "reason": (f"{partner.name}'s accreditation covers only specific projects ({named}); "
                           f"“{listing.project_name or 'no project name'}” isn't one of them.")}
    expiring = bool(partner.accreditation_valid_until and (partner.accreditation_valid_until - today).days <= 30)
    return {**base, "valid": True, "status": "VERIFIED", "reason": None, "expiring_soon": expiring}


def marketing_of(listing: PropertyListing, partner: Partner | None) -> dict:
    """The listing's marketing state as the pages show it."""
    accreditation = accreditation_of(partner, listing=listing)
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
        or_(Partner.accreditation_scope != "SPECIFIC_PROJECTS",
            exists(select(1).select_from(func.json_array_elements_text(Partner.accreditation_projects)
                                         .table_valued("value"))
                   .where(func.lower(func.trim(column("value"))) == func.lower(func.trim(PropertyListing.project_name)))
                   .correlate(Partner, PropertyListing))),
    )
    return and_(PropertyListing.marketing_status == "APPROVED", accredited)
