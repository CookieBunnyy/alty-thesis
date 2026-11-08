"""Developer accreditation, marketing approval, seller assignments and the
seller's own listing pages."""

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models.agent import Agent
from app.models.property_listing import PropertyListing
from tests.conftest import login


@pytest.fixture
def required(monkeypatch):
    monkeypatch.setattr(settings, "ACCREDITATION_REQUIRED", True)


def _listing(db, title="Acacia Townhomes Unit 3", **extra):
    listing = PropertyListing(title=title, status="AVAILABLE", sync_status="SYNCED", price_total=3_000_000, **extra)
    db.add(listing)
    db.commit()
    return listing.listing_id


def _developer(api, admin, **accreditation):
    made = api.post("/api/v1/partners", headers=admin, json={"name": "Camella Homes", "partner_type": "DEVELOPER",
                                                             **accreditation})
    assert made.status_code == 201, made.text
    return made.json()


def test_listing_needs_verified_accreditation(api, admin, db, required):
    listing_id = _listing(db, project_name="Acacia", floor_area_sqm=54)
    path = f"/api/v1/property-listings/{listing_id}"
    approve = lambda: api.post(f"{path}/marketing", headers=admin, json={"action": "approve"})  # noqa: E731

    # No developer yet: refused, and not on the public site.
    assert approve().status_code == 409
    assert api.get("/api/v1/public/properties").json() == []

    dev = _developer(api, admin, accreditation_status="PENDING")
    api.put(path, headers=admin, json={"partner_id": dev["id"]})
    refused = approve()
    assert refused.status_code == 409 and "isn't verified" in refused.json()["detail"]

    verified = api.put(f"/api/v1/partners/{dev['id']}", headers=admin, json={
        "accreditation_status": "VERIFIED", "accreditation_reference": "ACC-2026-014",
        "accreditation_valid_until": str(date.today() + timedelta(days=365))}).json()
    assert verified["accreditation"]["valid"] and verified["accreditation_verified_by"]
    approved = approve()
    assert approved.status_code == 200 and approved.json()["public"]
    public = api.get("/api/v1/public/properties").json()
    assert [p["listing_id"] for p in public] == [listing_id]
    assert public[0]["project_name"] == "Acacia" and public[0]["floor_area_sqm"] == 54

    # Expired accreditation takes the listing off the public site by itself.
    api.put(f"/api/v1/partners/{dev['id']}", headers=admin,
            json={"accreditation_valid_until": str(date.today() - timedelta(days=1))})
    assert api.get("/api/v1/public/properties").json() == []
    assert api.get(f"/api/v1/public/properties/{listing_id}").status_code == 404
    state = api.get(f"{path}/marketing", headers=admin).json()
    assert state["accreditation"]["status"] == "EXPIRED" and not state["public"]


def test_sellers_see_assigned_and_approved_listings_only(api, admin, db, required):
    for agent_id in ("AGT-51", "AGT-52"):
        db.add(Agent(agent_id=agent_id, full_name=agent_id, status="ACTIVE", sync_status="SYNCED"))
    db.commit()
    for username, agent_id in (("s51", "AGT-51"), ("s52", "AGT-52")):
        assert api.post("/api/v1/users", headers=admin, json={"username": username, "full_name": username,
                                                              "role": "Seller", "password": "password123",
                                                              "agent_id": agent_id}).status_code == 201
    mine = _listing(db, "Assigned but draft")
    other = _listing(db, "Draft, not mine")
    dev = _developer(api, admin, accreditation_status="VERIFIED")
    approved = _listing(db, "Approved for everyone", partner_id=dev["id"])
    api.post(f"/api/v1/property-listings/{approved}/marketing", headers=admin, json={"action": "approve"})
    assigned = api.post(f"/api/v1/property-listings/{mine}/sellers", headers=admin, json={"agent_id": "AGT-51"})
    assert assigned.status_code == 201 and assigned.json()["sellers"][0]["agent_id"] == "AGT-51"

    seller = login(api, "s51")
    rows = {r["listing_id"]: r for r in api.get("/api/v1/seller/listings", headers=seller).json()}
    assert set(rows) == {mine, approved} and other not in rows
    assert rows[mine]["assigned"] and not rows[approved]["assigned"]
    assert "details" in rows[mine]["editable_fields"] and rows[approved]["editable_fields"] == []

    ok = api.put(f"/api/v1/seller/listings/{mine}", headers=seller, json={"details": "Corner unit, near the gate."})
    assert ok.status_code == 200 and ok.json()["details"] == "Corner unit, near the gate."
    assert api.put(f"/api/v1/seller/listings/{mine}", headers=seller, json={"price_total": 1}).status_code == 403
    assert api.put(f"/api/v1/seller/listings/{approved}", headers=seller, json={"details": "x"}).status_code == 403
    # The other seller sees nothing assigned, and company pages stay closed.
    other_seller = login(api, "s52")
    assert {r["listing_id"] for r in api.get("/api/v1/seller/listings", headers=other_seller).json()} == {approved}
    assert api.get(f"/api/v1/property-listings/{mine}/marketing", headers=seller).status_code == 403
    assert api.get("/api/v1/seller/listings", headers=admin).status_code == 403   # not a seller account
    # Unassigning ends access to editing.
    api.delete(f"/api/v1/property-listings/{mine}/sellers/AGT-51", headers=admin)
    assert api.put(f"/api/v1/seller/listings/{mine}", headers=seller, json={"details": "y"}).status_code == 403
