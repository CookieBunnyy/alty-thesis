from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.supabase import supabase
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services.client_sync import reconcile_client_for_property
from app.schemas.property_listing import (
    PropertyListingResponse,
    PropertyListingStatusSummary,
    PropertyListingUpdate,
)


router = APIRouter(
    prefix="/property-listings",
    tags=["Property Listings"],
)


PROPERTY_STATUSES = {
    "AVAILABLE",
    "RESERVED",
    "SOLD",
    "ON_HOLD",
    "UNAVAILABLE",
}


# =========================================================
# GET ALL PROPERTY LISTINGS
# =========================================================

@router.get(
    "",
    response_model=list[PropertyListingResponse],
)
def get_property_listings(
    db: Session = Depends(get_db),
):
    return (
        db.execute(
            select(PropertyListing).order_by(
                PropertyListing.listing_id
            )
        )
        .scalars()
        .all()
    )


# =========================================================
# PROPERTY STATUS SUMMARY
# =========================================================

@router.get(
    "/status-summary",
    response_model=PropertyListingStatusSummary,
)
def get_property_status_summary(
    db: Session = Depends(get_db),
):
    normalized_status = func.upper(
        func.coalesce(
            PropertyListing.status,
            "AVAILABLE",
        )
    )

    row = db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            normalized_status == "AVAILABLE",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            normalized_status == "RESERVED",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            normalized_status == "SOLD",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            normalized_status == "ON_HOLD",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            normalized_status == "UNAVAILABLE",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(PropertyListing.listing_id),
        )
    ).one()

    (
        available,
        reserved,
        sold,
        on_hold,
        unavailable,
        total,
    ) = map(int, row)

    return {
        "available": available,
        "reserved": reserved,
        "sold": sold,
        "on_hold": on_hold,
        "unavailable": unavailable,
        "total": total,
    }


# =========================================================
# CREATE PROPERTY LISTING
# =========================================================

@router.post(
    "",
    status_code=status.HTTP_410_GONE,
)
def create_property_listing(
    _user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Property listings are created from validated property documents.",
    )


# =========================================================
# UPDATE PROPERTY LISTING
# =========================================================

@router.put(
    "/{listing_id}",
    response_model=PropertyListingResponse,
)
def update_property_listing(
    listing_id: int,
    payload: PropertyListingUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    listing = db.get(
        PropertyListing,
        listing_id,
    )

    if listing is None:
        raise HTTPException(
            status_code=404,
            detail="Property listing not found",
        )

    # Remember synchronization state BEFORE changing anything
    was_synced = listing.sync_status == "SYNCED"

    # IMPORTANT:
    # mode="json" converts Decimal values such as:
    #
    # Decimal("450000000.00")
    #
    # into JSON-compatible values before sending them
    # to Supabase.
    values = payload.model_dump(
        exclude_unset=True,
        mode="json",
    )

    # -----------------------------------------------------
    # Clean text fields
    # -----------------------------------------------------

    for field in (
        "layout_type",
        "village_name",
        "details",
    ):
        if field in values and values[field] is not None:
            values[field] = values[field].strip() or None

    # -----------------------------------------------------
    # Garage validation
    # -----------------------------------------------------

    if values.get("has_garage") is False:
        values["garage_spaces"] = 0

    # -----------------------------------------------------
    # Preserve current status
    # -----------------------------------------------------

    if (
        "status" not in values
        or values["status"] is None
    ):
        values["status"] = (
            listing.status
            or "AVAILABLE"
        )

    # -----------------------------------------------------
    # Normalize status
    # -----------------------------------------------------

    property_status = str(
        values["status"]
    ).strip().upper()

    property_status = property_status.replace(
        " ",
        "_",
    )

    if property_status not in PROPERTY_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid property status. "
                "Allowed values: AVAILABLE, RESERVED, "
                "SOLD, ON_HOLD, UNAVAILABLE."
            ),
        )

    values["status"] = property_status

    # -----------------------------------------------------
    # Prepare Supabase payload
    # -----------------------------------------------------

    cloud_values = dict(values)

    # These fields belong only to local PostgreSQL.
    cloud_values.pop(
        "sync_status",
        None,
    )

    cloud_values.pop(
        "last_synced_at",
        None,
    )

    # -----------------------------------------------------
    # Update Supabase
    # -----------------------------------------------------

    if was_synced:

        try:
            result = (
                supabase
                .table("listings")
                .update(cloud_values)
                .eq(
                    "listing_id",
                    listing_id,
                )
                .select("listing_id")
                .execute()
            )

            if not result.data:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The property exists locally "
                        "but was not found in Supabase."
                    ),
                )

        except HTTPException:
            raise

        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Supabase update failed: {exc}"
                ),
            ) from exc

    # -----------------------------------------------------
    # Update Local PostgreSQL
    # -----------------------------------------------------

    for field, value in values.items():

        if hasattr(
            listing,
            field,
        ):
            setattr(
                listing,
                field,
                value,
            )

    reconcile_client_for_property(db, listing)

    # -----------------------------------------------------
    # Synchronization status
    # -----------------------------------------------------

    if was_synced:
        listing.sync_status = "SYNCED"
        listing.last_synced_at = datetime.utcnow()

    else:
        listing.sync_status = "PENDING"
        listing.last_synced_at = None

    # -----------------------------------------------------
    # Commit Local PostgreSQL
    # -----------------------------------------------------

    try:
        db.commit()

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to save property changes locally."
            ),
        ) from exc

    db.refresh(listing)

    return listing


