"""Pages for seller (agent) accounts: only their own and permitted records.

A seller sees the listings assigned to them plus the listings currently
approved for marketing, may update the permitted fields of their assigned
listings, and sees no company-wide figures or other sellers' records. A
seller may add a property (POST /property-listings) and keep editing every
field of it until the Administrator approves it for marketing.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.v1.public import NOT_TEST_DATA, _labelled_media, _media_urls, _public_listing
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_seller_user
from app.models.listing_assignment import ListingAssignment
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.schemas.property_listing import PropertyListingUpdate
from app.services.accreditation import marketable_clause, marketing_of
from app.services.audit import record_audit

router = APIRouter(prefix="/seller", tags=["Seller"])


def editable_fields() -> set[str]:
    return {f.strip() for f in settings.SELLER_EDITABLE_LISTING_FIELDS.split(",") if f.strip()}


# Every field of a property the seller added themselves, until approved.
OWN_DRAFT_FIELDS = {
    "title", "category", "project_name", "partner_id", "price_total", "initial_dp", "monthly_rate",
    "num_bedrooms", "num_bathrooms", "layout_type", "village_name", "lat", "lng", "amenity_list", "details",
    "has_balcony", "has_kitchen", "has_backyard", "has_garage", "garage_spaces", "lot_area_sqm", "floor_area_sqm",
    "property_status", "financing_options", "reservation_fee", "equity_terms_months",
}


def _own_draft(listing: PropertyListing, user: User) -> bool:
    return listing.submitted_by_user_id == user.id and listing.marketing_status != "APPROVED"


def _assigned_ids(db: Session, agent_id: str) -> set[int]:
    return set(db.scalars(select(ListingAssignment.listing_id).where(
        ListingAssignment.agent_id == agent_id, ListingAssignment.removed_at.is_(None))))


@router.get("/listings")
def my_listings(db: Session = Depends(get_db), user: User = Depends(get_seller_user)):
    """Listings assigned to me, and the other listings approved for marketing."""
    assigned = _assigned_ids(db, user.agent_id)
    available = and_(PropertyListing.status == "AVAILABLE", NOT_TEST_DATA, marketable_clause())
    rows = db.execute(select(PropertyListing).where(or_(PropertyListing.listing_id.in_(assigned or [-1]), available))
                      .order_by(PropertyListing.title)).scalars().all()
    ids = [r.listing_id for r in rows]
    media, labelled = _media_urls(db, ids), _labelled_media(db, ids)
    partners = {p.id: p for p in db.execute(select(Partner)).scalars()}
    fields = sorted(editable_fields())

    def item(r: PropertyListing) -> dict:
        mine = r.listing_id in assigned
        own = _own_draft(r, user)
        return {**_public_listing(r, media.get(r.listing_id, []), labelled[r.listing_id]), "assigned": mine,
                "partner_id": r.partner_id,
                "developer": partners[r.partner_id].name if r.partner_id in partners else None,
                "marketing_status": marketing_of(r, partners.get(r.partner_id))["status"],
                "submitted_by_me": r.submitted_by_user_id == user.id,
                "editable_fields": sorted(OWN_DRAFT_FIELDS | set(fields)) if own else (fields if mine else [])}
    return [item(r) for r in rows]


@router.get("/developers")
def developers(db: Session = Depends(get_db), _user: User = Depends(get_seller_user)):
    """Developers a seller can choose when adding a property."""
    rows = db.execute(select(Partner).where(Partner.partner_type == "DEVELOPER", Partner.status == "ACTIVE")
                      .order_by(Partner.name)).scalars().all()
    return [{"id": p.id, "name": p.name, "status": p.status,
             "accredited": p.accreditation_status == "VERIFIED"} for p in rows]


@router.put("/listings/{listing_id}")
def update_my_listing(listing_id: int, payload: dict[str, Any], db: Session = Depends(get_db),
                      user: User = Depends(get_seller_user)):
    """Update the permitted fields of a listing assigned to me."""
    if listing_id not in _assigned_ids(db, user.agent_id):
        raise HTTPException(status_code=403, detail="You can only update listings assigned to you")
    listing = db.get(PropertyListing, listing_id)
    own = _own_draft(listing, user)
    allowed = editable_fields() | (OWN_DRAFT_FIELDS if own else set())
    refused = sorted(set(payload) - allowed)
    if refused:
        raise HTTPException(status_code=403, detail=f"Sellers can't change: {', '.join(refused)}")
    if own:
        try:  # same types and limits as the Administrator's edit
            payload = PropertyListingUpdate(**payload).model_dump(exclude_unset=True)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
        partner_id = payload.get("partner_id")
        if "partner_id" in payload:
            partner = db.get(Partner, partner_id) if partner_id is not None else None
            if partner is None or (partner.partner_type or "").upper() != "DEVELOPER":
                raise HTTPException(status_code=422, detail="Choose the developer this property belongs to")
    changes = {}
    for field, value in payload.items():
        if own:
            if getattr(listing, field) != value:
                changes[field] = {"old": str(getattr(listing, field)), "new": str(value)}
                setattr(listing, field, value)
            continue
        if field == "details" and value is not None and not isinstance(value, str):
            raise HTTPException(status_code=422, detail="details must be text")
        if field != "details" and value is not None and not isinstance(value, (list, dict)):
            raise HTTPException(status_code=422, detail=f"{field} must be a list")
        if getattr(listing, field) != value:
            changes[field] = {"old": getattr(listing, field), "new": value}
            setattr(listing, field, value)
    if changes:
        listing.sync_status = "PENDING"
        record_audit(db, "PROPERTY_UPDATED_BY_SELLER", actor=user, entity_type="property_listings",
                     entity_id=listing_id, details={"agent_id": user.agent_id, "changes": changes})
    db.commit()
    db.refresh(listing)
    return {**_public_listing(listing, _media_urls(db, [listing_id]).get(listing_id, []),
                              _labelled_media(db, [listing_id])[listing_id]), "assigned": True,
            "partner_id": listing.partner_id, "submitted_by_me": listing.submitted_by_user_id == user.id,
            "editable_fields": sorted(allowed)}
