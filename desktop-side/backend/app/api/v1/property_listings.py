"""Property listings.

There is no create endpoint: listings enter the system from Property
Information documents or from the central (Supabase) listing sync.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import FILING_ROLES, get_current_user, require_management, require_roles
from app.core.supabase import supabase
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.property_listing import (
    PropertyListingResponse,
    PropertyListingStatusSummary,
    PropertyListingUpdate,
)
from app.services.audit import record_audit
from app.services.client_sync import reconcile_property_status
from app.services.cloud_sync import cloud_sync_enabled, try_push_pending
from app.services.property_listing_sync import sync_property_listings as pull_listings

router = APIRouter(prefix="/property-listings", tags=["Property Listings"])

PROPERTY_STATUSES = ("AVAILABLE", "RESERVED", "SOLD", "ON_HOLD", "UNAVAILABLE")
MANUAL_STATUSES = {"AVAILABLE", "ON_HOLD", "UNAVAILABLE"}
require_editor = require_roles(*FILING_ROLES)


def _listing_or_404(db: Session, listing_id: int) -> PropertyListing:
    listing = db.get(PropertyListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Property listing not found")
    return listing


@router.get("", response_model=list[PropertyListingResponse])
def get_property_listings(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(PropertyListing)
    if status_filter:
        statement = statement.where(PropertyListing.status == status_filter.upper())
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(
            PropertyListing.title.ilike(pattern), PropertyListing.village_name.ilike(pattern),
            PropertyListing.category.ilike(pattern), PropertyListing.external_listing_id.ilike(pattern),
        ))
    return db.execute(
        statement.order_by(PropertyListing.listing_id).offset(offset).limit(limit)
    ).scalars().all()


@router.get("/status-summary", response_model=PropertyListingStatusSummary)
def get_property_status_summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.execute(
        select(func.upper(PropertyListing.status), func.count()).group_by(func.upper(PropertyListing.status))
    ).all()
    counts = {str(name): int(total) for name, total in rows}
    return {**{name.lower(): counts.get(name, 0) for name in PROPERTY_STATUSES},
            "total": sum(counts.values())}


@router.get("/{listing_id}", response_model=PropertyListingResponse)
def get_property_listing(listing_id: int, db: Session = Depends(get_db),
                         _user: User = Depends(get_current_user)):
    return _listing_or_404(db, listing_id)


@router.get("/{listing_id}/history")
def get_property_history(listing_id: int, db: Session = Depends(get_db),
                         _user: User = Depends(get_current_user)):
    """Transactions (reservation -> sale) and documents for one property."""
    listing = _listing_or_404(db, listing_id)
    transactions = db.execute(
        select(PropertyTransaction).where(PropertyTransaction.property_id == listing_id)
        .order_by(PropertyTransaction.transaction_date, PropertyTransaction.created_at)
    ).scalars().all()
    documents = db.execute(
        select(Document).where(Document.property_listing_id == listing_id)
        .order_by(Document.created_at.desc())
    ).scalars().all()
    return {
        "listing_id": listing.listing_id,
        "external_listing_id": listing.external_listing_id,
        "status": listing.status,
        "status_changed_at": listing.status_changed_at,
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "external_transaction_id": t.external_transaction_id,
                "client_id": t.client_id,
                "client_name": t.client.full_name,
                "agent_id": t.agent_id,
                "agent_name": t.agent.full_name,
                "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date,
                "amount": float(t.amount),
                "status": t.status,
                "source": t.source,
            }
            for t in transactions
        ],
        "documents": [
            {"document_id": d.document_id, "document_name": d.document_name,
             "document_type": d.document_type, "status": d.status, "created_at": d.created_at}
            for d in documents
        ],
    }


@router.put("/{listing_id}", response_model=PropertyListingResponse)
def update_property_listing(listing_id: int, payload: PropertyListingUpdate,
                            db: Session = Depends(get_db), user: User = Depends(require_editor)):
    listing = _listing_or_404(db, listing_id)
    values = payload.model_dump(exclude_unset=True)
    for field in ("layout_type", "village_name", "details"):
        if isinstance(values.get(field), str):
            values[field] = values[field].strip() or None
    if values.get("has_garage") is False:
        values["garage_spaces"] = 0

    old_status = listing.status
    new_status = values.pop("status", None) or old_status
    new_status = str(new_status).strip().upper().replace(" ", "_")
    if new_status not in PROPERTY_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid property status")
    if new_status != old_status:
        if new_status not in MANUAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"{new_status} is set by a reservation or sale document, not by editing.",
            )
        if old_status == "SOLD":
            raise HTTPException(status_code=409, detail="A SOLD property's status cannot be edited.")

    changes = {}
    for field, value in values.items():
        if hasattr(listing, field) and getattr(listing, field) != value:
            changes[field] = {"old": str(getattr(listing, field)), "new": str(value)}
            setattr(listing, field, value)
    notes: list[str] = []
    if new_status != old_status:
        listing.status = new_status
        changes["status"] = {"old": old_status, "new": new_status}
        notes = reconcile_property_status(db, listing, old_status)
    if changes:
        listing.sync_status = "PENDING"
        record_audit(db, "PROPERTY_UPDATED", actor=user, entity_type="property_listings",
                     entity_id=listing_id, details={"changes": changes, "consequences": notes})
    db.commit()
    if changes:
        try_push_pending(db)
    db.refresh(listing)
    return listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property_listing(listing_id: int, db: Session = Depends(get_db),
                            user: User = Depends(require_management)):
    listing = _listing_or_404(db, listing_id)
    transaction_count = db.scalar(
        select(func.count(PropertyTransaction.transaction_id)).where(
            PropertyTransaction.property_id == listing_id
        )
    ) or 0
    if transaction_count:
        raise HTTPException(
            status_code=409,
            detail="This property has transaction history and cannot be deleted. "
                   "Keep the listing so its client and transaction records remain valid.",
        )
    if listing.sync_status == "SYNCED" and cloud_sync_enabled():
        try:
            supabase.table("listings").delete().eq("listing_id", listing_id).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Unable to delete the synced property from Supabase: {exc}"
            ) from exc
    record_audit(db, "PROPERTY_DELETED", actor=user, entity_type="property_listings",
                 entity_id=listing_id, details={"title": listing.title,
                                                "external_listing_id": listing.external_listing_id})
    db.delete(listing)
    db.commit()
    return None


@router.post("/sync")
def sync_property_listings(db: Session = Depends(get_db), user: User = Depends(require_management)):
    """Pull listings from Supabase, then push local PENDING changes."""
    try:
        pulled = pull_listings(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to retrieve listings from Supabase: {exc}") from exc
    pushed = try_push_pending(db)
    record_audit(db, "PROPERTIES_SYNCED", actor=user, entity_type="property_listings",
                 details={"pulled": pulled, "pushed": pushed.get("tables", {}).get("listings")})
    db.commit()
    return {**pulled, "pushed": pushed}

