"""Apply a visitor's criteria to the listings and explain the matches.

Hard requirements (bedrooms, lot area, a drawn boundary, a pool, a school
nearby...) filter the listings. When nothing meets all of them, the least
important ones are relaxed one at a time and the reply says which, so the
visitor always gets the closest options instead of a dead end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .criteria import AMENITY_LABELS, ESTABLISHMENTS, FEATURES, Criteria, category_key


def peso(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"₱{value / 1_000_000:,.2f}M".replace(".00M", "M")
    return f"₱{value:,.0f}"


def _num(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def amenities_of(row: dict) -> set[str]:
    raw = row.get("amenity_list")
    if isinstance(raw, dict):
        return {str(k).lower() for k, v in raw.items() if v}
    if isinstance(raw, list):
        return {str(v).lower().replace(" ", "_") for v in raw}
    return set()


def nearest(row: dict, group: str) -> dict | None:
    """The closest recorded establishment of a group (e.g. "schools")."""
    data = row.get("nearby_establishments")
    if not isinstance(data, dict):
        return None
    items = [i for i in data.get(group) or [] if isinstance(i, dict)]
    # Listings may store "school" or "schools".
    if not items:
        items = [i for i in data.get(group.rstrip("s")) or [] if isinstance(i, dict)]
    items = [i for i in items if _num(i.get("distance_km")) is not None] or items
    return min(items, key=lambda i: _num(i.get("distance_km")) or 99) if items else None


def lot_sqm(row: dict) -> float | None:
    """Recorded lot area, else the area measured from the drawn boundary."""
    area = _num(row.get("lot_area_sqm"))
    if area:
        return area
    measured = row.get("boundary_measurements") or {}
    return _num(measured.get("area_sqm")) if isinstance(measured, dict) else None


@dataclass
class Rule:
    key: str
    label: str
    test: Callable[[dict], bool]


def rules_for(c: Criteria) -> list[Rule]:
    """Hard requirements, most important LAST (relaxed from the start)."""
    rules: list[Rule] = []
    if c.near and c.near_max_km:
        rules.append(Rule("near_max_km", f"within {c.near_max_km:g} km",
                          lambda r: all((_num((nearest(r, g) or {}).get("distance_km")) or 99) <= c.near_max_km
                                        for g in c.near)))
    for amenity in c.amenities:
        rules.append(Rule(f"amenity:{amenity}", AMENITY_LABELS[amenity],
                          lambda r, a=amenity: a in amenities_of(r)))
    if c.min_garage_spaces:
        rules.append(Rule("min_garage_spaces", f"parking for {c.min_garage_spaces} cars",
                          lambda r: (_num(r.get("garage_spaces")) or (1 if r.get("has_garage") else 0)) >= c.min_garage_spaces))
    for column in c.features:
        rules.append(Rule(f"feature:{column}", FEATURES[column][0], lambda r, col=column: bool(r.get(col))))
    if c.needs_boundary:
        rules.append(Rule("needs_boundary", "a drawn lot boundary", lambda r: bool(r.get("boundary"))))
    for group in c.near:
        rules.append(Rule(f"near:{group}", f"a {ESTABLISHMENTS[group][0]} nearby",
                          lambda r, g=group: nearest(r, g) is not None))
    if c.max_lot_sqm:
        rules.append(Rule("max_lot_sqm", f"lot up to {c.max_lot_sqm:,.0f} sqm",
                          lambda r: (lot_sqm(r) or 0) <= c.max_lot_sqm and lot_sqm(r) is not None))
    if c.min_lot_sqm:
        rules.append(Rule("min_lot_sqm", f"lot of at least {c.min_lot_sqm:,.0f} sqm",
                          lambda r: (lot_sqm(r) or 0) >= c.min_lot_sqm))
    if c.min_bathrooms:
        rules.append(Rule("min_bathrooms", f"{c.min_bathrooms}+ bathrooms",
                          lambda r: (_num(r.get("num_bathrooms")) or 0) >= c.min_bathrooms))
    if c.min_bedrooms:
        rules.append(Rule("min_bedrooms", f"{c.min_bedrooms}+ bedrooms",
                          lambda r: (_num(r.get("num_bedrooms")) or 0) >= c.min_bedrooms))
    if c.min_price:
        rules.append(Rule("min_price", f"price from {peso(c.min_price)}",
                          lambda r: (_num(r.get("price_total")) or 0) >= c.min_price))
    if c.max_monthly:
        rules.append(Rule("max_monthly", f"monthly up to {peso(c.max_monthly)}",
                          lambda r: _num(r.get("monthly_rate")) is not None and _num(r.get("monthly_rate")) <= c.max_monthly * 1.05))
    if c.max_downpayment:
        rules.append(Rule("max_downpayment", f"down payment up to {peso(c.max_downpayment)}",
                          lambda r: _num(r.get("initial_dp")) is not None and _num(r.get("initial_dp")) <= c.max_downpayment * 1.05))
    if c.max_price:
        rules.append(Rule("max_price", f"price up to {peso(c.max_price)}",
                          lambda r: _num(r.get("price_total")) is not None and _num(r.get("price_total")) <= c.max_price * 1.05))
    if c.category:
        rules.append(Rule("category", "the property type", lambda r: category_key(r.get("category")) == c.category))
    return rules


def filter_rows(rows: list[dict], c: Criteria) -> tuple[list[int], list[str]]:
    """Indexes of the rows that meet every requirement; when none do, the
    closest set found by relaxing the least important requirements first,
    with the labels of what was relaxed."""
    rules = rules_for(c)
    meets = lambda active: [i for i, row in enumerate(rows) if all(rule.test(row) for rule in active)]  # noqa: E731
    matches = meets(rules)
    if matches or not rules:
        return matches, []
    dropped: list[Rule] = []
    while rules and not matches:
        dropped.append(rules.pop(0))
        matches = meets(rules)
    # Put back every dropped requirement that some of the remaining matches still meet.
    for rule in list(reversed(dropped[:-1] if matches else dropped)):
        if meets(rules + [rule]):
            rules.append(rule)
            dropped.remove(rule)
    return meets(rules), [rule.label for rule in dropped]


_SORT_KEYS: dict[str, Callable[[dict], float]] = {
    "price_asc": lambda r: _num(r.get("price_total")) or float("inf"),
    "price_desc": lambda r: -(_num(r.get("price_total")) or 0),
    "dp_asc": lambda r: _num(r.get("initial_dp")) if _num(r.get("initial_dp")) is not None else float("inf"),
    "monthly_asc": lambda r: _num(r.get("monthly_rate")) if _num(r.get("monthly_rate")) is not None else float("inf"),
    "lot_desc": lambda r: -(lot_sqm(r) or 0),
    "bedrooms_desc": lambda r: -(_num(r.get("num_bedrooms")) or 0),
}


def sort_key(c: Criteria) -> Callable[[dict], float] | None:
    return _SORT_KEYS.get(c.sort or "")


def nearby_bonus(row: dict, c: Criteria) -> float:
    """0..1: how close the requested establishments are (closer is better)."""
    if not c.near:
        return 0.0
    total = 0.0
    for group in c.near:
        km = _num((nearest(row, group) or {}).get("distance_km"))
        total += 0.0 if km is None else 1.0 / (1.0 + km)
    return total / len(c.near)


def why(row: dict, c: Criteria) -> str:
    """One line of facts that match what the visitor asked for."""
    facts = []
    price = _num(row.get("price_total"))
    if price:
        facts.append(peso(price))
    if c.max_monthly or c.sort == "monthly_asc":
        if _num(row.get("monthly_rate")):
            facts.append(f"{peso(_num(row.get('monthly_rate')))}/month")
    if c.max_downpayment or c.sort == "dp_asc":
        if _num(row.get("initial_dp")) is not None:
            facts.append(f"{peso(_num(row.get('initial_dp')))} down payment")
    rooms = []
    if row.get("num_bedrooms") is not None:
        rooms.append(f"{row['num_bedrooms']} bd")
    if row.get("num_bathrooms") is not None:
        rooms.append(f"{row['num_bathrooms']} ba")
    if rooms and (c.min_bedrooms or c.min_bathrooms or c.sort == "bedrooms_desc" or len(facts) < 2):
        facts.append(" / ".join(rooms))
    area = lot_sqm(row)
    if area and (c.min_lot_sqm or c.max_lot_sqm or c.sort == "lot_desc" or c.needs_boundary or c.category in {"house-and-lot", "lot"}):
        facts.append(f"{area:,.0f} sqm lot")
    if c.needs_boundary and row.get("boundary"):
        measured = row.get("boundary_measurements") or {}
        perimeter = _num(measured.get("perimeter_m")) if isinstance(measured, dict) else None
        facts.append("lot boundary on the map" + (f" ({perimeter:,.0f} m around)" if perimeter else ""))
    for group in c.near:
        place = nearest(row, group)
        if place:
            km = _num(place.get("distance_km"))
            facts.append(f"{place.get('name', ESTABLISHMENTS[group][0])}" + (f" {km:g} km away" if km is not None else ""))
    have = amenities_of(row)
    matched = [AMENITY_LABELS[a] for a in c.amenities if a in have]
    if matched:
        facts.append("with " + ", ".join(matched))
    for column in c.features:
        if row.get(column):
            label = FEATURES[column][0]
            if column == "has_garage" and _num(row.get("garage_spaces")):
                label = f"parking for {int(_num(row.get('garage_spaces')))}"
            facts.append(label)
    commute = row.get("commute_info")
    if isinstance(commute, dict) and commute.get("duration_mins") is not None:
        facts.append(f"about {round(commute['duration_mins'])} min to your workplace")
    return " · ".join(dict.fromkeys(facts))
