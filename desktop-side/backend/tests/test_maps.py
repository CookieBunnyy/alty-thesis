"""Website map: routing providers, commute DSS, traffic and nearby agents.

No test calls a real routing service: providers are faked, or their HTTP
transport is mocked with recorded-shape responses.
"""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.api.v1 import maps
from app.models.agent import Agent
from app.models.property_listing import PropertyListing
from app.services import routing, traffic
from app.services.routing import (
    OsrmProvider,
    Point,
    RoutingError,
    RoutingProvider,
    TomTomProvider,
    ValhallaProvider,
)

WORK = {"origin_lat": 14.5547, "origin_lng": 121.0509}
HOME = {"dest_lat": 14.5778, "dest_lng": 121.0341}


class FakeProvider(RoutingProvider):
    name = "fake"
    supports_alternatives = True

    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.calls = 0

    @property
    def modes(self):
        return {"walking", "driving"}

    def _routes(self, origin, destination, mode, alternatives):
        self.calls += 1
        if self.fail:
            raise RoutingError(self.fail)
        path = [[origin.lat, origin.lng], [origin.lat, destination.lng], [destination.lat, destination.lng]]
        routes = [routing._route(4000, 900, path), routing._route(3500, 1200, path)]
        return routes if alternatives else routes[:1]

    def _matrix(self, origins, destination, mode):
        if self.fail:
            raise RoutingError(self.fail)
        return [(1000.0 * (i + 1), 120.0 * (i + 1)) for i in range(len(origins))]


@pytest.fixture
def fake():
    provider = FakeProvider()
    routing.set_provider(provider)
    maps.map_limiter._hits.clear()
    yield provider
    routing.set_provider(None)
    traffic.set_traffic_provider(None)


def test_capabilities_only_list_real_modes(api, fake):
    body = api.get("/api/v1/map/capabilities").json()
    modes = body["routing"]["modes"]
    assert modes["walking"]["supported"] and modes["driving"]["supported"]
    assert not modes["motorcycle"]["supported"] and not modes["bicycle"]["supported"]
    assert body["traffic"]["available"] is False and "not available" in body["traffic"]["message"]


def test_commute_reports_each_mode_with_factual_labels(api, fake):
    body = api.get("/api/v1/map/commute", params={**WORK, **HOME}).json()
    driving = body["modes"]["driving"]
    assert driving["status"] == "ok"
    assert [r["id"] for r in driving["routes"]] == ["A", "B"]
    assert driving["routes"][0]["tags"] == ["shortest_time"]       # 900 s
    assert driving["routes"][1]["tags"] == ["shortest_distance"]   # 3500 m
    assert len(driving["routes"][0]["geometry"]) == 3              # road polyline, not 2 points
    for mode in ("motorcycle", "bicycle"):
        assert body["modes"][mode]["status"] == "unsupported" and body["modes"][mode]["routes"] == []
    assert body["live_traffic"] is False
    assert 2500 < body["straight_line_m"] < 3500                   # geographic, reported separately


def test_routes_are_cached(api, fake):
    params = {**WORK, **HOME, "mode": "driving"}
    assert api.get("/api/v1/map/route", params=params).status_code == 200
    assert api.get("/api/v1/map/route", params=params).status_code == 200
    assert fake.calls == 1


@pytest.mark.parametrize("code,status", [("timeout", 503), ("rate_limited", 503), ("no_route", 404)])
def test_route_errors_are_user_safe(api, fake, code, status):
    fake.fail = code
    response = api.get("/api/v1/map/route", params={**WORK, **HOME})
    assert response.status_code == status
    assert response.json()["detail"] == routing.USER_MESSAGES[code]


def test_unsupported_mode_and_invalid_coordinates(api, fake):
    assert api.get("/api/v1/map/route", params={**WORK, **HOME, "mode": "motorcycle"}).status_code == 422
    assert api.get("/api/v1/map/route", params={**WORK, **HOME, "mode": "rocket"}).status_code == 422
    bad = {**WORK, "dest_lat": 123.0, "dest_lng": 121.0}
    assert api.get("/api/v1/map/route", params=bad).status_code == 422


