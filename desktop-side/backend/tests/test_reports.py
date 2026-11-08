"""Sales and recruitment reports with their filters, and who may read them."""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from tests.conftest import _make_user, login

API = "/api/v1"


def _sale(db, agent_id, amount, day, project):
    listing = PropertyListing(title=f"{project} unit {amount}", project_name=project, status="SOLD",
                              sync_status="SYNCED", price_total=Decimal(amount))
    client = Client(full_name=f"Buyer {amount}", status="SOLD", source="SYNC", sync_status="SYNCED")
    db.add_all([listing, client])
    db.flush()
    db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                               transaction_type="SOLD", status="COMPLETED", amount=Decimal(amount),
                               transaction_date=datetime(day.year, day.month, day.day, 4, tzinfo=timezone.utc),
                               source="SYNC", sync_status="SYNCED"))


def test_sales_report_groups_and_filters(api, admin, employee, agents, db):
    pinyas = api.post(f"{API}/branches", headers=admin, json={"name": "Pinyas"}).json()["id"]
    api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin, json={"branch_id": pinyas})
    _sale(db, agents[0], 3_000_000, date(2026, 3, 5), "Acacia Estates")
    _sale(db, agents[0], 2_000_000, date(2026, 3, 20), "Acacia Estates")
    _sale(db, agents[1], 4_500_000, date(2026, 4, 2), "Lumina Homes")
    _sale(db, agents[1], 9_000_000, date(2025, 12, 30), "Lumina Homes")      # outside the range
    db.commit()

    body = api.get(f"{API}/reports/sales?start=2026-01-01&end=2026-06-30", headers=employee).json()
    assert body["totals"]["sales"] == 3 and body["totals"]["revenue"] == 9_500_000
    assert [p["period"] for p in body["by_period"]] == ["2026-03", "2026-04"]
    assert body["top_sellers"][0]["agent_id"] == agents[0] and body["top_sellers"][0]["revenue"] == 5_000_000
    assert {p["name"]: p["sales"] for p in body["by_project"]} == {"Acacia Estates": 2, "Lumina Homes": 1}
    assert {t["name"]: t["revenue"] for t in body["by_team"]} == {"Pinyas": 5_000_000, "No team": 4_500_000}
    daily = api.get(f"{API}/reports/sales?start=2026-03-01&end=2026-03-31&period=day", headers=admin).json()
    assert [p["period"] for p in daily["by_period"]] == ["2026-03-05", "2026-03-20"]
    yearly = api.get(f"{API}/reports/sales?start=2025-01-01&end=2026-12-31&period=year", headers=admin).json()
    assert [(p["period"], p["sales"]) for p in yearly["by_period"]] == [("2025", 1), ("2026", 3)]
    team = api.get(f"{API}/reports/sales?start=2026-01-01&end=2026-12-31&team_id={pinyas}", headers=admin).json()
    assert team["totals"]["sales"] == 2
    project = api.get(f"{API}/reports/sales?start=2026-01-01&end=2026-12-31&project=lumina", headers=admin).json()
    assert project["totals"]["revenue"] == 4_500_000
    seller = api.get(f"{API}/reports/sales?start=2026-01-01&end=2026-12-31&agent_id={agents[1]}", headers=admin).json()
    assert seller["totals"]["sales"] == 1
    assert api.get(f"{API}/reports/sales?start=2026-05-01&end=2026-01-01", headers=admin).status_code == 422


def test_recruitment_report_and_access(api, admin, employee, agents, db):
    team = api.post(f"{API}/branches", headers=admin, json={"name": "San Pablo"}).json()["id"]
    base = f"{API}/recruitment/applicants"
    for name, recruiter in (("Ana", agents[0]), ("Ben", agents[0]), ("Cy", None)):
        made = api.post(base, headers=admin, json={"full_name": name, "recruiter_agent_id": recruiter,
                                                   "recruiter_name": None if recruiter else "Walk-in desk",
                                                   "branch_id": team, "not_bound_to_other_broker": True}).json()
        if name == "Ana":
            for status in ("SCREENING", "INTERVIEW", "APPROVED"):
                api.post(f"{base}/{made['id']}/stage", headers=admin, json={"status": status})
            api.post(f"{base}/{made['id']}/onboard", headers=admin, json={})
    today = date.today()
    body = api.get(f"{API}/reports/recruitment?start={today.year}-01-01&end={today}", headers=admin).json()
    assert body["totals"] == {"applications": 3, "recruited": 1}
    top = body["top_recruiters"][0]
    assert top["recruiter_agent_id"] == agents[0] and top["recruited"] == 1 and top["applications"] == 2
    assert {r["name"] for r in body["top_recruiters"]} == {"Angela Cruz", "Walk-in desk"}
    assert body["by_team"][0]["name"] == "San Pablo" and body["by_status"]["ONBOARDED"] == 1
    # The filing manager reads sales reports only; sellers read none.
    assert api.get(f"{API}/reports/recruitment", headers=employee).status_code == 403
    dash = api.get(f"{API}/reports/dashboard", headers=employee).json()
    assert "sales" in dash and "recruitment" not in dash
    assert "recruitment" in api.get(f"{API}/reports/dashboard", headers=admin).json()
    db.add(Agent(agent_id="AGT-90", full_name="Seller Ninety", status="ACTIVE", sync_status="SYNCED"))
    db.commit()
    api.post(f"{API}/users", headers=admin, json={"username": "s90", "full_name": "S", "role": "Seller",
                                                  "password": "password123", "agent_id": "AGT-90"})
    seller = login(api, "s90")
    for path in ("/reports/sales", "/reports/recruitment", "/reports/dashboard"):
        assert api.get(f"{API}{path}", headers=seller).status_code == 403, path
