from __future__ import annotations

from decimal import Decimal

from app.models.agent import Agent
from app.models.property_listing import PropertyListing
from tests.conftest import _make_user, login


def test_partners_are_real_records_managed_by_management(api, admin, employee, db):
    # Created by management; validated; duplicate names refused.
    created = api.post("/api/v1/partners", headers=admin, json={
        "name": "Amaia Land", "partner_type": "developer", "contact_person": "J. Cruz",
        "email": "sales@amaia.example", "website": "amaia.example"})
    assert created.status_code == 201, created.text
    partner = created.json()
    assert partner["partner_type"] == "DEVELOPER" and partner["status"] == "ACTIVE"
    assert partner["website"] == "https://amaia.example"
    assert api.post("/api/v1/partners", headers=admin, json={"name": "amaia land"}).status_code == 409
    assert api.post("/api/v1/partners", headers=admin, json={"name": "X", "email": "nope"}).status_code == 422

    # Everyone with the Partners page can view; only management changes.
    assert api.get("/api/v1/partners", headers=employee).status_code == 200
    assert api.post("/api/v1/partners", headers=employee, json={"name": "Nope"}).status_code == 403

    # A listing's developer: counted on the partner, and the partner can't be deleted while linked.
    listing = PropertyListing(title="Amaia Steps", category="condo", price_total=Decimal("2500000"), status="AVAILABLE",
                              sync_status="SYNCED")
    db.add(listing)
    db.commit()
    linked = api.put(f"/api/v1/property-listings/{listing.listing_id}", headers=admin, json={"partner_id": partner["id"]})
    assert linked.status_code == 200 and linked.json()["partner_id"] == partner["id"]
    assert api.put(f"/api/v1/property-listings/{listing.listing_id}", headers=admin, json={"partner_id": 99999}).status_code == 422
    detail = api.get(f"/api/v1/partners/{partner['id']}", headers=employee).json()
    assert detail["listings"] == 1 and detail["available_listings"] == 1 and detail["listing_rows"][0]["title"] == "Amaia Steps"
    blocked = api.delete(f"/api/v1/partners/{partner['id']}", headers=admin)
    assert blocked.status_code == 409 and "Inactive" in blocked.json()["detail"]
    assert api.put(f"/api/v1/partners/{partner['id']}", headers=admin, json={"status": "inactive"}).json()["status"] == "INACTIVE"

    # Unlinked partners can be deleted; every change is audited.
    other = api.post("/api/v1/partners", headers=admin, json={"name": "Temporary Partner"}).json()
    assert api.delete(f"/api/v1/partners/{other['id']}", headers=admin).status_code == 204
    actions = {e["action"] for e in api.get("/api/v1/audit?entity_type=partners", headers=admin).json()["items"]}
    assert {"PARTNER_CREATED", "PARTNER_UPDATED", "PARTNER_DELETED"} <= actions


def test_agent_accounts_link_to_one_agent_record_and_see_their_work(api, admin, db):
    db.add_all([Agent(agent_id="AGT-9", full_name="Nine Agent", status="ACTIVE", sync_status="SYNCED"),
                Agent(agent_id="AGT-8", full_name="Eight Agent", status="ACTIVE", sync_status="SYNCED")])
    db.commit()
    made = api.post("/api/v1/users", headers=admin, json={"username": "nine", "full_name": "Nine Agent", "role": "Agent",
                                                         "password": "password123", "agent_id": "AGT-9"})
    assert made.status_code == 201 and made.json()["agent_name"] == "Nine Agent"
    # One account per agent record; unknown agents refused.
    _make_user("other", "Agent")
    other_id = next(u["id"] for u in api.get("/api/v1/users", headers=admin).json() if u["username"] == "other")
    assert api.put(f"/api/v1/users/{other_id}", headers=admin, json={"agent_id": "AGT-9"}).status_code == 409
    assert api.put(f"/api/v1/users/{other_id}", headers=admin, json={"agent_id": "AGT-404"}).status_code == 422

    nine = login(api, "nine")
    assert api.get("/api/v1/auth/me", headers=nine).json()["agent_id"] == "AGT-9"
    work = api.get("/api/v1/agents/me/work", headers=nine).json()
    assert work["agent"]["agent_id"] == "AGT-9" and "recorded" in work["activity"] and "reviews" in work["reviews"]
    # Accounts without a link get a clear message.
    assert api.get("/api/v1/agents/me/work", headers=login(api, "other")).status_code == 404
