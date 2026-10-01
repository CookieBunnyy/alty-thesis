"""Public map endpoints used by the website (no authentication).

Website -> /api/v1/map/* -> routing / traffic / geocoding services -> provider.
Provider credentials stay on the server; provider errors are mapped to
user-safe messages and never passed through raw.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.api.v1.public import _RateLimiter
from app.core.config import settings
from app.services import geocoding, routing
from app.services.routing import MODE_LABELS, MODES, Point, RoutingError
from app.services.traffic import TrafficUnavailable, get_traffic_provider

router = APIRouter(prefix="/map", tags=["Public map"])

map_limiter = _RateLimiter()
BUSY = "Too many map requests; please wait a moment."


def _limit(request: Request) -> None:
    map_limiter.check(request.client.host if request.client else "unknown",
                      settings.MAP_REQUESTS_PER_MINUTE, window=60.0, detail=BUSY)


def _point(lat: float, lng: float) -> Point:
    try:
        return Point(lat, lng)
    except RoutingError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc


@router.get("/capabilities")
def map_capabilities():
    """What the configured providers can really do (the UI shows only this)."""
    provider = routing.get_provider()
    return {
        "routing": {
            "provider": provider.name,
            "available": bool(provider.modes),
            "attribution": provider.attribution,
            "alternatives": provider.supports_alternatives,
            # Car / motorcycle travel times include current traffic.
            "live_traffic": provider.live_traffic,
            "modes": {mode: {"label": MODE_LABELS[mode], "supported": mode in provider.modes} for mode in MODES},
        },
        "traffic": get_traffic_provider().status(),
    }


@router.get("/route")
def map_route(request: Request,
              origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float,
              mode: str = Query("driving", pattern="^(walking|bicycle|motorcycle|driving)$"),
              alternatives: bool = True):
    """Road route(s) for one travel mode."""
    _limit(request)
    origin, destination = _point(origin_lat, origin_lng), _point(dest_lat, dest_lng)
    provider = routing.get_provider()
    try:
        routes = provider.calculate_alternative_routes(origin, destination, mode, alternatives)
    except RoutingError as exc:
        status = 422 if exc.code in {"unsupported", "invalid"} else 404 if exc.code == "no_route" else 503
        raise HTTPException(status_code=status, detail=exc.message) from exc
    return {"provider": provider.name, "mode": mode, "attribution": provider.attribution,
            "routes": routing.compare_routes(routes),
            "straight_line_m": round(routing.haversine_m(origin, destination), 1),
            "live_traffic": provider.live_traffic}


@router.get("/commute")
def map_commute(request: Request,
                origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float,
                alternatives: bool = True):
    """Workplace -> property accessibility: every mode with its own status.

    With a live-traffic provider (``live_traffic`` true) car and motorcycle
    durations are travel times *now*, and each route carries its traffic
    delay, free-flow and typical times and congested stretches. Otherwise
    durations are the engine's typical times."""
    _limit(request)
    result = routing.commute(_point(origin_lat, origin_lng), _point(dest_lat, dest_lng), alternatives)
    return {**result, "traffic": get_traffic_provider().status()}


@router.get("/geocode")
def map_geocode(request: Request, q: str = Query(min_length=2, max_length=200)):
    _limit(request)
    try:
        return {"results": geocoding.search_places(q)}
    except geocoding.GeocodingError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc


@router.get("/reverse-geocode")
def map_reverse_geocode(request: Request, lat: float, lng: float):
    _limit(request)
    point = _point(lat, lng)
    try:
        return {"result": geocoding.reverse_place(point.lat, point.lng)}
    except geocoding.GeocodingError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc


@router.get("/traffic")
def map_traffic():
    return get_traffic_provider().status()


@router.get("/traffic/tiles/{z}/{x}/{y}.png")
def map_traffic_tile(z: int, x: int, y: int, theme: str = Query("light", pattern="^(light|dark)$")):
    if not 0 <= z <= 22 or not 0 <= x < 2 ** z or not 0 <= y < 2 ** z:
        raise HTTPException(status_code=404, detail="Tile not found")
    try:
        content = get_traffic_provider().fetch_tile(z, x, y, theme)
    except TrafficUnavailable as exc:
        raise HTTPException(status_code=503, detail="Live traffic data is not available.") from exc
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "public, max-age=60"})
