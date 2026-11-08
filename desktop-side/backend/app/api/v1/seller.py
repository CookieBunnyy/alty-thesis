"""Pages for seller (agent) accounts: only their own and permitted records.

A seller sees the listings assigned to them plus the listings currently
approved for marketing, may update the permitted fields of their assigned
listings, and sees no company-wide figures or other sellers' records.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.v1.public import NOT_TEST_DATA, _media_urls, _public_listing
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_seller_user
from app.models.listing_assignment import ListingAssignment
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services.accreditation import marketable_clause, marketing_of
from app.services.audit import record_audit

router = APIRouter(prefix="/seller", tags=["Seller"])


def editable_fields() -> set[str]:
    return {f.strip() for f in settings.SELLER_EDITABLE_LISTING_FIELDS.split(",") if f.strip()}


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
    media = _media_urls(db, [r.listing_id for r in rows])
    partners = {p.id: p for p in db.execute(select(Partner)).scalars()}
    fields = sorted(editable_fields())
    return [{**_public_listing(r, media.get(r.listing_id, [])), "assigned": r.listing_id in assigned,
             "developer": partners[r.partner_id].name if r.partner_id in partners else None,
             "marketing_status": marketing_of(r, partners.get(r.partner_id))["status"],
             "editable_fields": fields if r.listing_id in assigned else []} for r in rows]


@router.put("/listings/{listing_id}")
def update_my_listing(listing_id: int, payload: dict[str, Any], db: Session = Depends(get_db),
                      user: User = Depends(get_seller_user)):
    """Update the permitted fields of a listing assigned to me."""
    if listing_id not in _assigned_ids(db, user.agent_id):
        raise HTTPException(status_code=403, detail="You can only update listings assigned to you")
    allowed = editable_fields()
    refused = sorted(set(payload) - allowed)
    if refused:
        raise HTTPException(status_code=403, detail=f"Sellers can't change: {', '.join(refused)}")
    listing = db.get(PropertyListing, listing_id)
    changes = {}
    for field, value in payload.items():
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
    return {**_public_listing(listing, _media_urls(db, [listing_id]).get(listing_id, [])), "assigned": True,
            "editable_fields": sorted(allowed)}
