"""Roles from the Abellar Realty interview: Administrator (Admin / Marketing
staff), Filing Manager and Seller (the Broker role was folded into Administrator); developers have no
accounts; sellers never see company-wide or other sellers' records."""

from app.core.security import canonical_role, permissions_for
from app.models.agent import Agent
from tests.conftest import _make_user, login

COMPANY_ENDPOINTS = (
    "/api/v1/transactions", "/api/v1/transactions/summary", "/api/v1/clients", "/api/v1/agents",
    "/api/v1/dashboard/summary", "/api/v1/dashboard/agent-performance", "/api/v1/analytics/overview",
    "/api/v1/analytics/monthly", "/api/v1/documents", "/api/v1/property-listings", "/api/v1/search?q=ana",
    "/api/v1/intelligence/forecast", "/api/v1/users", "/api/v1/partners",
)


def _seller(api, admin, db, agent_id="AGT-77", username="seller77"):
    db.add(Agent(agent_id=agent_id, full_name=f"Seller {agent_id}", status="ACTIVE", sync_status="SYNCED"))
    db.commit()
    made = api.post("/api/v1/users", headers=admin, json={"username": username, "full_name": "Seller",
                                                         "role": "Seller", "password": "password123",
                                                         "agent_id": agent_id})
    assert made.status_code == 201, made.text
    return login(api, username)


def test_legacy_names_map_to_the_new_roles():
    assert canonical_role("President") == "Administrator"
    assert canonical_role("Broker") == "Administrator"       # the Broker role was removed
    assert canonical_role("general manager") == "Administrator"
    assert canonical_role("Employee") == "Filing Manager"
    assert canonical_role("Agent") == "Seller"
    assert canonical_role("Developer") == "Seller"           # unknown names get the least access
    assert "reports" in permissions_for("Filing Manager") and "users" not in permissions_for("Filing Manager")
    assert permissions_for("Seller") == ["my-work", "bulletin", "trips", "my-listings", "my-deals", "my-commissions",
                                        "settings"]


def test_seller_cannot_read_company_records(api, admin, db):
    seller = _seller(api, admin, db)
    for path in COMPANY_ENDPOINTS:
        assert api.get(path, headers=seller).status_code == 403, path
    # Their own work is open to them.
    mine = api.get("/api/v1/agents/me/work", headers=seller)
    assert mine.status_code == 200 and mine.json()["agent"]["agent_id"] == "AGT-77"
    me = api.get("/api/v1/auth/me", headers=seller).json()
    assert me["role"] == "Seller" and "reports" not in me["permissions"]


def test_seller_accounts_must_be_linked_and_developers_get_none(api, admin):
    base = {"full_name": "X", "password": "password123"}
    assert api.post("/api/v1/users", headers=admin, json={**base, "username": "s1", "role": "Seller"}).status_code == 422
    assert api.post("/api/v1/users", headers=admin, json={**base, "username": "d1", "role": "Developer"}).status_code == 422
    roles = [r["name"] for r in api.get("/api/v1/users/roles", headers=admin).json()]
    assert roles == ["Administrator", "Filing Manager", "Seller"]


def test_old_broker_accounts_and_filing_manager_scope(api, admin):
    _make_user("owner", "Broker")
    _make_user("filer", "Filing Manager")
    owner, filer = login(api, "owner"), login(api, "filer")
    # An account still stored as "Broker" works as an Administrator.
    assert api.get("/api/v1/auth/me", headers=owner).json()["role"] == "Administrator"
    for path in ("/api/v1/transactions", "/api/v1/intelligence/forecast", "/api/v1/audit", "/api/v1/users"):
        assert api.get(path, headers=owner).status_code == 200, path
    assert api.post("/api/v1/users", headers=admin, json={"username": "b2", "full_name": "B", "role": "Broker",
                                                          "password": "password123"}).status_code == 422
    # The filing manager reads sales records and documents, but doesn't manage listings or users.
    assert api.get("/api/v1/transactions", headers=filer).status_code == 200
    assert api.get("/api/v1/documents", headers=filer).status_code == 200
    assert api.get("/api/v1/users", headers=filer).status_code == 403
    assert api.put("/api/v1/property-listings/1", headers=filer, json={"title": "x"}).status_code == 403
