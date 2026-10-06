from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction


def _listing(db, title, category, price, status="AVAILABLE", lat=14.5, lng=121.0, photos=("x.jpg",)):
    listing = PropertyListing(title=title, category=category, price_total=Decimal(price), status=status,
                              lat=lat, lng=lng, photos=list(photos), sync_status="SYNCED")
    db.add(listing)
    db.flush()
    return listing


def _agent(db, agent_id, transactions, completed, assignments=10, status="ACTIVE"):
    db.add(Agent(agent_id=agent_id, full_name=f"Agent {agent_id}", status=status, sync_status="SYNCED",
                 transactions_count=transactions, completed_sales=completed, assignments_count=assignments))


def _tx(db, listing, agent_id, kind, status, days_ago, amount="1000000"):
    client = Client(full_name=f"Client {listing.listing_id}-{days_ago}", status="RESERVED", source="DOCUMENT",
                    sync_status="SYNCED")
    db.add(client)
    db.flush()
    db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                               transaction_type=kind, status=status, amount=Decimal(amount), source="DOCUMENT",
                               transaction_date=datetime.now(timezone.utc) - timedelta(days=days_ago)))


def _seed(db):
    _agent(db, "AGT-A", 20, 18)            # 90% — well above average
    _agent(db, "AGT-B", 20, 6, assignments=30)  # 30% with a heavy workload
    _agent(db, "AGT-C", 20, 12)
    _agent(db, "AGT-D", 20, 12)
    condos = [_listing(db, f"Condo {i}", "condo", 2_000_000 + i * 10_000) for i in range(4)]
    pricey = _listing(db, "Pricey Condo", "Condominium", 3_500_000)       # "condo" and "Condominium" compare together
    unmapped = _listing(db, "No Map House", "house", 5_000_000, lat=None, lng=None, photos=())
    for listing in condos:
        _tx(db, listing, "AGT-A", "RESERVED", "RESERVED", 10)
    _tx(db, condos[0], "AGT-B", "RESERVED", "RESERVED", 90)              # stale reservation
    db.commit()
    return pricey, unmapped, condos[0]


def test_intelligence_is_contextual_explainable_and_management_only(api, admin, employee, db):
    pricey, unmapped, stale = _seed(db)

    prop = api.get(f"/api/v1/intelligence/properties/{pricey.listing_id}", headers=admin).json()["insights"]
    high_price = next(i for i in prop if i["title"] == "Priced above comparable listings")
    assert high_price["severity"] == "medium" and "Condominium" in high_price["finding"]
    assert high_price["recommendation"] and high_price["rule"] and high_price["factors"]

    titles = {i["title"] for i in api.get(f"/api/v1/intelligence/properties/{unmapped.listing_id}", headers=admin).json()["insights"]}
    assert {"Not on the website map", "No photos", "No recorded activity"} <= titles

    stale_titles = [i["title"] for i in api.get(f"/api/v1/intelligence/properties/{stale.listing_id}", headers=admin).json()["insights"]]
    assert "Reservation without a sale" in stale_titles

    good = {i["title"]: i for i in api.get("/api/v1/intelligence/agents/AGT-A", headers=admin).json()["insights"]}
    assert good["Completed-sales rate above average"]["severity"] == "positive"
    # AGT-A also holds 4 of the 5 open reservations: flagged, and ranked first (medium before positive).
    assert good["Heavy reservation load"]["severity"] == "medium"
    weak = {i["title"]: i for i in api.get("/api/v1/intelligence/agents/AGT-B", headers=admin).json()["insights"]}
    assert "workload" in weak["Completed-sales rate below average despite a high workload"]["recommendation"]

    analytics_view = api.get("/api/v1/intelligence/analytics", headers=admin).json()
    leader = next(i for i in analytics_view["insights"] if i["id"] == "market-category-leader")
    assert "Condominium" in leader["title"]
    assert any(i["title"] == "Not enough history for a trend" for i in analytics_view["insights"])
    assert analytics_view["breakdown"]["by_category"][0]["name"] == "Condominium"

    # No fabricated forecast: one month of data is not enough.
    forecast = api.get("/api/v1/intelligence/forecast?metric=transactions", headers=admin).json()
    assert forecast["forecast"]["status"] == "insufficient_data" and forecast["forecast"]["forecast"] == []
    assert forecast["insights"][0]["title"] == "No forecast yet"

    feed = api.get("/api/v1/intelligence/insights", headers=admin).json()
    severities = [i["severity"] for i in feed["items"]]
    order = {"high": 0, "medium": 1, "positive": 2, "info": 3}
    assert severities == sorted(severities, key=order.get)
    assert feed["counts"]["medium"] >= 3 and not any(i["title"] == "Sold" for i in feed["items"])

    # Decision support is for management roles, like the desktop.
    assert api.get("/api/v1/intelligence/insights", headers=employee).status_code == 403
    assert api.get(f"/api/v1/intelligence/properties/{pricey.listing_id}", headers=employee).status_code == 403
    # The desktop's existing endpoint is unchanged.
    assert api.get("/api/v1/analytics/dss", headers=admin).status_code == 200
