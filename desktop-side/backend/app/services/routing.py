"""Road-network routing for the website map.

Three different quantities are kept apart on purpose:

* geographic distance – straight line (haversine) between two coordinates;
  used only for *proximity* (e.g. ranking agents), never shown as travel;
* road distance       – length of a route along the road network;
* travel time         – the routing engine's duration for that route.

Road distance and travel time only ever come from a routing provider. When a
provider cannot answer (mode unsupported, no route, timeout…) the caller gets
a ``RoutingError`` with a user-safe message; nothing is estimated locally.

Providers are selected with ``ROUTING_PROVIDER`` (see ``app.core.config``):

* ``osrm``      – OSRM, the provider the project already used. One server per
  profile (car / bike / foot). No motorcycle profile exists in OSRM.
* ``valhalla``  – Valhalla, which also has a motorcycle costing model.
* ``tomtom``    – TomTom Routing (needs ``TOMTOM_API_KEY``). Car and
  motorcycle travel times include *live traffic*; each route also reports
  the free-flow time, the typical (historic) time, the current delay and the
  congested stretches along it. Live results are cached only briefly.
* ``none``      – routing disabled.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger("alty.routing")

# Website modes, in display order.
MODES = ("walking", "bicycle", "motorcycle", "driving")
MODE_LABELS = {"walking": "Walking", "bicycle": "Bicycle", "motorcycle": "Motorcycle", "driving": "Car"}

USER_MESSAGES = {
    "unsupported": "This travel mode is not available from the current routing provider.",
    "no_route": "No road route was found between these points.",
    "timeout": "The routing service took too long to respond. Please try again.",
    "rate_limited": "The routing service is busy. Please try again in a moment.",
    "unavailable": "Route information is currently unavailable.",
    "invalid": "These coordinates are not valid.",
}


class RoutingError(Exception):
    """A routing failure with a code and a message safe to show to clients."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.message = USER_MESSAGES.get(code, USER_MESSAGES["unavailable"])


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lat) and math.isfinite(self.lng)) \
                or not -90 <= self.lat <= 90 or not -180 <= self.lng <= 180:
            raise RoutingError("invalid")


def haversine_m(a: Point, b: Point) -> float:
    """Geographic (straight-line) distance in metres. Not a travel distance."""
    radius = 6_371_000.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    d_lat, d_lng = lat2 - lat1, math.radians(b.lng - a.lng)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _route(distance_m: float, duration_s: float, geometry: list[list[float]], summary: str = "",
           traffic: dict | None = None) -> dict:
    return {
        "distance_m": round(float(distance_m), 1),
        # With a live-traffic provider this is the travel time *now*.
        "duration_s": round(float(duration_s), 1),
        # [lat, lng] pairs following the road network.
        "geometry": [[round(lat, 5), round(lng, 5)] for lat, lng in geometry],
        "summary": summary,
        # None unless the provider applied live traffic to this route.
        "traffic": traffic,
    }


