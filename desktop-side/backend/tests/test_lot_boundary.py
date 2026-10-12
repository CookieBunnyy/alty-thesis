"""Lot boundaries: validation, geodesic measurements, saving and access."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from app.models.property_listing import PropertyListing
from app.services import lot_geometry as geo

# An irregular five-sided lot in Silang, Cavite ([lng, lat]).
LOT = [[120.9792, 14.2223], [120.9801, 14.2224], [120.9806, 14.2213], [120.9797, 14.2207], [120.9789, 14.2214]]


def polygon(points, close=True):
    return {"type": "Polygon", "coordinates": [points + ([points[0]] if close else [])]}


def test_area_and_lengths_are_geodesic():
    # A 0.001° square on the equator: each side is R·π/180·0.001 metres.
    side = geo.EARTH_RADIUS * math.pi / 180 * 0.001
    square = geo.normalize(polygon([[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001]]))
    measured = geo.measure(square)
    assert measured["area_sqm"] == pytest.approx(side * side, rel=1e-4)
    assert measured["perimeter_m"] == pytest.approx(4 * side, rel=1e-4)
    # The same values the website's Turf library gives for the irregular lot.
    lot = geo.measure(geo.normalize(polygon(LOT)))
    assert lot["area_sqm"] == pytest.approx(22232.94, abs=0.05)
    assert lot["perimeter_m"] == pytest.approx(570.37, abs=0.05)
    assert lot["sides_m"] == pytest.approx([97.64, 133.66, 117.74, 116.16, 105.17], abs=0.01)
    # Shrinking longitude spacing away from the equator is respected (not lat/lng × lat/lng).
    north = geo.measure(geo.normalize(polygon([[0, 60], [0.001, 60], [0.001, 60.001], [0, 60.001]])))
    assert north["area_sqm"] == pytest.approx(side * side * math.cos(math.radians(60.0005)), rel=1e-3)


def test_invalid_boundaries_are_rejected():
    with pytest.raises(geo.BoundaryError, match="crosses itself"):
        geo.normalize(polygon([[0, 0], [0.001, 0.001], [0.001, 0], [0, 0.001]]))  # a bow tie
    with pytest.raises(geo.BoundaryError, match="at least 3"):
        geo.normalize(polygon([[0, 0], [0.001, 0]]))
    with pytest.raises(geo.BoundaryError, match="no holes"):
        geo.normalize({"type": "Polygon", "coordinates": [LOT + [LOT[0]], LOT + [LOT[0]]]})
    with pytest.raises(geo.BoundaryError, match="outside the map"):
        geo.normalize(polygon([[0, 0], [200, 0], [0, 1]]))
    with pytest.raises(geo.BoundaryError, match="polygon"):
        geo.normalize({"type": "Point", "coordinates": [0, 0]})
    # An unclosed ring with a repeated point is cleaned and closed.
    cleaned = geo.normalize(polygon(LOT[:2] + [LOT[1]] + LOT[2:], close=False))
    ring = cleaned["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) == len(LOT) + 1


@pytest.fixture
def listing(db) -> PropertyListing:
    row = PropertyListing(title="Garden Lot in Silang", category="House and Lot", status="AVAILABLE",
                          lat=14.2216, lng=120.9797, price_total=Decimal(4_000_000), sync_status="SYNCED")
    db.add(row)
    db.commit()
    return row


def test_save_measure_and_show_publicly(api, admin, employee, listing, db):
    path = f"/api/v1/property-listings/{listing.listing_id}/boundary"
    body = {"geometry": polygon(LOT), "use_as_lot_area": True}
    assert api.put(path, json=body).status_code == 401
    assert api.put(path, headers=employee, json=body).status_code == 403  # only property editors
    saved = api.put(path, headers=admin, json=body)
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["boundary"]["coordinates"][0][0] == LOT[0]
    assert data["boundary_measurements"]["area_sqm"] == pytest.approx(22232.94, abs=0.05)
    assert data["lot_area_sqm"] == pytest.approx(22232.94, abs=0.05)
    assert data["boundary_updated_by"]

    # Persists, and the public site gets the outline and measurements (not who drew it).
    again = api.get(f"/api/v1/property-listings/{listing.listing_id}", headers=employee).json()
    assert again["boundary"] == data["boundary"]
    public = next(p for p in api.get("/api/v1/public/properties").json() if p["listing_id"] == listing.listing_id)
    assert public["boundary"] == data["boundary"] and public["boundary_measurements"]["perimeter_m"] == pytest.approx(570.37, abs=0.05)
    assert "boundary_updated_by" not in public

    bad = api.put(path, headers=admin, json={"geometry": polygon([[0, 0], [0.001, 0.001], [0.001, 0], [0, 0.001]])})
    assert bad.status_code == 422 and "crosses itself" in bad.json()["detail"]

    removed = api.delete(path, headers=admin)
    assert removed.status_code == 200 and removed.json()["boundary"] is None
    assert removed.json()["lot_area_sqm"] == pytest.approx(22232.94, abs=0.05)  # the stated lot area stays
    assert api.delete(path, headers=admin).status_code == 404
    actions = [e["action"] for e in api.get("/api/v1/audit", headers=admin).json()["items"]]
    assert "PROPERTY_BOUNDARY_ADDED" in actions and "PROPERTY_BOUNDARY_REMOVED" in actions


def test_listings_without_a_boundary_still_work(api, admin, listing):
    data = api.get(f"/api/v1/property-listings/{listing.listing_id}", headers=admin).json()
    assert data["boundary"] is None and data["boundary_measurements"] is None
    public = api.get("/api/v1/public/properties").json()
    assert all("boundary" in p for p in public)
