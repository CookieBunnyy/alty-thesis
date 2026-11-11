"""Management reports on the two activities Abellar's management monitors
(interview): SALES and RECRUITMENT. Every figure comes from recorded data:
completed sales (transactions), recorded commissions, and recruitment
records (agent_applicants)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.branch import Branch
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.workforce import AgentApplicant
from app.services import commissions

PERIODS = ("day", "month", "quarter", "year")
NO_TEAM = "No team"


def _bucket(day: date, period: str) -> str:
    if period == "quarter":
        return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}"
    return day.isoformat() if period == "day" else f"{day.year:04d}-{day.month:02d}" if period == "month" \
        else f"{day.year:04d}"


def quarter_start(day: date) -> date:
    return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)


def _day(value) -> date:
    if isinstance(value, datetime):
        return (value.astimezone(timezone.utc) if value.tzinfo else value).date()
    return value


def _rank(groups: dict, key: str) -> list[dict]:
    return sorted(groups.values(), key=lambda g: (-g[key], str(g.get("name") or "")))


def sales_report(db: Session, start: date, end: date, period: str = "month", agent_id: str | None = None,
                 team_id: int | None = None, project: str | None = None, listing_id: int | None = None) -> dict:
    agents = {a.agent_id: a for a in db.execute(select(Agent)).scalars()}
    teams = dict(db.execute(select(Branch.id, Branch.name)).all())
    partners = dict(db.execute(select(Partner.id, Partner.name)).all())
    rows = db.execute(select(PropertyTransaction, PropertyListing)
                      .join(PropertyListing, PropertyListing.listing_id == PropertyTransaction.property_id)
                      .where(PropertyTransaction.transaction_type == "SOLD", PropertyTransaction.status == "COMPLETED")
                      ).all()
    commission_by_tx: dict[str, float] = defaultdict(float)
    for row in commissions.counted(db):
        if row["record"].transaction_id:
            commission_by_tx[str(row["record"].transaction_id)] += row["amount"]

    sales, by_period, by_seller, by_project, by_team = [], {}, {}, {}, {}
    for tx, listing in rows:
        day = _day(tx.transaction_date)
        if not start <= day <= end:
            continue
        agent = agents.get(tx.agent_id)
        team = agent.branch_id if agent and agent.branch_id else listing.branch_id
        project_name = listing.project_name or listing.title or f"#{listing.listing_id}"
        if agent_id and tx.agent_id != agent_id:
            continue
        if team_id is not None and (team or 0) != team_id:
            continue
        if listing_id and listing.listing_id != listing_id:
            continue
        if project and project.casefold() not in project_name.casefold():
            continue
        amount = float(tx.amount or 0)
        commission = commission_by_tx.get(str(tx.transaction_id), 0.0)
        sales.append({"transaction_id": str(tx.transaction_id), "date": day, "buyer": tx.client.full_name if tx.client else None,
                      "property": listing.title, "project": listing.project_name,
                      "developer": partners.get(listing.partner_id), "seller": agent.full_name if agent else None,
                      "agent_id": tx.agent_id, "team": teams.get(team) if team else None, "amount": amount,
                      "commission": round(commission, 2)})
        for groups, key, name, extra in (
            (by_period, _bucket(day, period), _bucket(day, period), {}),
            (by_seller, tx.agent_id or "-", agent.full_name if agent else "—", {"agent_id": tx.agent_id,
                                                                               "team": teams.get(team) if team else None}),
            (by_project, project_name, project_name, {"developer": partners.get(listing.partner_id)}),
            (by_team, team or 0, teams.get(team, NO_TEAM) if team else NO_TEAM, {"team_id": team or 0}),
        ):
            group = groups.setdefault(key, {"name": name, "sales": 0, "revenue": 0.0, "commission": 0.0, **extra})
            group["sales"] += 1
            group["revenue"] += amount
            group["commission"] += commission
    for groups in (by_period, by_seller, by_project, by_team):
        for group in groups.values():
            group["revenue"], group["commission"] = round(group["revenue"], 2), round(group["commission"], 2)
    total = sum(s["amount"] for s in sales)
    return {
        "start": start, "end": end, "period": period,
        "totals": {"sales": len(sales), "revenue": round(total, 2),
                   "commission": round(sum(s["commission"] for s in sales), 2),
                   "average_sale": round(total / len(sales), 2) if sales else None},
        "by_period": [{"period": k, **v} for k, v in sorted(by_period.items())],
        "top_sellers": _rank(by_seller, "revenue"),
        "by_project": _rank(by_project, "revenue"),
        "by_team": _rank(by_team, "revenue"),
        "sales": sorted(sales, key=lambda s: s["date"], reverse=True),
    }


def _onboarded_on(applicant: AgentApplicant) -> date | None:
    for event in reversed(applicant.history or []):
        if event.get("status") == "ONBOARDED":
            try:
                return datetime.fromisoformat(event["at"]).date()
            except (KeyError, ValueError):
                break
    return _day(applicant.updated_at) if applicant.status == "ONBOARDED" else None


def recruitment_report(db: Session, start: date, end: date, period: str = "month", recruiter: str | None = None,
                       team_id: int | None = None) -> dict:
    """Applications received and sellers recruited (onboarded) in the period."""
    agents = dict(db.execute(select(Agent.agent_id, Agent.full_name)).all())
    teams = dict(db.execute(select(Branch.id, Branch.name)).all())
    applications, by_period, by_recruiter, by_team = [], {}, {}, {}
    status_counts: dict[str, int] = defaultdict(int)
    for applicant in db.execute(select(AgentApplicant)).scalars():
        name = applicant.recruiter_name or agents.get(applicant.recruiter_agent_id) or "Not recorded"
        rec_key = applicant.recruiter_agent_id or f"name:{name.casefold()}"
        if recruiter and recruiter not in {applicant.recruiter_agent_id, name}:
            continue
        if team_id is not None and (applicant.branch_id or 0) != team_id:
            continue
        applied = _day(applicant.created_at)
        onboarded = _onboarded_on(applicant)
        applied_in = start <= applied <= end
        onboarded_in = onboarded is not None and start <= onboarded <= end
        if not (applied_in or onboarded_in):
            continue
        if applied_in:
            status_counts[applicant.status] += 1
        applications.append({"id": applicant.id, "full_name": applicant.full_name, "status": applicant.status,
                             "applied_on": applied, "onboarded_on": onboarded, "recruiter": name,
                             "team": teams.get(applicant.branch_id), "agent_id": applicant.agent_id})
        team_name = teams.get(applicant.branch_id, NO_TEAM) if applicant.branch_id else NO_TEAM
        for groups, key, label, extra in (
            (by_recruiter, rec_key, name, {"recruiter_agent_id": applicant.recruiter_agent_id}),
            (by_team, applicant.branch_id or 0, team_name, {"team_id": applicant.branch_id or 0}),
        ):
            group = groups.setdefault(key, {"name": label, "applications": 0, "recruited": 0, **extra})
            group["applications"] += int(applied_in)
            group["recruited"] += int(onboarded_in)
        if applied_in:
            by_period.setdefault(_bucket(applied, period), {"applications": 0, "recruited": 0})["applications"] += 1
        if onboarded_in:
            by_period.setdefault(_bucket(onboarded, period), {"applications": 0, "recruited": 0})["recruited"] += 1
    return {
        "start": start, "end": end, "period": period,
        "totals": {"applications": sum(1 for a in applications if start <= a["applied_on"] <= end),
                   "recruited": sum(1 for a in applications if a["onboarded_on"] and start <= a["onboarded_on"] <= end)},
        "by_status": dict(status_counts),
        "by_period": [{"period": k, **v} for k, v in sorted(by_period.items())],
        "top_recruiters": sorted(by_recruiter.values(), key=lambda g: (-g["recruited"], -g["applications"], g["name"])),
        "by_team": sorted(by_team.values(), key=lambda g: (-g["recruited"], -g["applications"], g["name"])),
        "applications": sorted(applications, key=lambda a: a["applied_on"], reverse=True),
    }


def dashboard(db: Session, include_recruitment: bool) -> dict:
    """The management dashboard: sales and recruitment this year, with trends."""
    today = date.today()
    year_start = date(today.year, 1, 1)
    trend_start = date(today.year - 1, today.month, 1) + timedelta(days=31)
    trend_start = date(trend_start.year, trend_start.month, 1)
    sales_year = sales_report(db, year_start, today)
    sales_trend = sales_report(db, trend_start, today, "month")
    body = {
        "year": today.year,
        # Top sellers by sales amount, this month and this quarter (second interview).
        "sales": {"totals": sales_year["totals"], "top_sellers": sales_year["top_sellers"][:5],
                  "top_sellers_month": sales_report(db, date(today.year, today.month, 1), today)["top_sellers"][:5],
                  "top_sellers_quarter": sales_report(db, quarter_start(today), today)["top_sellers"][:5],
                  "by_team": sales_year["by_team"], "trend": sales_trend["by_period"]},
    }
    if include_recruitment:
        rec_year = recruitment_report(db, year_start, today)
        rec_trend = recruitment_report(db, trend_start, today, "month")
        body["recruitment"] = {"totals": rec_year["totals"], "top_recruiters": rec_year["top_recruiters"][:5],
                               "by_team": rec_year["by_team"], "trend": rec_trend["by_period"]}
    return body