class RoutingProvider(ABC):
    name = "none"
    attribution = ""
    supports_alternatives = False
    # True when car/motorcycle durations include live traffic.
    live_traffic = False

    @property
    def cache_seconds(self) -> int:
        return settings.LIVE_ROUTE_CACHE_SECONDS if self.live_traffic else settings.ROUTE_CACHE_SECONDS

    @property
    @abstractmethod
    def modes(self) -> set[str]:
        """Travel modes this provider can actually route."""

    @abstractmethod
    def _routes(self, origin: Point, destination: Point, mode: str, alternatives: bool) -> list[dict]:
        """Provider request: routes ordered as the engine returns them."""

    @abstractmethod
    def _matrix(self, origins: list[Point], destination: Point, mode: str) -> list[tuple[float, float] | None]:
        """(road distance m, duration s) from each origin to the destination."""

    def _check_mode(self, mode: str) -> None:
        if mode not in MODES or mode not in self.modes:
            raise RoutingError("unsupported")

    def calculate_route(self, origin: Point, destination: Point, mode: str = "driving") -> dict:
        return self.calculate_alternative_routes(origin, destination, mode, alternatives=False)[0]

    def calculate_alternative_routes(self, origin: Point, destination: Point, mode: str = "driving",
                                     alternatives: bool = True) -> list[dict]:
        self._check_mode(mode)
        key = ("route", self.name, mode, alternatives, _key(origin), _key(destination))
        cached = _cache.get(key)
        if cached is not None:
            return cached
        routes = self._routes(origin, destination, mode, alternatives and self.supports_alternatives)
        if not routes:
            raise RoutingError("no_route")
        _cache.put(key, routes, self.cache_seconds)
        return routes

    def calculate_distance(self, origin: Point, destination: Point, mode: str = "driving") -> float:
        return self.calculate_route(origin, destination, mode)["distance_m"]

    def calculate_duration(self, origin: Point, destination: Point, mode: str = "driving") -> float:
        return self.calculate_route(origin, destination, mode)["duration_s"]

    def calculate_matrix(self, origins: list[Point], destination: Point,
                         mode: str = "driving") -> list[tuple[float, float] | None]:
        """Road distance/time from many origins (e.g. agents) in one request."""
        self._check_mode(mode)
        if not origins:
            return []
        key = ("matrix", self.name, mode, tuple(_key(o) for o in origins), _key(destination))
        cached = _cache.get(key)
        if cached is None:
            cached = self._matrix(origins, destination, mode)
            _cache.put(key, cached, self.cache_seconds)
        return cached


class NoRoutingProvider(RoutingProvider):
    name = "none"

    @property
    def modes(self) -> set[str]:
        return set()

    def _routes(self, origin, destination, mode, alternatives):  # pragma: no cover - never called
        raise RoutingError("unavailable")

    def _matrix(self, origins, destination, mode):  # pragma: no cover - never called
        raise RoutingError("unavailable")


def _get_json(client: httpx.Client, method: str, url: str, **kwargs) -> dict:
    try:
        response = client.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise RoutingError("timeout", str(exc)) from exc
    except httpx.HTTPError as exc:
        raise RoutingError("unavailable", str(exc)) from exc
    if response.status_code == 429:
        raise RoutingError("rate_limited")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RoutingError("unavailable", f"HTTP {response.status_code}") from exc
    if response.status_code >= 500:
        raise RoutingError("unavailable", f"HTTP {response.status_code}")
    return payload


class OsrmProvider(RoutingProvider):
    name = "osrm"
    attribution = "Routes © OSRM, map data © OpenStreetMap contributors"
    supports_alternatives = True

    def __init__(self, servers: dict[str, str], client: httpx.Client | None = None) -> None:
        self.servers = {mode: url.rstrip("/") for mode, url in servers.items() if url}
        self.client = client or httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS,
                                             headers={"User-Agent": settings.GEOCODER_USER_AGENT})

    @property
    def modes(self) -> set[str]:
        return set(self.servers) & {"walking", "bicycle", "driving"}

    @staticmethod
    def _coords(points: list[Point]) -> str:
        return ";".join(f"{p.lng:.6f},{p.lat:.6f}" for p in points)

    def _routes(self, origin, destination, mode, alternatives):
        url = f"{self.servers[mode]}/route/v1/driving/{self._coords([origin, destination])}"
        payload = _get_json(self.client, "GET", url, params={
            "overview": "full", "geometries": "geojson", "alternatives": "3" if alternatives else "false",
        })
        if payload.get("code") in {"NoRoute", "NoSegment"}:
            raise RoutingError("no_route")
        if payload.get("code") != "Ok":
            raise RoutingError("unavailable", str(payload.get("code")))
        return [
            _route(r["distance"], r["duration"], [[lat, lng] for lng, lat in r["geometry"]["coordinates"]],
                   ", ".join(leg.get("summary", "") for leg in r.get("legs", []) if leg.get("summary")))
            for r in payload.get("routes", [])
        ]

    def _matrix(self, origins, destination, mode):
        url = f"{self.servers[mode]}/table/v1/driving/{self._coords([*origins, destination])}"
        payload = _get_json(self.client, "GET", url, params={
            "sources": ";".join(str(i) for i in range(len(origins))),
            "destinations": str(len(origins)), "annotations": "distance,duration",
        })
        if payload.get("code") != "Ok":
            raise RoutingError("unavailable", str(payload.get("code")))
        out: list[tuple[float, float] | None] = []
        for distances, durations in zip(payload["distances"], payload["durations"]):
            distance, duration = distances[0], durations[0]
            out.append(None if distance is None or duration is None else (float(distance), float(duration)))
        return out