def test_map_requests_are_rate_limited(api, fake, monkeypatch):
    monkeypatch.setattr(maps.settings, "MAP_REQUESTS_PER_MINUTE", 2)
    params = {**WORK, **HOME}
    assert api.get("/api/v1/map/route", params=params).status_code == 200
    assert api.get("/api/v1/map/route", params=params).status_code == 200
    assert api.get("/api/v1/map/route", params=params).status_code == 429


def test_traffic_tiles_need_a_real_provider(api, fake):
    assert api.get("/api/v1/map/traffic/tiles/12/3420/1880.png").status_code == 503

    class Live(traffic.TrafficProvider):
        name = "test"
        legend = [{"level": "low", "label": "Free flow", "color": "#00ff00"}]

        @property
        def available(self):
            return True

        def fetch_tile(self, z, x, y, theme="light"):
            return b"\x89PNG tile"

    traffic.set_traffic_provider(Live())
    assert api.get("/api/v1/map/traffic").json()["available"] is True
    tile = api.get("/api/v1/map/traffic/tiles/12/3420/1880.png")
    assert tile.status_code == 200 and tile.content == b"\x89PNG tile"
    assert api.get("/api/v1/map/traffic/tiles/2/9/0.png").status_code == 404


def _seed_property_and_agents(db):
    listing = PropertyListing(title="Test Studio", category="Condo", price_total=Decimal("2500000"),
                              lat=Decimal("14.5778"), lng=Decimal("121.0341"), status="AVAILABLE")
    db.add(listing)
    for agent_id, name, lat, lng, status in (
        ("AGT-1", "Far Agent", "14.6760", "121.0437", "ACTIVE"),
        ("AGT-2", "Near Agent", "14.5800", "121.0350", "ACTIVE"),
        ("AGT-3", "Inactive Agent", "14.5779", "121.0342", "INACTIVE"),
        ("AGT-4", "Unmapped Agent", None, None, "ACTIVE"),
    ):
        db.add(Agent(agent_id=agent_id, full_name=name, phone_number="0917 000 0000",
                     agent_location="Metro Manila", latitude=lat and Decimal(lat),
                     longitude=lng and Decimal(lng), star_rating=Decimal("4.5"), status=status,
                     total_commission=Decimal("99999"), sync_status="SYNCED"))
    db.commit()
    return listing.listing_id


def test_nearby_agents_use_database_agents_and_separate_distances(api, fake, db):
    listing_id = _seed_property_and_agents(db)
    body = api.get(f"/api/v1/public/properties/{listing_id}/nearby-agents").json()
    names = [agent["full_name"] for agent in body["agents"]]
    assert names == ["Near Agent", "Far Agent", "Unmapped Agent"]   # inactive agent excluded
    near = body["agents"][0]
    assert near["straight_line_km"] < 1
    assert near["road_distance_km"] == 1.0 and near["travel_time_min"] == 2   # from the provider
    assert body["agents"][2]["straight_line_km"] is None
    assert body["routing"]["available"] is True
    assert "total_commission" not in near and "performance_score" not in near
    assert near["phone_number"] == "0917 000 0000"


def test_nearby_agents_without_routing_keep_road_fields_empty(api, fake, db):
    fake.fail = "unavailable"
    listing_id = _seed_property_and_agents(db)
    body = api.get(f"/api/v1/public/properties/{listing_id}/nearby-agents").json()
    assert body["routing"]["available"] is False
    assert body["routing"]["message"] == routing.USER_MESSAGES["unavailable"]
    assert all(agent["road_distance_km"] is None for agent in body["agents"])
    assert api.get("/api/v1/public/properties/999999/nearby-agents").status_code == 404


# --- provider parsing (mocked HTTP) ----------------------------------------

