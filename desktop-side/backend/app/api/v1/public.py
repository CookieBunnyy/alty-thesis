"""Public (read-only) endpoints used by the website.

Anyone may read live property data, agents, reviews and the home page here.
Reservations and purchases are NOT made through the website: clients
contact an agent, and the transaction is recorded from the documents the
agent submits (Document Repository). The website never writes to Supabase.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_optional_client
from app.models.agent import Agent
from app.services import reviews as review_service
from app.models.media import PropertyMedia
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services.document_storage import StorageError, read_file

router = APIRouter(prefix="/public", tags=["Public website"])

PUBLIC_STATUSES = {"AVAILABLE", "RESERVED", "SOLD"}
MEDIA_OK = {"GOOD", "ACCEPTABLE"}


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 3600.0,
              detail: str = "Too many submissions; try again later.") -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status_code=429, detail=detail)
            hits.append(now)



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


def _active_agents(db: Session) -> list[Agent]:
    return list(db.execute(
        select(Agent).where(func.upper(Agent.status) == "ACTIVE").order_by(Agent.full_name)
    ).scalars())


def _public_agent(agent: Agent, stats: dict, viewer: User | None = None) -> dict:
    """Client-facing agent card. Ratings come from client reviews only.

    The phone number (Call / Text) is only given to signed-in website clients;
    everyone else gets ``contact_requires_sign_in`` instead."""
    return {
        "agent_id": agent.agent_id,
        "full_name": agent.full_name,
        "agent_location": agent.agent_location,
        "phone_number": agent.phone_number if viewer is not None else None,
        "has_phone": bool(agent.phone_number),
        "contact_requires_sign_in": viewer is None,
        "status": agent.status,
        **review_service.stats_for(stats, agent.agent_id),
        # Legacy/system rating synced from Supabase (not client reviews).
        "star_rating": float(agent.star_rating) if agent.star_rating is not None else None,
    }


@router.get("/agents")
def list_public_agents(db: Session = Depends(get_db), viewer: User | None = Depends(get_optional_client)):
    agents = _active_agents(db)
    stats = review_service.review_stats(db, [a.agent_id for a in agents])
    return [_public_agent(agent, stats, viewer) for agent in agents]


@router.get("/agents/{agent_id}")
def get_public_agent(agent_id: str, limit: int = 10, offset: int = 0, db: Session = Depends(get_db),
                     viewer: User | None = Depends(get_optional_client)):
    """Public agent profile with real client reviews (newest first)."""
    agent = db.get(Agent, agent_id)
    if agent is None or str(agent.status or "").upper() != "ACTIVE":
        raise HTTPException(status_code=404, detail="Agent not found")
    stats = review_service.review_stats(db, [agent_id])
    limit, offset = max(1, min(limit, 50)), max(0, offset)
    return {
        **_public_agent(agent, stats, viewer),
        "completed_sales": agent.completed_sales,
        "reviews": [review_service.public_review(r)
                    for r in review_service.recent_reviews(db, agent_id, limit, offset)],
    }


@router.get("/home")
def public_home(db: Session = Depends(get_db)):
    """Everything the home page shows, in one request, from live data only."""
    available = PropertyListing.status == "AVAILABLE"
    # Listings with photos first: the home page is a showcase.
    with_photos = func.coalesce(func.cardinality(PropertyListing.photos), 0) > 0
    featured = db.execute(
        select(PropertyListing).where(available, PropertyListing.price_total.is_not(None))
        .order_by(with_photos.desc(), PropertyListing.created_at.desc(), PropertyListing.listing_id.desc())
        .limit(6)
    ).scalars().all()
    media = _media_urls(db, [listing.listing_id for listing in featured])
    categories = db.execute(
        select(PropertyListing.category, func.count())
        .where(available).group_by(PropertyListing.category)
        .order_by(func.count().desc())
    ).all()
    agents = _active_agents(db)
    stats = review_service.review_stats(db, [a.agent_id for a in agents])
    agents.sort(key=lambda a: (-review_service.stats_for(stats, a.agent_id)["review_count"],
                               -(review_service.stats_for(stats, a.agent_id)["client_rating"] or 0),
                               a.full_name))
    return {
        "stats": {
            "available_properties": db.scalar(select(func.count()).select_from(PropertyListing).where(available)) or 0,
            "active_agents": len(agents),
            "client_reviews": review_service.overall_stats(db),
        },
        "featured_properties": [_public_listing(listing, media.get(listing.listing_id, []))
                                for listing in featured],
        "categories": [{"category": name or "Other", "count": count} for name, count in categories],
        "agents": [_public_agent(agent, stats) for agent in agents[:6]],
        "reviews": [review_service.public_review(r, include_agent=True)
                    for r in review_service.recent_reviews(db, limit=9, with_text_first=True)],
    }


@router.get("/properties/{listing_id}/nearby-agents")
def list_nearby_agents(listing_id: int, request: Request, limit: int = 5,
                       db: Session = Depends(get_db), viewer: User | None = Depends(get_optional_client)):
    """Active agents nearest to a property.

    Ranking uses *geographic* proximity (straight-line distance between the
    agent's and the property's coordinates). Road distance and travel time
    come from the routing provider when it can answer; otherwise they are
    null and ``routing.message`` says why. Only client-facing contact fields
    are returned (no sales, commission or performance figures)."""
    from app.api.v1.maps import _limit
    from app.services import routing

    _limit(request)
    listing = db.get(PropertyListing, listing_id)
    if listing is None or listing.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Property not found")
    limit = max(1, min(limit, 10))
    agents = db.execute(
        select(Agent).where(func.upper(Agent.status) == "ACTIVE").order_by(Agent.full_name)
    ).scalars().all()

    stats = review_service.review_stats(db, [a.agent_id for a in agents])

    def card(agent: Agent) -> dict:
        return {**_public_agent(agent, stats, viewer), "completed_sales": agent.completed_sales,
                "straight_line_km": None, "road_distance_km": None, "travel_time_min": None}

    property_point = None
    if listing.lat is not None and listing.lng is not None:
        property_point = routing.Point(float(listing.lat), float(listing.lng))
    located, unlocated = [], []
    for agent in agents:
        entry = card(agent)
        if property_point is not None and agent.latitude is not None and agent.longitude is not None:
            agent_point = routing.Point(float(agent.latitude), float(agent.longitude))
            entry["straight_line_km"] = round(routing.haversine_m(agent_point, property_point) / 1000, 2)
            located.append((entry, agent_point))
        else:
            unlocated.append(entry)
    located.sort(key=lambda pair: pair[0]["straight_line_km"])
    located = located[:limit]

    routing_status = {"available": False, "mode": "driving",
                      "message": "Road distances need the property's map location."}
    if located:
        provider = routing.get_provider()
        try:
            cells = provider.calculate_matrix([point for _, point in located], property_point, "driving")
            for (entry, _), cell in zip(located, cells):
                if cell is not None:
                    entry["road_distance_km"] = round(cell[0] / 1000, 2)
                    entry["travel_time_min"] = round(cell[1] / 60)
            routing_status = {"available": True, "mode": "driving", "provider": provider.name,
                              "live_traffic": provider.live_traffic,
                              "message": "Road distance and car travel time from the agent's base "
                                         + ("with current traffic." if provider.live_traffic
                                            else "(typical conditions, no live traffic).")}
        except routing.RoutingError as exc:
            routing_status = {"available": False, "mode": "driving", "message": exc.message}
    results = [entry for entry, _ in located] + unlocated[: max(0, limit - len(located))]
    return {"property_id": listing.listing_id, "property_status": listing.status,
            "ranking": "Geographic (straight-line) proximity to the property",
            "routing": routing_status, "agents": results}


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