def decode_polyline(encoded: str, precision: int = 6) -> list[list[float]]:
    """Decode a Google-style encoded polyline (Valhalla uses precision 6)."""
    coordinates, index, lat, lng = [], 0, 0, 0
    factor = 10 ** precision
    while index < len(encoded):
        for axis in (0, 1):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lng += delta
        coordinates.append([lat / factor, lng / factor])
    return coordinates


class ValhallaProvider(RoutingProvider):
    name = "valhalla"
    attribution = "Routes © Valhalla, map data © OpenStreetMap contributors"
    supports_alternatives = True
    COSTING = {"walking": "pedestrian", "bicycle": "bicycle", "motorcycle": "motorcycle", "driving": "auto"}

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS,
                                             headers={"User-Agent": settings.GEOCODER_USER_AGENT})

    @property
    def modes(self) -> set[str]:
        return set(self.COSTING)

    def _routes(self, origin, destination, mode, alternatives):
        body = {
            "locations": [{"lat": origin.lat, "lon": origin.lng}, {"lat": destination.lat, "lon": destination.lng}],
            "costing": self.COSTING[mode], "units": "kilometers",
            "directions_type": "none",
        }
        if alternatives:
            body["alternates"] = 2
        payload = _get_json(self.client, "POST", f"{self.base_url}/route", json=body)
        if "trip" not in payload:
            # 442 = no path between locations; 171/170 = no suitable edges near a location.
            if payload.get("error_code") in {442, 170, 171}:
                raise RoutingError("no_route")
            raise RoutingError("unavailable", str(payload.get("error")))
        routes = []
        for trip in [payload["trip"], *(alt["trip"] for alt in payload.get("alternates", []))]:
            geometry = [point for leg in trip["legs"] for point in decode_polyline(leg["shape"])]
            routes.append(_route(trip["summary"]["length"] * 1000, trip["summary"]["time"], geometry))
        return routes

    def _matrix(self, origins, destination, mode):
        body = {
            "sources": [{"lat": p.lat, "lon": p.lng} for p in origins],
            "targets": [{"lat": destination.lat, "lon": destination.lng}],
            "costing": self.COSTING[mode], "units": "kilometers",
        }
        payload = _get_json(self.client, "POST", f"{self.base_url}/sources_to_targets", json=body)
        if "sources_to_targets" not in payload:
            raise RoutingError("unavailable", str(payload.get("error")))
        out: list[tuple[float, float] | None] = []
        for row in payload["sources_to_targets"]:
            cell = row[0]
            if cell.get("distance") is None or cell.get("time") is None:
                out.append(None)
            else:
                out.append((float(cell["distance"]) * 1000, float(cell["time"])))
        return out