def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_osrm_parses_geojson_routes_and_table():
    def handler(request: httpx.Request) -> httpx.Response:
        if "/table/" in request.url.path:
            return httpx.Response(200, json={"code": "Ok", "distances": [[1500.0], [None]],
                                             "durations": [[300.0], [None]]})
        assert request.url.host == "foot.example"
        return httpx.Response(200, json={"code": "Ok", "routes": [{
            "distance": 4125.0, "duration": 3300.0, "legs": [{"summary": "EDSA"}],
            "geometry": {"coordinates": [[121.05, 14.55], [121.04, 14.56], [121.03, 14.57]]},
        }]})

    provider = OsrmProvider({"walking": "https://foot.example", "driving": "https://car.example"},
                            client=_client(handler))
    assert provider.modes == {"walking", "driving"}
    route = provider.calculate_route(Point(14.55, 121.05), Point(14.57, 121.03), "walking")
    assert route["geometry"][0] == [14.55, 121.05] and route["summary"] == "EDSA"
    with pytest.raises(RoutingError) as exc:
        provider.calculate_route(Point(14.55, 121.05), Point(14.57, 121.03), "motorcycle")
    assert exc.value.code == "unsupported"
    cells = provider.calculate_matrix([Point(14.5, 121.0), Point(14.6, 121.1)], Point(14.57, 121.03))
    assert cells == [(1500.0, 300.0), None]


def test_osrm_maps_failures():
    responses = iter([httpx.Response(200, json={"code": "NoRoute"}), httpx.Response(429, json={})])
    provider = OsrmProvider({"driving": "https://car.example"}, client=_client(lambda r: next(responses)))
    for code, origin in (("no_route", Point(1, 1)), ("rate_limited", Point(2, 2))):
        with pytest.raises(RoutingError) as exc:
            provider.calculate_route(origin, Point(3, 3))
        assert exc.value.code == code

    def timeout(request):
        raise httpx.ConnectTimeout("slow")

    slow = OsrmProvider({"driving": "https://car.example"}, client=_client(timeout))
    with pytest.raises(RoutingError) as exc:
        slow.calculate_route(Point(4, 4), Point(5, 5))
    assert exc.value.code == "timeout" and "slow" not in exc.value.message


def test_valhalla_supports_motorcycle_and_decodes_shapes():
    shape = "_izlhA~rlgdF_{geC~ywl@_kwzCn`{nI"  # polyline6 of (38.5,-120.2),(40.7,-120.95),(43.252,-126.453)

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        assert body["costing"] == "motorcycle"
        trip = {"summary": {"length": 4.636, "time": 1080.0}, "legs": [{"shape": shape}]}
        return httpx.Response(200, json={"trip": trip, "alternates": [{"trip": trip}]})

    provider = ValhallaProvider("https://valhalla.example", client=_client(handler))
    routes = provider.calculate_alternative_routes(Point(14.55, 121.05), Point(14.57, 121.03), "motorcycle")
    assert len(routes) == 2 and routes[0]["distance_m"] == 4636.0
    assert routes[0]["geometry"][0] == [38.5, -120.2] and routes[0]["geometry"][2] == [43.252, -126.453]


# --- TomTom: live traffic -------------------------------------------------

def _tomtom_route(length=5200, live=1500, delay=360, sections=()):
    points = [{"latitude": 14.55 + i * 0.001, "longitude": 121.05 - i * 0.001} for i in range(10)]
    return {
        "summary": {"lengthInMeters": length, "travelTimeInSeconds": live, "trafficDelayInSeconds": delay,
                    "trafficLengthInMeters": 900, "noTrafficTravelTimeInSeconds": live - delay,
                    "historicTrafficTravelTimeInSeconds": live - 120,
                    "departureTime": "2026-10-02T08:00:00+08:00"},
        "legs": [{"points": points}],
        "sections": list(sections),
    }


