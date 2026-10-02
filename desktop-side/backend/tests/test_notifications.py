from __future__ import annotations

from app.models.review import AgentReview
from tests.test_client_portal import _listing, _record_transaction, _register


def _keys(response) -> dict[str, dict]:
    assert response.status_code == 200, response.text
    return {item["key"].split(":")[0]: item for item in response.json()["items"]}


def test_notifications_come_from_records_and_respect_roles(api, admin, employee, agents, db):
    _register(api)  # a website client account
    listing = _listing(db)  # available, no coordinates
    transaction = _record_transaction(db, "ana.reyes@example.com", listing.listing_id, "RESERVED")
    db.add(AgentReview(agent_id="AGT-0003", client_id=transaction.client_id,
                       transaction_id=transaction.transaction_id, rating=2, review="Slow to reply"))
    db.commit()
    api.post("/api/v1/auth/login", data={"username": "admin", "password": "wrong"})  # failed sign-in

    items = _keys(api.get("/api/v1/notifications", headers=admin))
    assert items["transaction"]["title"] == "Reservation recorded"
    assert "Ana Reyes" in items["transaction"]["message"] and "Angela Cruz" in items["transaction"]["message"]
    assert items["review"]["title"] == "New 2★ review for Angela Cruz" and items["review"]["severity"] == "warning"
    assert items["client-account"]["message"] == "Ana Reyes signed up on the website"
    assert items["listings-no-location"]["page"] == "properties"
    assert items["login-failed"]["page"] == "audit"
    assert all(not item["read"] for item in items.values())

    # Employees get their pages' notifications but no security alerts.
    employee_items = _keys(api.get("/api/v1/notifications", headers=employee))
    assert "transaction" in employee_items and "login-failed" not in employee_items

    # Read marks are per user; a status change is a new (unread) notification.
    key = items["transaction"]["key"]
    after = api.post("/api/v1/notifications/read", json={"keys": [key]}, headers=admin).json()
    assert next(i for i in after["items"] if i["key"] == key)["read"]
    assert after["unread"] == len(items) - 1
    assert not _keys(api.get("/api/v1/notifications", headers=employee))["transaction"]["read"]

    transaction.status = "COMPLETED"
    db.commit()
    updated = _keys(api.get("/api/v1/notifications", headers=admin))["transaction"]
    assert updated["title"] == "Sale completed" and not updated["read"]

    cleared = api.post("/api/v1/notifications/read-all", headers=admin).json()
    assert cleared["unread"] == 0
    assert api.get("/api/v1/notifications").status_code == 401