class TomTomProvider(RoutingProvider):
    """TomTom Routing API with live traffic (car and motorcycle).

    ``travelTimeInSeconds`` already includes current traffic. With
    ``computeTravelTimeFor=all`` TomTom also returns the free-flow and the
    historic (typical) travel time, and ``sectionType=traffic`` lists the
    congested stretches of the route with their delay and severity.
    """

    name = "tomtom"
    attribution = "Routes and live traffic © TomTom"
    supports_alternatives = True
    live_traffic = True
    TRAVEL_MODE = {"walking": "pedestrian", "bicycle": "bicycle", "motorcycle": "motorcycle", "driving": "car"}
    TRAFFIC_MODES = {"driving", "motorcycle"}
    # magnitudeOfDelay: 0 unknown, 1 minor, 2 moderate, 3 major, 4 undefined (closures)
    LEVELS = {0: "slow", 1: "slow", 2: "moderate", 3: "heavy", 4: "closed"}

    def __init__(self, api_key: str, base_url: str = "https://api.tomtom.com",
                 client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS)

    @property
    def modes(self) -> set[str]:
        return set(self.TRAVEL_MODE)

    def _request(self, origin: Point, destination: Point, mode: str, alternatives: bool,
                 sections: bool = True) -> dict:
        locations = f"{origin.lat:.6f},{origin.lng:.6f}:{destination.lat:.6f},{destination.lng:.6f}"
        uses_traffic = mode in self.TRAFFIC_MODES
        params: list[tuple[str, str]] = [
            ("key", self.api_key),
            ("travelMode", self.TRAVEL_MODE[mode]),
            ("traffic", "true" if uses_traffic else "false"),
            ("routeType", "fastest"),
            ("departAt", "now"),
            ("maxAlternatives", "2" if alternatives else "0"),
            ("routeRepresentation", "polyline"),
        ]
        if uses_traffic:
            params.append(("computeTravelTimeFor", "all"))
            if sections:
                params.append(("sectionType", "traffic"))
        payload = _get_json(self.client, "GET",
                            f"{self.base_url}/routing/1/calculateRoute/{locations}/json", params=params)
        if "routes" not in payload:
            error = payload.get("detailedError") or payload.get("error") or {}
            code = str(error.get("code", "") if isinstance(error, dict) else error).upper()
            if "NO_ROUTE" in code or "MAP_MATCHING" in code or "UNREACHABLE" in code:
                raise RoutingError("no_route", code)
            raise RoutingError("unavailable", code or "no routes in response")
        return payload

    def _traffic(self, route: dict, point_count: int) -> dict:
        summary = route["summary"]
        segments = []
        for section in route.get("sections", []):
            if section.get("sectionType") != "TRAFFIC":
                continue
            start, end = int(section.get("startPointIndex", 0)), int(section.get("endPointIndex", 0))
            if not 0 <= start < end < point_count:
                continue
            closed = section.get("simpleCategory") == "ROAD_CLOSURE"
            segments.append({
                "start": start, "end": end,
                "level": "closed" if closed else self.LEVELS.get(int(section.get("magnitudeOfDelay", 0)), "slow"),
                "category": section.get("simpleCategory", "OTHER"),
                "delay_s": float(section.get("delayInSeconds", 0) or 0),
                "speed_kmh": section.get("effectiveSpeedInKmh"),
            })
        return {
            "live": True,
            "delay_s": float(summary.get("trafficDelayInSeconds", 0) or 0),
            "free_flow_duration_s": summary.get("noTrafficTravelTimeInSeconds"),
            "typical_duration_s": summary.get("historicTrafficTravelTimeInSeconds"),
            "congested_length_m": summary.get("trafficLengthInMeters"),
            "departure_time": summary.get("departureTime"),
            "segments": segments,
        }

    def _routes(self, origin, destination, mode, alternatives):
        payload = self._request(origin, destination, mode, alternatives)
        routes = []
        for route in payload["routes"]:
            geometry = [[p["latitude"], p["longitude"]] for leg in route["legs"] for p in leg["points"]]
            summary = route["summary"]
            traffic = self._traffic(route, len(geometry)) if mode in self.TRAFFIC_MODES else None
            routes.append(_route(summary["lengthInMeters"], summary["travelTimeInSeconds"], geometry,
                                 traffic=traffic))
        return routes

    def _matrix(self, origins, destination, mode):
        def one(origin: Point) -> tuple[float, float] | None:
            try:
                summary = self._request(origin, destination, mode, False, sections=False)["routes"][0]["summary"]
            except RoutingError as exc:
                if exc.code == "no_route":
                    return None
                raise
            return float(summary["lengthInMeters"]), float(summary["travelTimeInSeconds"])

        with ThreadPoolExecutor(max_workers=min(5, len(origins))) as pool:
            return list(pool.map(one, origins))


