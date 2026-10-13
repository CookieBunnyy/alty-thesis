"""Branches, agent assignment, recruitment, assessments, commission and the
workforce demand-vs-capacity plan."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services import analytics, workforce_planning

API = "/api/v1"


def _branch(api, admin, name, code=None):
    response = api.post(f"{API}/branches", headers=admin, json={"name": name, "code": code})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _months_back(n: int) -> tuple[int, int]:
    today = datetime.now(timezone.utc)
    index = today.year * 12 + today.month - 1 - n
    return index // 12, index % 12 + 1


def _deal(db, agent_id, amount, months_ago, kind="SOLD", status="COMPLETED", day=10):
    year, month = _months_back(months_ago)
    listing = PropertyListing(title=f"Home {agent_id} {months_ago} {amount}", price_total=Decimal(amount),
                              status="SOLD" if kind == "SOLD" else "RESERVED", sync_status="SYNCED")
    client = Client(full_name=f"Buyer {agent_id} {months_ago}", status="SOLD", source="SYNC", sync_status="SYNCED")
    db.add_all([listing, client])
    db.flush()
    db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                               transaction_type=kind, status=status, amount=Decimal(amount),
                               transaction_date=datetime(year, month, day, 4, tzinfo=timezone.utc),
                               source="SYNC", sync_status="SYNCED"))


# ---- branches ------------------------------------------------------------------------

def test_branches_crud_and_rules(api, admin, employee, agents, db):
    assert api.post(f"{API}/branches", headers=employee, json={"name": "X"}).status_code == 403
    cavite = _branch(api, admin, "Cavite Branch", "CAV")
    assert api.post(f"{API}/branches", headers=admin, json={"name": "cavite branch"}).status_code == 409
    assert api.post(f"{API}/branches", headers=admin, json={"name": "Laguna", "code": "cav"}).status_code == 409
    assert api.get(f"{API}/branches", headers=employee).status_code == 200  # pickers for every staff role
    edited = api.put(f"{API}/branches/{cavite}", headers=admin, json={"address": "Imus, Cavite"}).json()
    assert edited["address"] == "Imus, Cavite" and edited["name"] == "Cavite Branch"

    # Assign an agent; the branch can't be deleted while it has agents.
    assigned = api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin,
                       json={"branch_id": cavite, "designation": "Senior Sales Agent", "work_area": "Imus, Bacoor"})
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert body["branch_name"] == "Cavite Branch" and body["designation"] == "Senior Sales Agent"
    assert api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin,
                   json={"designation": "Wizard"}).status_code == 422
    assert api.put(f"{API}/agents/{agents[0]}/assignment", headers=employee, json={}).status_code == 403
    assert api.delete(f"{API}/branches/{cavite}", headers=admin).status_code == 409
    api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin, json={"branch_id": None})
    assert api.delete(f"{API}/branches/{cavite}", headers=admin).status_code == 204


def test_listing_branch(api, admin, db):
    branch = _branch(api, admin, "Laguna Branch")
    listing = PropertyListing(title="Sta. Rosa Home", status="AVAILABLE", sync_status="SYNCED")
    db.add(listing)
    db.commit()
    path = f"{API}/property-listings/{listing.listing_id}"
    assert api.put(path, headers=admin, json={"branch_id": 999}).status_code == 422
    saved = api.put(path, headers=admin, json={"branch_id": branch})
    assert saved.status_code == 200 and saved.json()["branch_id"] == branch


def test_branch_comparison_and_commission(api, admin, employee, agents, db):
    north, south = _branch(api, admin, "North"), _branch(api, admin, "South")
    api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin, json={"branch_id": north})
    api.put(f"{API}/agents/{agents[1]}/assignment", headers=admin, json={"branch_id": south})
    # agents[0] has a recorded 5% rate; the others use the 3% default.
    agent = db.get(Agent, agents[0])
    agent.total_sales, agent.total_commission = Decimal(10_000_000), Decimal(500_000)
    db.commit()
    for months_ago in range(1, 8):
        _deal(db, agents[0], 2_000_000 + months_ago * 100_000, months_ago)
        _deal(db, agents[1], 1_000_000, months_ago)
    _deal(db, agents[2], 3_000_000, 1)  # no branch
    db.commit()

    assert api.get(f"{API}/branches/comparison", headers=employee).status_code == 403
    body = api.get(f"{API}/branches/comparison", headers=admin).json()
    rows = {row["name"]: row for row in body["branches"]}
    assert set(rows) == {"North", "South", "No branch"}
    assert rows["North"]["last_month"]["revenue"] == 2_100_000
    assert rows["North"]["last_month"]["commission"] == 105_000          # 5%
    assert rows["South"]["last_month"]["commission"] == 30_000           # 3% default
    assert rows["No branch"]["totals"]["revenue"] == 3_000_000
    assert rows["North"]["trend_per_month"] < 0                          # older months sold more
    assert rows["North"]["forecast_status"] == "estimated" and body["best_last_month"] == "North"

    # Commission is a Business Outlook measure like the others.
    outlook = api.get(f"{API}/intelligence/forecast?metric=commission&horizon=2", headers=admin)
    assert outlook.status_code == 200, outlook.text
    history = {p["month"]: p["value"] for p in outlook.json()["forecast"]["history"]}
    key = "%04d-%02d" % _months_back(1)
    assert history[key] == 105_000 + 30_000 + 90_000
    month = api.get(f"{API}/intelligence/outlook/month?month={key}&metric=commission", headers=admin).json()
    assert month["total"] == 225_000 and {round(i["commission_rate"], 2) for i in month["items"]} == {0.05, 0.03}
    agent_commission = api.get(f"{API}/agents/{agents[0]}/commission?months=3", headers=admin).json()
    assert agent_commission["rate"] == 0.05 and len(agent_commission["months"]) == 3


# ---- demand vs capacity ------------------------------------------------------------------

def test_capacity_plan_reallocates_then_recruits(api, admin, agents, db):
    busy, quiet = _branch(api, admin, "Busy"), _branch(api, admin, "Quiet")
    # Busy: one agent with 6 deals a month for 7 months. Quiet: three agents, one deal a month in total.
    api.put(f"{API}/agents/{agents[0]}/assignment", headers=admin, json={"branch_id": busy})
    for agent_id in agents[1:]:
        api.put(f"{API}/agents/{agent_id}/assignment", headers=admin, json={"branch_id": quiet})
    for months_ago in range(1, 8):
        for day in range(1, 7):
            _deal(db, agents[0], 1_000_000, months_ago, day=day)
        _deal(db, agents[1], 1_000_000, months_ago)
    db.commit()

    plan = api.get(f"{API}/intelligence/workforce-plan?capacity=2", headers=admin).json()
    rows = {row["name"]: row for row in plan["branches"]}
    assert plan["capacity"]["per_agent"] == 2 and plan["capacity"]["overridden"]
    assert rows["Busy"]["agents_needed"] == 3 and rows["Busy"]["gap"] == 2 and rows["Busy"]["status"] == "SHORT"
    assert rows["Quiet"]["status"] == "OVER"
    kinds = [(r["kind"], r.get("from_branch"), r.get("to_branch"), r["agents"]) for r in plan["recommendations"]]
    assert ("REALLOCATE", "Quiet", "Busy", 2) in kinds

    tight = api.get(f"{API}/intelligence/workforce-plan?capacity=1", headers=admin).json()
    assert any(r["kind"] == "RECRUIT" and r["to_branch"] == "Busy" for r in tight["recommendations"])
    observed = workforce_planning.observed_capacity(db)
    assert observed["basis"] == "observed" and observed["value"] >= 1


# ---- recruitment ----------------------------------------------------------------------------

def test_recruitment_pipeline_onboards_an_agent(api, admin, employee, agents, db):
    branch = _branch(api, admin, "Cavite Branch")
    base = f"{API}/recruitment/applicants"
    assert api.get(base, headers=employee).status_code == 403
    assert api.post(base, headers=admin, json={"full_name": "Jo", "email": "bad"}).status_code == 422
    created = api.post(base, headers=admin, json={"full_name": "Jose Rizal", "phone_number": "0917 000 0000",
                                                  "branch_id": branch, "desired_designation": "Sales Agent",
                                                  "source": "referral", "has_license": True})
    assert created.status_code == 201, created.text
    applicant = created.json()
    assert applicant["status"] == "APPLIED" and applicant["source"] == "REFERRAL" and len(applicant["history"]) == 1
    stage = f"{base}/{applicant['id']}/stage"
    assert api.post(stage, headers=admin, json={"status": "INTERVIEW"}).status_code == 409   # skips screening
    assert api.post(f"{base}/{applicant['id']}/onboard", headers=admin, json={}).status_code == 409
    for status in ("SCREENING", "INTERVIEW", "APPROVED"):
        assert api.post(stage, headers=admin, json={"status": status}).status_code == 200
    onboarded = api.post(f"{base}/{applicant['id']}/onboard", headers=admin, json={"work_area": "Imus"})
    assert onboarded.status_code == 200, onboarded.text
    agent_id = onboarded.json()["agent"]["agent_id"]
    assert agent_id == "AGT-0008"                                   # after the test agents' highest number
    agent = db.get(Agent, agent_id)
    assert agent.branch_id == branch and agent.designation == "Sales Agent" and agent.sync_status == "PENDING"
    assert onboarded.json()["status"] == "ONBOARDED"
    assert api.delete(f"{base}/{applicant['id']}", headers=admin).status_code == 409
    summary = api.get(f"{API}/recruitment/summary", headers=admin).json()
    assert summary["by_status"]["ONBOARDED"] == 1 and summary["acceptance_rate"] == 100.0

    other = api.post(base, headers=admin, json={"full_name": "Andres B."}).json()
    assert api.post(f"{base}/{other['id']}/stage", headers=admin, json={"status": "REJECTED"}).status_code == 422
    rejected = api.post(f"{base}/{other['id']}/stage", headers=admin,
                        json={"status": "REJECTED", "note": "No license yet"})
    assert rejected.json()["status"] == "REJECTED"
    assert api.post(f"{base}/{other['id']}/stage", headers=admin, json={"status": "SCREENING"}).status_code == 409


# ---- assessments ----------------------------------------------------------------------------

def test_assessments_use_recorded_figures(api, admin, agents, db):
    for months_ago in (1, 2):
        _deal(db, agents[0], 5_000_000, months_ago)
        _deal(db, agents[1], 1_000_000, months_ago)
    db.commit()
    start, end = date.today() - timedelta(days=100), date.today()
    path = f"{API}/agents/{agents[0]}"
    draft = api.get(f"{path}/assessment-draft?start={start}&end={end}", headers=admin).json()
    assert draft["kpis"]["completed_sales"] == 2 and draft["kpis"]["sales_value"] == 10_000_000
    assert draft["suggested"]["sales_performance"] >= 4 and draft["suggested"]["client_satisfaction"] is None

    scores = {"sales_performance": 5, "client_satisfaction": 4, "documentation_compliance": 5,
              "product_knowledge": 4, "teamwork": 5}
    assert api.post(f"{path}/assessments", headers=admin, json={
        "period_start": str(start), "period_end": str(end), "scores": {**scores, "teamwork": 9}}).status_code == 422
    assert api.post(f"{path}/assessments", headers=admin, json={
        "period_start": str(start), "period_end": str(end), "scores": {"teamwork": 5}}).status_code == 422
    saved = api.post(f"{path}/assessments", headers=admin, json={
        "period_start": str(start), "period_end": str(end), "scores": scores, "remarks": "Strong quarter"})
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["overall"] == 4.6 and body["rating"] == "Outstanding"
    assert body["recommendation"] == "Consider for promotion" and body["kpis"]["completed_sales"] == 2
    listed = api.get(f"{path}/assessments", headers=admin).json()
    assert [a["id"] for a in listed] == [body["id"]]
    assert api.delete(f"{path}/assessments/{body['id']}", headers=admin).status_code == 204
    assert workforce_planning.rating_for(2.4) == "Needs improvement"


def test_commission_rate_defaults():
    assert analytics.METRICS == {"revenue", "transactions", "sales", "commission"}
