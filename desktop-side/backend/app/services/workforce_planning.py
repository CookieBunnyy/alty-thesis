"""Branch performance, workforce demand vs capacity, and agent assessments.

Everything is computed from recorded transactions, agents, listings and
reviews at request time, with the inputs returned so the pages can show how
each figure was reached. Recommendations are rules, stated with the rule.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import Agent
from app.models.branch import Branch
from app.models.property_listing import PropertyListing
from app.models.review import AgentReview
from app.models.transaction import PropertyTransaction
from app.services import analytics
from app.services.analytics import LIVE, SALE

UNASSIGNED = 0          # "branch" id used for records without a branch
CAPACITY_PERCENTILE = 75
TREND_MONTHS = 6


def _active(status: str | None) -> bool:
    return str(status or "").upper() == "ACTIVE"


def _complete_months(series: list[dict]) -> list[dict]:
    current = analytics._month_key(analytics._now())
    return [row for row in series if row["month"] != current]


def _branches(db: Session, include_inactive: bool = True) -> list[Branch]:
    statement = select(Branch).order_by(Branch.name)
    if not include_inactive:
        statement = statement.where(Branch.is_active.is_(True))
    return list(db.execute(statement).scalars())


def _agents_by_branch(db: Session) -> dict[int, list[Agent]]:
    groups: dict[int, list[Agent]] = {}
    for agent in db.execute(select(Agent)).scalars():
        groups.setdefault(agent.branch_id or UNASSIGNED, []).append(agent)
    return groups


# ------------------------------------------------------------------ branch comparison

def _branch_figures(db: Session, branch_id: int) -> dict:
    """Recorded figures and trend for one branch (0 = no branch)."""
    series = _complete_months(analytics.monthly_series(db, branch_id=branch_id))
    current_row = next((row for row in analytics.monthly_series(db, 1, branch_id=branch_id)), None)
    last = series[-1] if series else None
    previous = series[-2] if len(series) > 1 else None
    recent = series[-TREND_MONTHS:]
    revenue = [row["revenue"] for row in recent]
    trend = analytics._trend(revenue) if len(revenue) >= 3 else None
    mean = float(np.mean(revenue)) if revenue else 0.0
    forecast = analytics.forecast(db, "revenue", 1, branch_id=branch_id, seasonal=False)
    point = forecast["forecast"][0] if forecast["status"] == "estimated" else None
    total = lambda key: sum(row[key] for row in series)  # noqa: E731
    deals = total("transactions")
    return {
        "months": [{"month": row["month"], "revenue": row["revenue"], "sales": row["sales"],
                    "transactions": row["transactions"], "commission": row["commission"]} for row in recent],
        "this_month": current_row,
        "last_month": last,
        "previous_month": previous,
        "change_pct": analytics._pct_change(last["revenue"], previous["revenue"]) if last and previous else None,
        "trend_per_month": round(trend["slope"], 2) if trend else None,
        "trend_pct": round(trend["slope"] / mean * 100, 1) if trend and mean else None,
        "forecast_next": point and {"month": point["month"], "value": point["value"],
                                    "lower": point["lower"], "upper": point["upper"]},
        "forecast_status": forecast["status"],
        "totals": {"transactions": deals, "sales": total("sales"), "revenue": round(total("revenue"), 2),
                   "commission": round(total("commission"), 2),
                   "conversion": round(total("sales") / deals * 100, 1) if deals else None},
    }


def branch_comparison(db: Session) -> dict:
    """Every branch side by side, plus "No branch" when records lack one."""
    agents = _agents_by_branch(db)
    listings = {(branch_id or UNASSIGNED): int(count) for branch_id, count in db.execute(
        select(PropertyListing.branch_id, func.count())
        .where(PropertyListing.status == "AVAILABLE").group_by(PropertyListing.branch_id)).all()}
    rows = []
    for branch in _branches(db):
        members = agents.get(branch.id, [])
        rows.append({"branch_id": branch.id, "name": branch.name, "code": branch.code, "is_active": branch.is_active,
                     "address": branch.address, "agents": len(members),
                     "active_agents": sum(1 for a in members if _active(a.status)),
                     "available_listings": int(listings.get(branch.id, 0)), **_branch_figures(db, branch.id)})
    unassigned = _branch_figures(db, UNASSIGNED)
    if unassigned["totals"]["transactions"] or agents.get(UNASSIGNED) or listings.get(UNASSIGNED):
        members = agents.get(UNASSIGNED, [])
        rows.append({"branch_id": UNASSIGNED, "name": "No branch", "code": None, "is_active": True, "address": None,
                     "agents": len(members), "active_agents": sum(1 for a in members if _active(a.status)),
                     "available_listings": int(listings.get(UNASSIGNED, 0)), **unassigned})
    company = sum(row["totals"]["revenue"] for row in rows)
    for row in rows:
        row["revenue_share"] = round(row["totals"]["revenue"] / company * 100, 1) if company else None
    ranked = sorted((r for r in rows if r["branch_id"] != UNASSIGNED and r["last_month"]),
                    key=lambda r: -r["last_month"]["revenue"])
    return {"branches": rows,
            "best_last_month": ranked[0]["name"] if ranked and ranked[0]["last_month"]["revenue"] > 0 else None,
            "trend_months": TREND_MONTHS}


# ------------------------------------------------------------------ demand vs capacity

def observed_capacity(db: Session) -> dict:
    """How many deals one agent handles in a busy month: the 75th percentile
    of agent-months with any deal over the last 12 complete months."""
    month = func.to_char(func.timezone("UTC", PropertyTransaction.transaction_date), "YYYY-MM")
    current = analytics._month_key(analytics._now())
    start = analytics._shift_month(current, -12)
    counts = [int(n) for (n,) in db.execute(
        select(func.count()).where(LIVE, month >= start, month < current)
        .group_by(PropertyTransaction.agent_id, month)).all()]
    if not counts:
        return {"value": 1.0, "agent_months": 0, "basis": "default"}
    value = max(1.0, float(np.percentile(counts, CAPACITY_PERCENTILE)))
    return {"value": round(value, 1), "agent_months": len(counts), "basis": "observed",
            "median": float(np.median(counts)), "busiest": max(counts)}


def _expected_demand(db: Session, branch_id: int | None) -> dict:
    """Deals expected next month: the forecast when there is enough history,
    else the average of the last 3 complete months."""
    result = analytics.forecast(db, "transactions", 1, branch_id=branch_id, seasonal=branch_id is None)
    if result["status"] == "estimated":
        point = result["forecast"][0]
        return {"month": point["month"], "value": point["value"], "high": point["upper"], "method": "forecast"}
    series = _complete_months(analytics.monthly_series(db, branch_id=branch_id))[-3:]
    value = float(np.mean([row["transactions"] for row in series])) if series else 0.0
    return {"month": analytics._shift_month(analytics._month_key(analytics._now()), 0), "value": round(value, 2),
            "high": round(value, 2), "method": "recent_average"}


def capacity_plan(db: Session, capacity: float | None = None) -> dict:
    """Agents needed next month against active agents, per branch and overall,
    with rule-based recommendations to reallocate or recruit."""
    observed = observed_capacity(db)
    per_agent = float(capacity) if capacity else observed["value"]
    agents = _agents_by_branch(db)
    open_reservations = dict(db.execute(
        select(PropertyTransaction.agent_id, func.count())
        .where(PropertyTransaction.transaction_type == "RESERVED", PropertyTransaction.status == "RESERVED")
        .group_by(PropertyTransaction.agent_id)).all())

    def plan_row(branch_id: int | None, name: str, members: list[Agent]) -> dict:
        demand = _expected_demand(db, branch_id)
        active = sum(1 for a in members if _active(a.status))
        needed = math.ceil(demand["value"] / per_agent) if demand["value"] > 0 else 0
        needed_high = math.ceil(demand["high"] / per_agent) if demand["high"] > 0 else 0
        utilization = demand["value"] / (active * per_agent) * 100 if active else None
        return {"branch_id": branch_id, "name": name, "active_agents": active, "demand": demand,
                "agents_needed": needed, "agents_needed_high": needed_high, "gap": needed - active,
                "utilization": round(utilization, 1) if utilization is not None else None,
                "status": ("SHORT" if needed > active else "OVER" if active - needed >= 2 and active > 1
                           else "BALANCED")}

    rows = [plan_row(b.id, b.name, agents.get(b.id, [])) for b in _branches(db, include_inactive=False)]
    if agents.get(UNASSIGNED) and rows:
        rows.append(plan_row(UNASSIGNED, "No branch", agents.get(UNASSIGNED, [])))
    company = plan_row(None, "Whole company", [a for group in agents.values() for a in group])

    recommendations: list[dict] = []
    short = sorted((r for r in rows if r["gap"] > 0 and r["branch_id"] != UNASSIGNED), key=lambda r: -r["gap"])
    spare = {r["branch_id"]: max(0, r["active_agents"] - max(r["agents_needed_high"], 1))
             for r in rows if r["branch_id"] != UNASSIGNED}
    unassigned_active = next((r["active_agents"] for r in rows if r["branch_id"] == UNASSIGNED), 0)
    for row in short:
        missing = row["gap"]
        if unassigned_active and missing:
            moved = min(unassigned_active, missing)
            unassigned_active -= moved
            missing -= moved
            recommendations.append({"kind": "ASSIGN", "to_branch": row["name"], "agents": moved,
                                    "detail": f"Assign {moved} agent(s) without a branch to {row['name']}.",
                                    "rule": "a branch needs more agents and some active agents have no branch"})
        for donor in sorted((r for r in rows if spare.get(r["branch_id"], 0) > 0), key=lambda r: -spare[r["branch_id"]]):
            if not missing:
                break
            moved = min(spare[donor["branch_id"]], missing)
            spare[donor["branch_id"]] -= moved
            missing -= moved
            recommendations.append({"kind": "REALLOCATE", "from_branch": donor["name"], "to_branch": row["name"],
                                    "agents": moved,
                                    "detail": f"Move {moved} agent(s) from {donor['name']} to {row['name']}.",
                                    "rule": "the giving branch keeps enough agents for its busiest expected month"})
        if missing:
            recommendations.append({"kind": "RECRUIT", "to_branch": row["name"], "agents": missing,
                                    "detail": f"Recruit {missing} agent(s) for {row['name']}.",
                                    "rule": "expected deals ÷ deals per agent is more than the agents available "
                                            "after reallocation"})
    if not rows and company["gap"] > 0:
        recommendations.append({"kind": "RECRUIT", "to_branch": None, "agents": company["gap"],
                                "detail": f"Recruit {company['gap']} agent(s).",
                                "rule": "expected deals ÷ deals per agent is more than the active agents"})
    if company["utilization"] is not None and company["utilization"] < 50 and company["active_agents"] > 1:
        recommendations.append({"kind": "LEADS", "agents": 0,
                                "detail": "Agents have more capacity than the expected deals: focus on lead "
                                          "generation and marketing before hiring.",
                                "rule": "company utilization below 50%"})

    overloaded = []
    for group in agents.values():
        for agent in group:
            load = int(open_reservations.get(agent.agent_id, 0))
            if _active(agent.status) and load > per_agent:
                overloaded.append({"agent_id": agent.agent_id, "full_name": agent.full_name,
                                   "branch": agent.branch_name, "open_reservations": load})
    if overloaded:
        recommendations.append({"kind": "REBALANCE", "agents": len(overloaded),
                                "detail": "Give new clients to other agents until these agents' open reservations "
                                          "go down: " + ", ".join(o["full_name"] for o in overloaded) + ".",
                                "rule": "open reservations above the deals one agent handles in a busy month"})
    return {"capacity": {"per_agent": round(per_agent, 1), "observed": observed,
                         "overridden": capacity is not None},
            "company": company, "branches": rows, "overloaded_agents": overloaded,
            "recommendations": recommendations}


# ------------------------------------------------------------------ assessments

RATINGS = [(4.5, "Outstanding"), (3.5, "Very satisfactory"), (2.5, "Satisfactory"), (1.5, "Needs improvement"),
           (0.0, "Poor")]
RECOMMENDATIONS = {"Outstanding": "Consider for promotion", "Very satisfactory": "Retain and recognize",
                   "Satisfactory": "Retain; set improvement goals", "Needs improvement": "Coaching plan",
                   "Poor": "Performance improvement plan"}


def rating_for(overall: float) -> str:
    return next(label for floor, label in RATINGS if overall >= floor)


def _scale(value: float, team: list[float]) -> int:
    """1-5 by where a value sits among the team (quintiles); 3 with no comparison."""
    if not team or max(team) == min(team):
        return 3
    below = sum(1 for v in team if v < value) / len(team)
    return min(5, 1 + int(below * 5))


def agent_kpis(db: Session, agent_id: str, start: date, end: date) -> dict:
    """Recorded figures for one agent over a period."""
    period = (func.date(func.timezone("UTC", PropertyTransaction.transaction_date)) >= start) & \
             (func.date(func.timezone("UTC", PropertyTransaction.transaction_date)) <= end)
    rows = db.execute(select(PropertyTransaction.transaction_type, PropertyTransaction.status,
                             PropertyTransaction.amount)
                      .where(PropertyTransaction.agent_id == agent_id, period)).all()
    sales = [float(a or 0) for t, s, a in rows if t == "SOLD" and s == "COMPLETED"]
    deals = [r for r in rows if r[1] != "CANCELLED"]
    cancelled = sum(1 for r in rows if r[1] == "CANCELLED")
    rate = analytics.commission_rates(db).get(agent_id, settings.DEFAULT_COMMISSION_RATE)
    rating, reviews = db.execute(select(func.avg(AgentReview.rating), func.count())
                                 .where(AgentReview.agent_id == agent_id)).one()
    return {"deals": len(deals), "completed_sales": len(sales), "sales_value": round(sum(sales), 2),
            "commission": round(sum(sales) * rate, 2), "cancellations": cancelled,
            "conversion": round(len(sales) / len(deals) * 100, 1) if deals else None,
            "client_rating": round(float(rating), 2) if rating is not None else None, "reviews": int(reviews or 0)}


def assessment_draft(db: Session, agent: Agent, start: date, end: date) -> dict:
    """Suggested scores from recorded figures (sales against the team, client
    ratings); the criteria only people can judge are left for the assessor."""
    kpis = agent_kpis(db, agent.agent_id, start, end)
    team = [agent_kpis(db, a.agent_id, start, end) for a in db.execute(
        select(Agent).where(func.upper(Agent.status) == "ACTIVE")).scalars()]
    sales_score = _scale(kpis["sales_value"], [k["sales_value"] for k in team]) if kpis["deals"] or any(
        k["sales_value"] for k in team) else 3
    if kpis["client_rating"] is None:
        satisfaction = None
    else:
        satisfaction = max(1, min(5, round(kpis["client_rating"])))
    return {"period_start": start, "period_end": end, "kpis": kpis,
            "team_size": len(team),
            "suggested": {"sales_performance": sales_score, "client_satisfaction": satisfaction},
            "basis": {"sales_performance": "Sales value compared with the other active agents in the same period "
                                           "(top fifth = 5, bottom fifth = 1).",
                      "client_satisfaction": "Average client review rating, rounded."
                      if satisfaction is not None else "No client reviews yet: score it from your own observation."}}


def agent_commission(db: Session, agent_id: str, months: int = 12) -> dict:
    series = analytics.monthly_series(db, months, agent_id=agent_id)
    rate = analytics.commission_rates(db).get(agent_id, settings.DEFAULT_COMMISSION_RATE)
    return {"rate": rate, "months": [{"month": r["month"], "sales": r["sales"], "revenue": r["revenue"],
                                      "commission": r["commission"]} for r in series],
            "total": round(sum(r["commission"] for r in series), 2)}
