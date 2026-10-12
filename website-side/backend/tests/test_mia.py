"""MIA: preferences read from messages, requirement matching, FAQs and the /chat flow.

No network: listings, geocoding and routing are replaced with fixed data.
"""

import pytest

from assistant import criteria as crit
from assistant.faq import answer
from assistant.search import filter_rows, why

BOUNDARY = {"type": "Polygon", "coordinates": [[[121.0, 14.5], [121.001, 14.5], [121.001, 14.501], [121.0, 14.5]]]}

ROWS = [
    {"listing_id": 1, "title": "Garden Home Antipolo", "category": "House and Lot", "price_total": 4_800_000,
     "initial_dp": 480_000, "monthly_rate": 32_000, "num_bedrooms": 3, "num_bathrooms": 2, "lot_area_sqm": 220,
     "boundary": BOUNDARY, "boundary_measurements": {"area_sqm": 221.4, "perimeter_m": 61.0},
     "village_name": "San Roque, Antipolo", "has_garage": True, "garage_spaces": 2, "has_backyard": True,
     "amenity_list": {"security": True, "playground": True, "pool": False},
     "nearby_establishments": {"schools": [{"name": "Antipolo Elementary", "distance_km": 0.4}],
                               "malls": [{"name": "SM Masinag", "distance_km": 3.2}]},
     "lat": 14.6, "lng": 121.17, "status": "AVAILABLE"},
    {"listing_id": 2, "title": "Uptown Loft BGC", "category": "condo", "price_total": 7_500_000,
     "initial_dp": 750_000, "monthly_rate": 45_000, "num_bedrooms": 1, "num_bathrooms": 1, "lot_area_sqm": None,
     "boundary": None, "village_name": "BGC, Taguig", "has_balcony": True,
     "amenity_list": {"pool": True, "gym": True, "security": True},
     "nearby_establishments": {"malls": [{"name": "Uptown Mall", "distance_km": 0.4}],
                               "hospitals": [{"name": "St. Lukes BGC", "distance_km": 0.6}]},
     "lat": 14.55, "lng": 121.05, "status": "AVAILABLE"},
    {"listing_id": 3, "title": "Bacoor Townhouse", "category": "Townhouse", "price_total": 2_900_000,
     "initial_dp": 150_000, "monthly_rate": 15_500, "num_bedrooms": 2, "num_bathrooms": 1, "lot_area_sqm": 80,
     "boundary": None, "village_name": "Molino, Bacoor", "amenity_list": ["security"],
     "nearby_establishments": {"schools": [{"name": "Molino High", "distance_km": 1.5}]},
     "lat": 14.4, "lng": 120.97, "status": "AVAILABLE"},
    {"listing_id": 4, "title": "Batangas Farm Lot", "category": "Lot Only", "price_total": 3_600_000,
     "initial_dp": 360_000, "monthly_rate": 20_000, "lot_area_sqm": 12_000, "boundary": BOUNDARY,
     "boundary_measurements": {"area_sqm": 11_950.0, "perimeter_m": 440.0}, "village_name": "Lipa, Batangas",
     "amenity_list": {}, "nearby_establishments": {}, "lat": 13.94, "lng": 121.16, "status": "AVAILABLE"},
]


# ---- reading preferences ------------------------------------------------------------

@pytest.mark.parametrize("message, expected", [
    ("I want a house and lot that has lot boundary", {"category": "house-and-lot", "needs_boundary": True}),
    ("3 bedroom 2 bathroom house with at least 200 sqm lot",
     {"category": "house-and-lot", "min_bedrooms": 3, "min_bathrooms": 2, "min_lot_sqm": 200}),
    ("three bedrooms and two CRs", {"min_bedrooms": 3, "min_bathrooms": 2}),
    ("lot of 1 hectare", {"min_lot_sqm": 10_000}),
    ("townhouse under 100 sqm", {"category": "townhouse", "max_lot_sqm": 100}),
    ("condo with a pool and gym near a mall", {"category": "condominium", "amenities": ["gym", "pool"], "near": ["malls"]}),
    ("house walking distance to a school", {"near": ["schools"], "near_max_km": 1.0}),
    ("within 2 km of a hospital", {"near": ["hospitals"], "near_max_km": 2.0}),
    ("house with 2 car garage and a balcony", {"features": ["has_balcony", "has_garage"], "min_garage_spaces": 2}),
    ("between 2M and 4M", {"min_price": 2_000_000, "max_price": 4_000_000}),
    ("biggest lot you have", {"sort": "lot_desc"}),
    ("lowest down payment", {"sort": "dp_asc"}),
    ("cheapest condo", {"category": "condominium", "sort": "price_asc"}),
    ("within 45 minutes of my work", {"max_commute_mins": 45}),
    ("less than an hour commute", {"max_commute_mins": 60}),
])
def test_preferences_are_read(message, expected):
    found, _ = crit.parse(message)
    for key, value in expected.items():
        assert getattr(found, key) == value, (message, key, getattr(found, key))


def test_lot_area_and_rooms_are_not_money():
    _, money_text = crit.parse("house 3 bedrooms 200 sqm under 5M")
    assert "200" not in money_text and "5 m" in money_text
    found, _ = crit.parse("15k-20k monthly")
    assert found.min_price is None and found.max_price is None  # a monthly range, not the price


def test_townhouse_is_not_a_house():
    found, _ = crit.parse("townhouse in Bacoor")
    assert found.category == "townhouse"


