"""Pull property listings from Supabase into local PostgreSQL.

Local rows with ``sync_status = PENDING`` (document-derived or edited but not
yet pushed) are never overwritten by the pull.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.supabase import supabase
from app.models.property_listing import PropertyListing
from app.services.client_sync import reconcile_property_status

PROPERTY_STATUSES = {"AVAILABLE", "RESERVED", "SOLD", "ON_HOLD", "UNAVAILABLE"}
SYNCED_FIELDS = (
    "title", "category", "price_total", "initial_dp", "monthly_rate", "num_bedrooms",
    "num_bathrooms", "layout_type", "village_name", "lat", "lng", "photos", "amenity_list",
    "nearby_places", "details", "nearby_establishments", "has_balcony", "has_kitchen",
    "has_backyard", "has_garage", "garage_spaces",
)


def sync_property_listings(db: Session) -> dict[str, Any]:
    response = supabase.table("listings").select("*").execute()
    listings: list[dict[str, Any]] = response.data or []
    inserted = updated = skipped = errors = 0
    messages: list[str] = []
    now = datetime.utcnow()

    for data in listings:
        listing_id = data.get("listing_id")
        if listing_id is None:
            continue
        try:
            values = {field: data.get(field) for field in SYNCED_FIELDS}
            values.update(sync_status="SYNCED", last_synced_at=now)
            if data.get("external_listing_id"):
                values["external_listing_id"] = data["external_listing_id"]
            cloud_status = str(data.get("status") or "").strip().upper().replace(" ", "_")
            cloud_status = cloud_status if cloud_status in PROPERTY_STATUSES else None

            existing = db.get(PropertyListing, listing_id)
            if existing is None:
                db.add(PropertyListing(
                    listing_id=listing_id, status=cloud_status or "AVAILABLE",
                    created_at=now, status_changed_at=now, **values,
                ))
                inserted += 1
            elif existing.sync_status == "PENDING":
                skipped += 1
            else:
                old_status = existing.status
                for field, value in values.items():
                    setattr(existing, field, value)
                if cloud_status is not None and cloud_status != old_status:
                    existing.status = cloud_status
                    reconcile_property_status(db, existing, old_status)
                updated += 1
        except Exception as exc:
            errors += 1
            messages.append(f"listing {listing_id}: {type(exc).__name__}: {exc}")

    if errors == 0:
        db.commit()
    else:
        db.rollback()
    return {
        "total": len(listings), "inserted": inserted, "updated": updated,
        "skipped_pending": skipped, "errors": errors, "error_messages": messages[:20],
    }
