from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.supabase import supabase
from app.models.property_listing import PropertyListing


def sync_property_listings(db: Session) -> dict[str, int]:
    """
    Synchronize property listings from Supabase into local PostgreSQL.

    Supabase is treated as the source of property listing data.
    PostgreSQL stores the local operational copy used by FastAPI/Desktop.
    """

    response = (
        supabase
        .table("listings")
        .select("*")
        .execute()
    )

    listings: list[dict[str, Any]] = response.data or []

    inserted = 0
    updated = 0
    errors = 0

    for data in listings:
        listing_id = data.get("listing_id")

        if listing_id is None:
            continue

        try:
            existing = db.execute(
                select(PropertyListing).where(
                    PropertyListing.listing_id == listing_id
                )
            ).scalar_one_or_none()

            values = {
                "title": data.get("title"),
                "category": data.get("category"),
                "price_total": data.get("price_total"),
                "initial_dp": data.get("initial_dp"),
                "monthly_rate": data.get("monthly_rate"),
                "num_bedrooms": data.get("num_bedrooms"),
                "num_bathrooms": data.get("num_bathrooms"),
                "layout_type": data.get("layout_type"),
                "village_name": data.get("village_name"),
                "lat": data.get("lat"),
                "lng": data.get("lng"),
                "photos": data.get("photos"),
                "amenity_list": data.get("amenity_list"),
                "nearby_places": data.get("nearby_places"),
                "details": data.get("details"),
                "nearby_establishments": data.get(
                    "nearby_establishments"
                ),
                "has_balcony": data.get("has_balcony"),
                "has_kitchen": data.get("has_kitchen"),
                "has_backyard": data.get("has_backyard"),
                "has_garage": data.get("has_garage"),
                "garage_spaces": data.get("garage_spaces"),
                "sync_status": "SYNCED",
                "last_synced_at": datetime.utcnow(),
            }

            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)

                updated += 1

            else:
                listing = PropertyListing(
                    listing_id=listing_id,
                    **values,
                )

                db.add(listing)
                inserted += 1

        except Exception:
            errors += 1

    if errors == 0:
        db.commit()
    else:
        db.rollback()

    return {
        "total": len(listings),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }