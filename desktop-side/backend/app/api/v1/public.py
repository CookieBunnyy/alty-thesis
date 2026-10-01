"""Public (unauthenticated) endpoints used by the website.

The website reads live property data and submits client transactions here;
it never writes to Supabase or keeps its own transaction store. Submissions
go through the same matching and property-lifecycle rules as documents.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.agent import Agent
from app.models.media import PropertyMedia
from app.models.property_listing import PropertyListing
from app.services.audit import WEBSITE, record_audit
from app.services.cloud_sync import try_push_pending
from app.services.document_processing import Context, ProcessingError, apply_transaction, new_result
from app.services.document_storage import StorageError, read_file

router = APIRouter(prefix="/public", tags=["Public website"])

PUBLIC_STATUSES = {"AVAILABLE", "RESERVED", "SOLD"}
MEDIA_OK = {"GOOD", "ACCEPTABLE"}


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 3600.0) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status_code=429, detail="Too many submissions; try again later.")
            hits.append(now)


rate_limiter = _RateLimiter()


def _media_urls(db: Session, listing_ids: list[int]) -> dict[int, list[str]]:
    if not listing_ids:
        return {}
    rows = db.execute(
        select(PropertyMedia.listing_id, PropertyMedia.id)
        .where(PropertyMedia.listing_id.in_(listing_ids), PropertyMedia.quality_status.in_(MEDIA_OK))
        .order_by(PropertyMedia.created_at)
    ).all()
    urls: dict[int, list[str]] = defaultdict(list)
    for listing_id, media_id in rows:
        urls[listing_id].append(f"/api/v1/public/media/{media_id}")
    return urls


def _public_listing(listing: PropertyListing, media: list[str]) -> dict:
    number = lambda value: float(value) if value is not None else None  # noqa: E731
    return {
        "listing_id": listing.listing_id,
        "listing_code": listing.external_listing_id,
        "title": listing.title,
        "category": listing.category,
        "price_total": number(listing.price_total),
        "initial_dp": number(listing.initial_dp),
        "monthly_rate": number(listing.monthly_rate),
        "num_bedrooms": listing.num_bedrooms,
        "num_bathrooms": listing.num_bathrooms,
        "layout_type": listing.layout_type,
        "village_name": listing.village_name,
        "lat": number(listing.lat),
        "lng": number(listing.lng),
        "photos": list(listing.photos or []),
        "media": media,
        "amenity_list": listing.amenity_list,
        "nearby_places": listing.nearby_places,
        "nearby_establishments": listing.nearby_establishments,
        "details": listing.details,
        "has_balcony": listing.has_balcony,
        "has_kitchen": listing.has_kitchen,
        "has_backyard": listing.has_backyard,
        "has_garage": listing.has_garage,
        "garage_spaces": listing.garage_spaces,
        "status": listing.status,
    }


@router.get("/properties")
def list_public_properties(status: str = "AVAILABLE", mapped_only: bool = False,
                           db: Session = Depends(get_db)):
    wanted = {part.strip().upper() for part in status.split(",")} & PUBLIC_STATUSES
    if not wanted:
        raise HTTPException(status_code=422, detail="status must be AVAILABLE, RESERVED or SOLD")
    statement = select(PropertyListing).where(PropertyListing.status.in_(wanted))
    if mapped_only:
        statement = statement.where(PropertyListing.lat.is_not(None), PropertyListing.lng.is_not(None))
    listings = db.execute(statement.order_by(PropertyListing.listing_id)).scalars().all()
    media = _media_urls(db, [listing.listing_id for listing in listings])
    return [_public_listing(listing, media.get(listing.listing_id, [])) for listing in listings]


@router.get("/properties/{listing_id}")
def get_public_property(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(PropertyListing, listing_id)
    if listing is None or listing.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Property not found")
    return _public_listing(listing, _media_urls(db, [listing_id]).get(listing_id, []))


@router.get("/agents")
def list_public_agents(db: Session = Depends(get_db)):
    agents = db.execute(
        select(Agent).where(func.upper(Agent.status) == "ACTIVE").order_by(Agent.full_name)
    ).scalars().all()
    return [{"agent_id": a.agent_id, "full_name": a.full_name, "agent_location": a.agent_location,
             "star_rating": float(a.star_rating) if a.star_rating is not None else None}
            for a in agents]


@router.get("/media/{media_id}")
def get_public_media(media_id: int, db: Session = Depends(get_db)):
    media = db.get(PropertyMedia, media_id)
    listing = db.get(PropertyListing, media.listing_id) if media else None
    if media is None or media.quality_status not in MEDIA_OK or listing is None \
            or listing.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        content = read_file(media.storage_bucket, media.storage_path)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="Media unavailable") from exc
    return Response(content=content, media_type=media.mime_type,
                    headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})


class WebsiteTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int
    agent_id: str = Field(min_length=1, max_length=32)
    transaction_type: str = Field(pattern="^(RESERVED|SOLD)$")
    full_name: str = Field(min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone_number: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=255)

    @field_validator("full_name", "phone_number", "location", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return (" ".join(value.split()) or None) if isinstance(value, str) else value

    @model_validator(mode="after")
    def contact_required(self) -> "WebsiteTransaction":
        if not self.email and not self.phone_number:
            raise ValueError("Provide an email address or phone number so the agent can reach you")
        return self


@router.post("/transactions", status_code=201)
def submit_website_transaction(payload: WebsiteTransaction, request: Request,
                               db: Session = Depends(get_db)):
    """USER SELECTS PROPERTY -> FORM -> validate property & status -> create or
    match client -> create transaction -> update property status."""
    rate_limiter.check(request.client.host if request.client else "unknown",
                       settings.PUBLIC_SUBMISSIONS_PER_HOUR)
    listing = db.get(PropertyListing, payload.property_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if listing.price_total is None:
        raise HTTPException(status_code=409, detail="This property has no listed price yet; contact an agent.")
    agent = db.get(Agent, payload.agent_id)
    if agent is None or str(agent.status or "").upper() != "ACTIVE":
        raise HTTPException(status_code=422, detail="Choose an active agent")

    fields = {
        "listing_id": str(listing.listing_id),
        "agent_id": agent.agent_id,
        "full_name": payload.full_name,
        "email": str(payload.email).casefold() if payload.email else None,
        "contact_number": payload.phone_number,
        "address": payload.location,
        "transaction_date": datetime.now(timezone.utc),
        # The website records the listed contract price; reservation fees and
        # payments are captured later from receipts/agreements.
        "amount": listing.price_total,
    }
    fields = {key: value for key, value in fields.items() if value is not None}
    result = new_result(None, None, "WEBSITE")
    context = Context(db, None, "WEBSITE_TRANSACTION", fields, result, source="WEBSITE")
    savepoint = db.begin_nested()
    try:
        apply_transaction(context, payload.transaction_type)
        db.flush()
    except ProcessingError as exc:
        savepoint.rollback()
        record_audit(db, "WEBSITE_TRANSACTION_REJECTED", actor=WEBSITE, entity_type="property_listings",
                     entity_id=listing.listing_id, result="FAILED",
                     details={"stage": exc.stage, "reason": str(exc),
                              "transaction_type": payload.transaction_type})
        db.commit()
        status = 409 if exc.stage in {"ENTITY_MATCHING", "DUPLICATE_CHECK"} else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    savepoint.commit()
    for event in context.events:
        record_audit(db, event["action"], actor=WEBSITE, entity_type=event["entity_type"],
                     entity_id=event["entity_id"], details={**event["details"], "source": "WEBSITE"})
    db.commit()
    try_push_pending(db)
    matched = result["matched_entities"]
    return {
        "status": "SUCCESS",
        "already_recorded": result["idempotent"],
        "transaction_id": matched.get("transaction", {}).get("id"),
        "client_id": matched.get("client", {}).get("id"),
        "property_id": listing.listing_id,
        "property_status": listing.status,
        "transaction_type": payload.transaction_type,
        "message": (
            "Your request was already recorded." if result["idempotent"]
            else "Your request was recorded. An agent will contact you."
        ),
    }
