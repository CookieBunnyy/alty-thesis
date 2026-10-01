"""Place search for the website's workplace picker (Nominatim).

Follows the Nominatim usage policy: an identifying User-Agent, at most one
request per second (requests are serialised), results cached, and searches
only on submit (the website never searches on each keystroke).
"""

from __future__ import annotations

import threading
import time

import httpx

from app.core.config import settings


class GeocodingError(Exception):
    message = "Place search is currently unavailable. Please try again."


_lock = threading.Lock()
_last_request = 0.0
_cache: dict[tuple, list[dict]] = {}
_client: httpx.Client | None = None


def _get(path: str, params: dict) -> object:
    global _last_request, _client
    if _client is None:
        _client = httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS,
                               headers={"User-Agent": settings.GEOCODER_USER_AGENT})
    with _lock:
        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            response = _client.get(f"{settings.GEOCODER_URL.rstrip('/')}/{path}",
                                   params={**params, "format": "jsonv2"})
        except httpx.HTTPError as exc:
            raise GeocodingError() from exc
        finally:
            _last_request = time.monotonic()
    if response.status_code != 200:
        raise GeocodingError()
    return response.json()


def _place(row: dict) -> dict:
    return {"name": row.get("name") or row.get("display_name", "").split(",")[0],
            "address": row.get("display_name", ""),
            "lat": float(row["lat"]), "lng": float(row["lon"])}


def search_places(query: str, limit: int = 5) -> list[dict]:
    key = ("search", query.strip().casefold(), limit)
    if key not in _cache:
        params = {"q": query, "limit": limit, "addressdetails": 0}
        if settings.GEOCODER_COUNTRY_CODES:
            params["countrycodes"] = settings.GEOCODER_COUNTRY_CODES
        rows = _get("search", params)
        _cache[key] = [_place(row) for row in rows if row.get("lat") and row.get("lon")]
    return _cache[key]


def reverse_place(lat: float, lng: float) -> dict | None:
    key = ("reverse", round(lat, 5), round(lng, 5))
    if key not in _cache:
        row = _get("reverse", {"lat": lat, "lon": lng, "zoom": 17})
        _cache[key] = [_place(row)] if isinstance(row, dict) and row.get("lat") else []
    return (_cache[key] or [None])[0]