def test_tomtom_applies_live_traffic_to_car_routes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        jam = {"sectionType": "TRAFFIC", "startPointIndex": 2, "endPointIndex": 6, "simpleCategory": "JAM",
               "magnitudeOfDelay": 3, "delayInSeconds": 300, "effectiveSpeedInKmh": 9}
        closure = {"sectionType": "TRAFFIC", "startPointIndex": 7, "endPointIndex": 8,
                   "simpleCategory": "ROAD_CLOSURE", "magnitudeOfDelay": 4, "delayInSeconds": 60}
        bogus = {"sectionType": "TRAFFIC", "startPointIndex": 8, "endPointIndex": 99}  # out of range
        return httpx.Response(200, json={"routes": [_tomtom_route(sections=[jam, closure, bogus]),
                                                     _tomtom_route(length=6100, live=1380, delay=60)]})

    provider = TomTomProvider("test-key", client=_client(handler))
    routes = provider.calculate_alternative_routes(Point(14.55, 121.05), Point(14.56, 121.04), "driving")
    params = seen[0].params
    assert params["traffic"] == "true" and params["travelMode"] == "car"
    assert params["computeTravelTimeFor"] == "all" and params["sectionType"] == "traffic"
    first = routes[0]
    assert first["duration_s"] == 1500.0  # travel time *with* current traffic
    assert first["traffic"]["delay_s"] == 360 and first["traffic"]["free_flow_duration_s"] == 1140
    assert first["traffic"]["typical_duration_s"] == 1380
    assert [(seg["start"], seg["end"], seg["level"]) for seg in first["traffic"]["segments"]] == [
        (2, 6, "heavy"), (7, 8, "closed")]
    # Traffic changes the factual comparison: the longer route is faster right now.
    labelled = routing.compare_routes(routes)
    assert labelled[0]["tags"] == ["shortest_distance"] and labelled[1]["tags"] == ["shortest_time"]


def test_tomtom_bicycle_and_walking_ignore_traffic_and_support_motorcycle():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params)
        return httpx.Response(200, json={"routes": [_tomtom_route()]})

    provider = TomTomProvider("test-key", client=_client(handler))
    assert provider.modes == {"walking", "bicycle", "motorcycle", "driving"}
    bike = provider.calculate_route(Point(14.55, 121.05), Point(14.56, 121.04), "bicycle")
    assert seen[-1]["traffic"] == "false" and "sectionType" not in seen[-1] and bike["traffic"] is None
    moto = provider.calculate_route(Point(14.55, 121.05), Point(14.56, 121.04), "motorcycle")
    assert seen[-1]["travelMode"] == "motorcycle" and moto["traffic"]["live"] is True


def test_tomtom_errors_and_short_live_cache(monkeypatch):
    responses = iter([
        httpx.Response(400, json={"detailedError": {"code": "NO_ROUTE_FOUND", "message": "x"}}),
        httpx.Response(403, json={"detailedError": {"code": "FORBIDDEN", "message": "bad key"}}),
    ])
    provider = TomTomProvider("bad", client=_client(lambda request: next(responses)))
    for code, origin in (("no_route", Point(1, 1)), ("unavailable", Point(2, 2))):
        with pytest.raises(RoutingError) as exc:
            provider.calculate_route(origin, Point(3, 3))
        assert exc.value.code == code and "bad key" not in exc.value.message
    monkeypatch.setattr(routing.settings, "LIVE_ROUTE_CACHE_SECONDS", 120)
    assert provider.cache_seconds == 120 < routing.settings.ROUTE_CACHE_SECONDS


def test_tomtom_matrix_uses_live_car_times():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/routing/1/calculateRoute/1.000000"):
            return httpx.Response(400, json={"detailedError": {"code": "NO_ROUTE_FOUND"}})
        return httpx.Response(200, json={"routes": [_tomtom_route(length=3000, live=600)]})

    provider = TomTomProvider("test-key", client=_client(handler))
    cells = provider.calculate_matrix([Point(14.5, 121.0), Point(1, 1)], Point(14.57, 121.03))
    assert cells == [(3000.0, 600.0), None]


def test_commute_reports_live_traffic(api, fake):
    fake.live_traffic = True
    body = api.get("/api/v1/map/commute", params={**WORK, **HOME}).json()
    assert body["live_traffic"] is True
    assert api.get("/api/v1/map/capabilities").json()["routing"]["live_traffic"] is True


def test_traffic_tiles_follow_theme():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, content=b"png", headers={"content-type": "image/png"})

    provider = traffic.TomTomTrafficProvider("test-key", client=_client(handler))
    provider.fetch_tile(12, 3420, 1880, "dark")
    provider.fetch_tile(12, 3420, 1880, "light")
    provider.fetch_tile(12, 3420, 1880, "dark")  # cached
    assert seen == ["/traffic/map/4/tile/flow/relative0-dark/12/3420/1880.png",
                    "/traffic/map/4/tile/flow/relative0/12/3420/1880.png"]