def test_follow_ups_refine_the_last_search():
    first, _ = crit.parse("house and lot under 5M")
    first.max_price = 5_000_000
    more, _ = crit.parse("how about with 2 bathrooms?")
    assert crit.is_refinement("how about with 2 bathrooms?")
    merged = first.merged_with(more)
    assert merged.category == "house-and-lot" and merged.min_bathrooms == 2 and merged.max_price == 5_000_000
    assert crit.wants_reset("start over")


# ---- matching listings ---------------------------------------------------------------

def test_boundary_request_returns_only_lots_with_a_boundary():
    wanted, _ = crit.parse("I want a house and lot that has lot boundary")
    allowed, relaxed = filter_rows(ROWS, wanted)
    assert [ROWS[i]["listing_id"] for i in allowed] == [1] and relaxed == []
    assert "lot boundary on the map (61 m around)" in why(ROWS[0], wanted)


def test_requirements_combine():
    wanted, _ = crit.parse("3 bedroom house with 200 sqm lot near a school with parking")
    allowed, _ = filter_rows(ROWS, wanted)
    assert [ROWS[i]["listing_id"] for i in allowed] == [1]
    assert "Antipolo Elementary 0.4 km away" in why(ROWS[0], wanted)


def test_closest_options_when_nothing_matches_everything():
    wanted, _ = crit.parse("condo with a pool and a helipad")
    allowed, relaxed = filter_rows(ROWS, wanted)
    assert relaxed == ["helipad"] and [ROWS[i]["listing_id"] for i in allowed] == [2]


def test_monthly_and_down_payment_limits():
    wanted = crit.Criteria(max_downpayment=200_000, max_monthly=16_000)
    allowed, _ = filter_rows(ROWS, wanted)
    assert [ROWS[i]["listing_id"] for i in allowed] == [3]


# ---- frequently asked questions --------------------------------------------------------

@pytest.mark.parametrize("message, intent", [
    ("hello", "greeting"),
    ("How do I reserve a property?", "reserve"),
    ("how much is the reservation fee", "reservation_fee"),
    ("what is a lot boundary?", "boundary"),
    ("Do you accept Pag-IBIG?", "financing"),
    ("what are the requirements", "requirements"),
    ("can I schedule a site visit", "viewing"),
    ("how many properties do you have", "inventory"),
    ("what is the price range", "price_range"),
    ("where are your properties located?", "locations"),
    ("how is the travel time computed?", "commute"),
    ("who are you", "who"),
    ("what can you do", "help"),
])
def test_frequent_questions(message, intent):
    found = answer(message, ROWS)
    assert found and found[0] == intent, (message, found)


def test_live_answers_use_the_listings():
    assert "4 available properties" in answer("how many properties do you have", ROWS)[1]
    assert "₱2.90M to ₱7.50M" in answer("what is the price range", ROWS)[1]
    assert "2 available properties have a drawn boundary" in answer("what is a lot boundary", ROWS)[1]


def test_searches_are_not_mistaken_for_questions():
    assert answer("show me houses with a lot boundary", ROWS) is None
    assert answer("I want a house near a school", ROWS) is None


# ---- the chat endpoint ----------------------------------------------------------------

@pytest.fixture
def chat(monkeypatch):
    import main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(main, "_fetch_listings", lambda: [dict(r) for r in ROWS])
    monkeypatch.setattr(main, "geocode_location", lambda name: None)
    monkeypatch.setattr(main, "calculate_osrm_commute", lambda *a: None)
    monkeypatch.setattr(main, "place_entities", lambda text: [])
    main.load_recommender()
    client = TestClient(main.app)
    return lambda message, context=None: client.post("/chat", json={"message": message, "context": context}).json()


def test_chat_finds_lots_with_a_boundary(chat):
    body = chat("i want a house and lot that has lot boundary")
    assert body["status"] == "recommendation_found"
    assert [r["listing_id"] for r in body["recommendations"]] == [1]
    assert "a drawn lot boundary" in body["reply"] and "budget" in body["reply"]  # asks the next question


def test_chat_refines_and_explains_relaxing(chat):
    first = chat("house and lot under 5M")
    assert [r["listing_id"] for r in first["recommendations"]] == [1]
    follow = chat("how about with 4 bathrooms?", first["context"])
    assert follow["context"]["category"] == "house-and-lot" and follow["context"]["min_bathrooms"] == 4
    assert "I left out: 4+ bathrooms" in follow["reply"]


def test_chat_answers_questions_and_keeps_context(chat):
    body = chat("how do I reserve?", {"category": "condominium"})
    assert body["intent"] == "reserve" and body["context"] == {"category": "condominium"}
    assert chat("start over")["context"] is None


def test_chat_sorts_by_request(chat):
    body = chat("show me the biggest lot")
    assert body["recommendations"][0]["listing_id"] == 4
    body = chat("lowest down payment")
    assert body["recommendations"][0]["listing_id"] == 3


def test_only_the_blocking_requirement_is_relaxed():
    # Garage is met by listing 1; only the helipad can't be.
    wanted = crit.Criteria(features=["has_garage"], amenities=["helipad"], category="house-and-lot")
    allowed, relaxed = filter_rows(ROWS, wanted)
    assert relaxed == ["helipad"] and [ROWS[i]["listing_id"] for i in allowed] == [1]


def test_gibberish_after_a_search_is_not_a_search(chat):
    first = chat("house and lot under 5M")
    body = chat("asdfgh qwerty", first["context"])
    assert body["status"] == "casual_chat" and body["recommendations"] == []