# ---------------------------------------------------------------------------
# Cache: routes are requested per selected property, then reused.
# ---------------------------------------------------------------------------

def _key(point: Point) -> tuple[float, float]:
    return round(point.lat, 5), round(point.lng, 5)


class _TtlCache:
    def __init__(self, max_items: int = 2000) -> None:
        self._items: dict[tuple, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self.max_items = max_items

    def get(self, key: tuple):
        with self._lock:
            hit = self._items.get(key)
            if hit is None or hit[0] < time.monotonic():
                self._items.pop(key, None)
                return None
            return hit[1]

    def put(self, key: tuple, value, seconds: int | None = None) -> None:
        ttl = settings.ROUTE_CACHE_SECONDS if seconds is None else seconds
        with self._lock:
            if len(self._items) >= self.max_items:
                self._items.pop(next(iter(self._items)))  # oldest insertion
            self._items[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_cache = _TtlCache()
_provider: RoutingProvider | None = None
_provider_lock = threading.Lock()


def get_provider() -> RoutingProvider:
    global _provider
    with _provider_lock:
        if _provider is None:
            choice = settings.ROUTING_PROVIDER.strip().casefold()
            if choice == "osrm":
                _provider = OsrmProvider({
                    "driving": settings.OSRM_DRIVING_URL,
                    "bicycle": settings.OSRM_BICYCLE_URL,
                    "walking": settings.OSRM_WALKING_URL,
                })
            elif choice == "valhalla":
                _provider = ValhallaProvider(settings.VALHALLA_URL)
            elif choice == "tomtom":
                if settings.TOMTOM_API_KEY:
                    _provider = TomTomProvider(settings.TOMTOM_API_KEY, settings.TOMTOM_API_URL)
                else:
                    logger.warning("ROUTING_PROVIDER=tomtom needs TOMTOM_API_KEY; using OSRM without live traffic")
                    _provider = OsrmProvider({
                        "driving": settings.OSRM_DRIVING_URL,
                        "bicycle": settings.OSRM_BICYCLE_URL,
                        "walking": settings.OSRM_WALKING_URL,
                    })
            else:
                _provider = NoRoutingProvider()
        return _provider


def set_provider(provider: RoutingProvider | None) -> None:
    """Swap the provider (tests, or a configuration reload)."""
    global _provider
    with _provider_lock:
        _provider = provider
    _cache.clear()


def compare_routes(routes: list[dict]) -> list[dict]:
    """Label routes with factual comparisons only — never a universal "best"."""
    if not routes:
        return []
    shortest = min(range(len(routes)), key=lambda i: routes[i]["distance_m"])
    fastest = min(range(len(routes)), key=lambda i: routes[i]["duration_s"])
    labelled = []
    for index, route in enumerate(routes):
        tags = []
        if index == shortest:
            tags.append("shortest_distance")
        if index == fastest:
            tags.append("shortest_time")
        if not tags:
            tags.append("alternative")
        labelled.append({**route, "id": chr(ord("A") + index), "tags": tags})
    return labelled


def commute(origin: Point, destination: Point, alternatives: bool = True) -> dict:
    """Route every website mode between two points (concurrently, cached)."""
    provider = get_provider()

    def one(mode: str) -> tuple[str, dict]:
        if mode not in provider.modes:
            return mode, {"status": "unsupported", "message": USER_MESSAGES["unsupported"], "routes": []}
        try:
            routes = provider.calculate_alternative_routes(origin, destination, mode, alternatives)
        except RoutingError as exc:
            return mode, {"status": exc.code, "message": exc.message, "routes": []}
        return mode, {"status": "ok", "message": None, "routes": compare_routes(routes)}

    with ThreadPoolExecutor(max_workers=len(MODES)) as pool:
        results = dict(pool.map(one, MODES))
    return {
        "provider": provider.name,
        "attribution": provider.attribution,
        "live_traffic": provider.live_traffic,
        "straight_line_m": round(haversine_m(origin, destination), 1),
        "modes": {mode: {"label": MODE_LABELS[mode], **results[mode]} for mode in MODES},
    }
