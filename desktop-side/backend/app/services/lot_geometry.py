"""Lot boundaries: validation and measurements.

A boundary is a GeoJSON Polygon (one outer ring of [longitude, latitude]
points, WGS84), drawn by staff over satellite imagery. Nothing here invents a
boundary from the listing's single map point.

Measurements are geodesic estimates on the spherical earth, using the same
formulas as the Turf library the website uses, so both sides agree:
  * area: spherical polygon area (Chamberlain & Duquette) and
  * lengths: haversine, both on the mean earth radius 6,371,008.8 m (very close
    to the equal-area radius of the WGS84 ellipsoid, 6,371,007.2 m).
For parcels of a few hectares the difference from an ellipsoidal survey is
well under 1%. They are estimates from the mapped outline, not a survey.
"""

from __future__ import annotations

import math

EARTH_RADIUS = 6_371_008.8
MAX_POINTS = 500
MAX_AREA_SQM = 100_000_000.0   # 100 km²: beyond any lot
MIN_AREA_SQM = 1.0


class BoundaryError(ValueError):
    """The drawn boundary can't be used (the message says why)."""


def _ring(geometry: object) -> list[tuple[float, float]]:
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise BoundaryError("The boundary must be a polygon")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        raise BoundaryError("The boundary must be a single outline (no holes or separate parts)")
    points = []
    for point in rings[0] if isinstance(rings[0], list) else []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise BoundaryError("Every boundary point needs a longitude and a latitude")
        lng, lat = point[0], point[1]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lng, lat)):
            raise BoundaryError("Boundary points must be numbers")
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise BoundaryError("A boundary point is outside the map")
        points.append((float(lng), float(lat)))
    return points


def _segments_cross(a, b, c, d) -> bool:
    def orient(p, q, r):
        value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(value) < 1e-18 else (1 if value > 0 else -1)

    def on_segment(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and on_segment(a, c, b)) or (o2 == 0 and on_segment(a, d, b))
            or (o3 == 0 and on_segment(c, a, d)) or (o4 == 0 and on_segment(c, b, d)))


def normalize(geometry: object) -> dict:
    """A clean, closed, valid polygon, or BoundaryError."""
    points = _ring(geometry)
    cleaned: list[tuple[float, float]] = []
    for point in points:  # drop repeated consecutive points (and the closing one)
        rounded = (round(point[0], 8), round(point[1], 8))
        if not cleaned or cleaned[-1] != rounded:
            cleaned.append(rounded)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 3:
        raise BoundaryError("A boundary needs at least 3 different points")
    if len(cleaned) > MAX_POINTS:
        raise BoundaryError(f"A boundary can have at most {MAX_POINTS} points")
    edges = [(cleaned[i], cleaned[(i + 1) % len(cleaned)]) for i in range(len(cleaned))]
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue  # neighbouring sides share a corner
            if _segments_cross(*edges[i], *edges[j]):
                raise BoundaryError("The boundary crosses itself; move the points so the sides don't cross")
    ring = [list(point) for point in cleaned] + [list(cleaned[0])]
    area = area_sqm(ring)
    if area < MIN_AREA_SQM:
        raise BoundaryError("The boundary is too small to be a lot")
    if area > MAX_AREA_SQM:
        raise BoundaryError("The boundary is larger than 100 km², which can't be a single lot")
    return {"type": "Polygon", "coordinates": [ring]}


def area_sqm(ring: list) -> float:
    """Spherical area of a closed ring of [lng, lat] points (square metres)."""
    count = len(ring)
    if count < 4:
        return 0.0
    total = 0.0
    for i in range(count - 1):
        lower = ring[i]
        middle = ring[(i + 1) % (count - 1)]
        upper = ring[(i + 2) % (count - 1)]
        total += (math.radians(upper[0]) - math.radians(lower[0])) * math.sin(math.radians(middle[1]))
    return abs(total * EARTH_RADIUS * EARTH_RADIUS / 2)


def distance_m(a: list, b: list) -> float:
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    d_lat, d_lng = lat2 - lat1, math.radians(b[0] - a[0])
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS * math.asin(min(1.0, math.sqrt(h)))


def measure(geometry: dict | None) -> dict | None:
    """Area (m²), perimeter (m) and side lengths of a stored boundary."""
    if not geometry:
        return None
    ring = geometry["coordinates"][0]
    sides = [round(distance_m(ring[i], ring[i + 1]), 2) for i in range(len(ring) - 1)]
    return {"area_sqm": round(area_sqm(ring), 2), "perimeter_m": round(sum(sides), 2), "sides_m": sides}