# =========================================================
# DELETE PROPERTY LISTING
# =========================================================

@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_property_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    listing = db.get(
        PropertyListing,
        listing_id,
    )

    if listing is None:
        raise HTTPException(
            status_code=404,
            detail="Property listing not found",
        )

    transaction_count = db.scalar(
        select(func.count(PropertyTransaction.transaction_id)).where(
            PropertyTransaction.property_id == listing_id
        )
    ) or 0
    if transaction_count:
        raise HTTPException(
            status_code=409,
            detail=(
                "This property has transaction history and cannot be deleted. "
                "Keep the listing so its client and transaction records remain valid."
            ),
        )

    # -----------------------------------------------------
    # Delete from Supabase first when synchronized
    # -----------------------------------------------------

    if listing.sync_status == "SYNCED":

        try:
            result = (
                supabase
                .table("listings")
                .delete()
                .eq(
                    "listing_id",
                    listing_id,
                )
                .select("listing_id")
                .execute()
            )

            if not result.data:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The synced property was not "
                        "found in Supabase."
                    ),
                )

        except HTTPException:
            raise

        except Exception as exc:
            if "23503" in str(exc) or "foreign key" in str(exc).casefold():
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This property has related transaction records and "
                        "cannot be deleted."
                    ),
                ) from exc
            raise HTTPException(
                status_code=502,
                detail=(
                    "Unable to delete the synced "
                    f"property from Supabase: {exc}"
                ),
            ) from exc

    # -----------------------------------------------------
    # Delete Local PostgreSQL Record
    # -----------------------------------------------------

    db.delete(listing)

    try:
        db.commit()

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to delete property locally.",
        ) from exc

    return None


# =========================================================
# SYNCHRONIZE SUPABASE → LOCAL POSTGRESQL
# =========================================================

@router.post("/sync")
def sync_property_listings(
    db: Session = Depends(get_db),
):
    """
    Synchronize property listings from Supabase
    into the local PostgreSQL database.

    Supabase is treated as the cloud source
    for synchronized property listing records.
    """

    try:
        response = (
            supabase
            .table("listings")
            .select("*")
            .execute()
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve property listings "
                f"from Supabase: {exc}"
            ),
        ) from exc

    listings = response.data or []

    inserted = 0
    updated = 0
    errors = 0

    for data in listings:

        listing_id = data.get(
            "listing_id"
        )

        if listing_id is None:
            continue

        try:
            existing = db.execute(
                select(PropertyListing).where(
                    PropertyListing.listing_id
                    == listing_id
                )
            ).scalar_one_or_none()

            # -------------------------------------------------
            # Normalize cloud status
            # -------------------------------------------------

            cloud_status = str(
                data.get("status")
                or ""
            ).strip().upper()

            cloud_status = cloud_status.replace(
                " ",
                "_",
            )

            if cloud_status not in PROPERTY_STATUSES:
                cloud_status = "AVAILABLE"

            # -------------------------------------------------
            # Values synchronized from Supabase
            # -------------------------------------------------

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
                "status": cloud_status,
                "sync_status": "SYNCED",
                "last_synced_at": datetime.utcnow(),
            }
            if data.get("external_listing_id"):
                values["external_listing_id"] = data["external_listing_id"]

            # -------------------------------------------------
            # Existing local property
            # -------------------------------------------------

            if existing:
                if existing.sync_status == "SYNCED":
                    for field, value in values.items():
                        setattr(existing, field, value)
                elif data.get("external_listing_id") and not existing.external_listing_id:
                    existing.external_listing_id = data["external_listing_id"]
                listing_to_reconcile = existing
                updated += 1

            # -------------------------------------------------
            # New local property
            # -------------------------------------------------

            else:

                listing = PropertyListing(
                    listing_id=listing_id,
                    **values,
                )

                db.add(listing)
                listing_to_reconcile = listing
                inserted += 1

            reconcile_client_for_property(db, listing_to_reconcile)

        except Exception:
            errors += 1

    # ---------------------------------------------------------
    # Commit synchronization
    # ---------------------------------------------------------

    if errors == 0:

        try:
            db.commit()

        except Exception as exc:
            db.rollback()

            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to save synchronized "
                    f"property listings locally: {exc}"
                ),
            ) from exc

    else:
        db.rollback()

    return {
        "total": len(listings),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
    }