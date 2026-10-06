"""ALTY Intelligence: the decision-support reasoning layer.

Turns stored records and the analytics/forecast results into contextual
insights that are shown where the decision is made — on the Analytics and
Forecasting pages, on a property, on an agent — and collected in one feed.

Every insight is evidence-based and explainable:

* ``finding``        what the data shows (numbers included);
* ``recommendation`` an optional suggestion phrased for management to
                     consider — ALTY never makes the decision;
* ``factors``        the supporting evidence;
* ``rule``           the exact condition that produced it;
* ``severity``       high | medium | positive | info (sort order of the feed).

Rules only fire when there is enough data; otherwise an ``info`` insight
says what is missing instead of guessing. Signals ALTY does not record
(website views, inquiries, listing dates) are never assumed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services import analytics
from app.services import reviews as review_service

SEVERITY_ORDER = {"high": 0, "medium": 1, "positive": 2, "info": 3}
MIN_COMPARABLES = 3          # listings in the same category to compare prices
PRICE_GAP = 0.25             # ±25% from the category median
MIN_AGENT_TRANSACTIONS = 3   # recorded transactions before judging conversion
CONVERSION_GAP = 0.15        # 15 percentage points from the agent average
STALE_RESERVATION_DAYS = 60
SHARE_LEADER = 0.40          # one group holds ≥40% of activity
MIN_ACTIVITY = 5             # transactions before comparing groups


# Stored categories are free text ("condo", "house"); insights use the same
# standard names as the website and desktop (lib/categories.ts).
_CATEGORY_NAMES = {
    "condo": "Condominium", "condominium": "Condominium", "studio": "Condominium", "loft": "Condominium",
    "house": "House and Lot", "house and lot": "House and Lot", "house & lot": "House and Lot",
    "townhouse": "Townhouse", "duplex": "Duplex", "apartment": "Apartment", "lot": "Lot Only",
    "lot only": "Lot Only", "commercial": "Commercial", "warehouse": "Warehouse / Industrial",
}


def category_label(value: str | None) -> str:
    text = " ".join(str(value or "").split())
    return _CATEGORY_NAMES.get(text.casefold(), text or "Uncategorized")


def _insight(key: str, scope: str, severity: str, title: str, finding: str, *, rule: str,
             recommendation: str | None = None, factors: list[str] | None = None,
             subject: dict | None = None, data: dict | None = None) -> dict:
    return {"id": key, "scope": scope, "severity": severity, "title": title, "finding": finding,
            "recommendation": recommendation, "factors": factors or [], "rule": rule,
            "subject": subject, "data": data or {}}


def _sort(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: SEVERITY_ORDER.get(item["severity"], 9))


def _peso(value: float) -> str:
    return f"₱{value:,.0f}"


def _now() -> datetime:
    return datetime.utcnow()


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


# ---------------------------------------------------------------- breakdowns

def breakdown(db: Session) -> dict:
    """Activity grouped by property category, by the handling agent's base
    location, and per property. Listings have no city field, so "area" is the
    agent's recorded base location (stated in the response)."""
    rows = db.execute(
        select(PropertyTransaction, PropertyListing, Agent)
        .join(PropertyListing, PropertyListing.listing_id == PropertyTransaction.property_id)
        .outerjoin(Agent, Agent.agent_id == PropertyTransaction.agent_id)
    ).all()
    listings = db.execute(select(PropertyListing)).scalars().all()

    def bucket() -> dict:
        return {"transactions": 0, "reservations": 0, "sales": 0, "cancelled": 0, "revenue": 0.0}

    by_category: dict[str, dict] = defaultdict(lambda: {**bucket(), "listings": 0, "available": 0})
    by_area: dict[str, dict] = defaultdict(bucket)
    by_property: dict[int, dict] = {}
    for listing in listings:
        group = by_category[category_label(listing.category)]
        group["listings"] += 1
        group["available"] += int(listing.status == "AVAILABLE")
        by_property[listing.listing_id] = {
            "listing_id": listing.listing_id, "title": listing.title, "category": listing.category,
            "status": listing.status, "price_total": float(listing.price_total) if listing.price_total else None,
            **bucket(),
        }
    for transaction, listing, agent in rows:
        targets = [by_category[category_label(listing.category)],
                   by_area[(agent.agent_location if agent and agent.agent_location else "Unknown location")],
                   by_property[listing.listing_id]]
        sale = transaction.transaction_type == "SOLD" and transaction.status == "COMPLETED"
        for group in targets:
            if transaction.status == "CANCELLED":
                group["cancelled"] += 1
                continue
            group["transactions"] += 1
            group["reservations"] += int(transaction.transaction_type == "RESERVED")
            group["sales"] += int(sale)
            group["revenue"] += float(transaction.amount) if sale else 0.0

    def ordered(groups: dict) -> list[dict]:
        return sorted(({"name": name, **values} for name, values in groups.items()),
                      key=lambda g: (-g["revenue"], -g["transactions"], g["name"]))

    return {
        "by_category": ordered(by_category),
        "by_area": ordered(by_area),
        "area_basis": "Base location of the agent who handled each transaction (listings have no city field).",
        "properties": sorted(by_property.values(), key=lambda p: (-p["transactions"], p["listing_id"])),
    }


# ------------------------------------------------------------- market / analytics

def market_insights(db: Session, data: dict | None = None) -> list[dict]:
    data = data or breakdown(db)
    items: list[dict] = []
    series = [row for row in analytics.monthly_series(db) if row["month"] != analytics._month_key(analytics._now())]

    # Trend: last 3 complete months vs the 3 before.
    if len(series) >= 6:
        recent, previous = series[-3:], series[-6:-3]
        r_tx, p_tx = sum(r["transactions"] for r in recent), sum(r["transactions"] for r in previous)
        r_rev, p_rev = sum(r["revenue"] for r in recent), sum(r["revenue"] for r in previous)
        change = analytics._pct_change(r_tx, p_tx)
        factors = [f"Transactions: {r_tx} in the last 3 complete months vs {p_tx} in the 3 before",
                   f"Sales revenue: {_peso(r_rev)} vs {_peso(p_rev)}"]
        if change is not None and change <= -30:
            items.append(_insight("market-trend", "analytics", "high", "Transaction activity is declining",
                                  f"Transactions fell {abs(change):.1f}% compared with the previous quarter.",
                                  recommendation="Management may review lead sources, listing exposure and agent "
                                                 "follow-ups for recent inquiries.",
                                  factors=factors, rule="3-month transaction count fell by 30% or more"))
        elif change is not None and change >= 30:
            items.append(_insight("market-trend", "analytics", "positive", "Transaction activity is growing",
                                  f"Transactions rose {change:.1f}% compared with the previous quarter.",
                                  recommendation="Management may make sure available inventory and agent "
                                                 "coverage keep up with demand.",
                                  factors=factors, rule="3-month transaction count rose by 30% or more"))
        else:
            items.append(_insight("market-trend", "analytics", "info", "Transaction activity is steady",
                                  "Transactions changed by less than 30% compared with the previous quarter.",
                                  factors=factors, rule="3-month change within ±30%"))
    else:
        items.append(_insight("market-trend", "analytics", "info", "Not enough history for a trend",
                              f"{len(series)} complete month(s) of transactions are recorded; quarter-on-quarter "
                              "comparison needs 6.",
                              rule="trend needs 6 complete months"))

    # Concentration: does one category or area dominate activity?
    total = sum(group["transactions"] for group in data["by_category"])
    for dimension, label, groups in (("category", "property type", data["by_category"]),
                                     ("area", "agent base location", data["by_area"])):
        if total < MIN_ACTIVITY:
            continue
        leader = max(groups, key=lambda g: g["transactions"])
        share = leader["transactions"] / total if total else 0
        if share >= SHARE_LEADER:
            items.append(_insight(
                f"market-{dimension}-leader", "analytics", "positive",
                f"{leader['name']} leads recorded activity",
                f"{leader['name']} accounts for {_pct(share)} of recorded reservations and sales "
                f"({leader['transactions']} of {total}) by {label}.",
                recommendation=("Management may consider increasing acquisition, marketing exposure or agent "
                                f"coverage for {leader['name']}, while checking that other "
                                f"{'types' if dimension == 'category' else 'areas'} are not under-served."),
                factors=[f"{g['name']}: {g['transactions']} transactions, {g['sales']} sales, {_peso(g['revenue'])}"
                         for g in groups[:4]],
                rule=f"one {label} has ≥{int(SHARE_LEADER * 100)}% of ≥{MIN_ACTIVITY} transactions",
                data={"dimension": dimension}))
    if total < MIN_ACTIVITY:
        items.append(_insight("market-concentration", "analytics", "info", "Too few transactions to compare segments",
                              f"{total} transaction(s) recorded; comparisons by type and area start at {MIN_ACTIVITY}.",
                              rule=f"segment comparison needs ≥{MIN_ACTIVITY} transactions"))

    # Inventory with no activity at all, per category.
    for group in data["by_category"]:
        if group["available"] >= 3 and group["transactions"] == 0:
            items.append(_insight(
                f"market-idle-{group['name']}", "analytics", "medium", f"No activity on available {group['name']} listings",
                f"{group['available']} {group['name']} listing(s) are available and none has a recorded reservation or sale.",
                recommendation="Management may review pricing and promotion for this property type.",
                rule="category with ≥3 available listings and 0 transactions"))

    # Cancellations.
    cancelled = sum(g["cancelled"] for g in data["by_category"])
    if total + cancelled >= MIN_ACTIVITY and cancelled / (total + cancelled) >= 0.2:
        items.append(_insight("market-cancellations", "analytics", "medium", "High cancellation share",
                              f"{cancelled} of {total + cancelled} recorded transactions were cancelled "
                              f"({_pct(cancelled / (total + cancelled))}).",
                              recommendation="Management may review why reservations are cancelled (financing, "
                                             "pricing, documentation) with the handling agents.",
                              rule="≥20% of transactions cancelled"))
    return _sort(items)


# --------------------------------------------------------------------- forecast

def forecast_insights(db: Session, metric: str, result: dict) -> list[dict]:
    names = {"revenue": "sales revenue", "transactions": "transactions", "sales": "completed sales"}
    name = names.get(metric, metric)
    if result["status"] != "estimated":
        return [_insight(f"forecast-{metric}", "forecast", "info", "No forecast yet",
                         f"{result.get('message') or 'Forecast unavailable.'} {result['observations']} complete month(s) "
                         f"recorded ({result['nonzero_months']} with activity); {result['minimum_required']} needed, "
                         "with activity in at least 3.",
                         recommendation="Keep recording transactions through documents; the forecast appears "
                                        "automatically once enough months exist.",
                         rule=f"forecast needs ≥{result['minimum_required']} complete months and ≥3 with activity")]

    history = [row["value"] for row in result["history"]]
    mean = sum(history) / len(history) if history else 0
    slope = result["slope_per_month"]
    relative = slope / mean if mean else 0
    r2 = result.get("r_squared")
    points = result["forecast"]
    factors = [f"Linear trend {slope:+,.0f} per month over {result['observations']} months",
               f"R² {r2:.2f}" if r2 is not None else "R² not available (no variation in history)",
               f"Next month {points[0]['value']:,.0f} (range {points[0]['lower']:,.0f}–{points[0]['upper']:,.0f})"]
    items: list[dict] = []
    if r2 is not None and r2 < 0.3:
        items.append(_insight(f"forecast-{metric}-fit", "forecast", "info", "Weak trend fit",
                              f"The trend explains only {r2 * 100:.0f}% of the month-to-month variation in {name}, "
                              "so the projection is uncertain.",
                              recommendation="Treat the forecast as a rough direction and rely on the range, not the "
                                             "single value.",
                              factors=factors, rule="R² below 0.30"))
    if relative >= 0.05:
        active_agents = int(db.scalar(select(func.count()).select_from(Agent).where(func.upper(Agent.status) == "ACTIVE")) or 0)
        available = int(db.scalar(select(func.count()).select_from(PropertyListing)
                                  .where(PropertyListing.status == "AVAILABLE")) or 0)
        items.append(_insight(f"forecast-{metric}-up", "forecast", "positive", f"{name.capitalize()} projected to increase",
                              f"The forecast indicates rising {name} over the next {len(points)} month(s).",
                              recommendation="Management may prioritise properties with strong reservation activity "
                                             "and make sure there is enough available inventory and agent coverage "
                                             "for the projected increase.",
                              factors=[*factors, f"{available} available listing(s)", f"{active_agents} active agent(s)"],
                              rule="trend slope ≥ +5% of the monthly average"))
    elif relative <= -0.05:
        items.append(_insight(f"forecast-{metric}-down", "forecast", "medium", f"{name.capitalize()} projected to decrease",
                              f"The forecast indicates falling {name} over the next {len(points)} month(s).",
                              recommendation="Management may review marketing exposure, pricing of long-available "
                                             "listings and follow-up of open reservations.",
                              factors=factors, rule="trend slope ≤ −5% of the monthly average"))
    else:
        items.append(_insight(f"forecast-{metric}-flat", "forecast", "info", f"{name.capitalize()} projected to stay level",
                              f"The forecast shows little change in {name} over the next {len(points)} month(s).",
                              factors=factors, rule="trend slope within ±5% of the monthly average"))
    return _sort(items)


# --------------------------------------------------------------------- property

def property_insights(db: Session, listing: PropertyListing) -> list[dict]:
    subject = {"type": "property", "id": listing.listing_id, "name": listing.title}
    items: list[dict] = []
    now = _now()
    transactions = db.execute(
        select(PropertyTransaction).where(PropertyTransaction.property_id == listing.listing_id)
        .order_by(PropertyTransaction.transaction_date)
    ).scalars().all()

    # Price vs comparable listings (same category).
    if listing.price_total:
        label = category_label(listing.category)
        prices = [float(p) for p, category in db.execute(
            select(PropertyListing.price_total, PropertyListing.category).where(
                PropertyListing.price_total.is_not(None), PropertyListing.listing_id != listing.listing_id)
        ).all() if category_label(category) == label]
        if len(prices) >= MIN_COMPARABLES:
            mid = median(prices)
            gap = float(listing.price_total) / mid - 1 if mid else 0
            factors = [f"This listing: {_peso(float(listing.price_total))}",
                       f"Median of {len(prices)} other {label} listings: {_peso(mid)}"]
            if gap >= PRICE_GAP and listing.status == "AVAILABLE":
                items.append(_insight(f"property-{listing.listing_id}-price-high", "property", "medium",
                                      "Priced above comparable listings",
                                      f"The price is {gap * 100:.0f}% above the median of comparable {label} listings.",
                                      recommendation="Management may review the pricing, or make sure the listing "
                                                     "explains what justifies the premium (size, amenities, location).",
                                      factors=factors, subject=subject, rule=f"≥{int(PRICE_GAP * 100)}% above category median"))
            elif gap <= -PRICE_GAP:
                items.append(_insight(f"property-{listing.listing_id}-price-low", "property", "info",
                                      "Priced below comparable listings",
                                      f"The price is {abs(gap) * 100:.0f}% below the median of comparable {label} listings.",
                                      factors=factors, subject=subject, rule=f"≥{int(PRICE_GAP * 100)}% below category median"))
        else:
            items.append(_insight(f"property-{listing.listing_id}-price-na", "property", "info",
                                  "Not enough comparable listings",
                                  f"Only {len(prices)} other {label} listing(s) have a price; "
                                  f"price comparison needs {MIN_COMPARABLES}.",
                                  subject=subject, rule=f"price comparison needs ≥{MIN_COMPARABLES} comparables"))

    # Reservation with no sale for a long time.
    open_reservations = [t for t in transactions if t.transaction_type == "RESERVED" and t.status == "RESERVED"]
    sold = any(t.transaction_type == "SOLD" and t.status == "COMPLETED" for t in transactions)
    for reservation in open_reservations:
        days = (now - reservation.transaction_date.replace(tzinfo=None)).days
        if days >= STALE_RESERVATION_DAYS and not sold:
            items.append(_insight(f"property-{listing.listing_id}-stale-{reservation.transaction_id}", "property", "medium",
                                  "Reservation without a sale",
                                  f"The reservation recorded {days} days ago has not progressed to a sale.",
                                  recommendation="Management may ask the handling agent for the status of the "
                                                 "client's payment and documents.",
                                  factors=[f"Reserved on {reservation.transaction_date:%b %d, %Y}",
                                           f"Agent {reservation.agent_id}"],
                                  subject=subject, rule=f"open reservation older than {STALE_RESERVATION_DAYS} days"))

    cancelled = sum(t.status == "CANCELLED" for t in transactions)
    if cancelled >= 2:
        items.append(_insight(f"property-{listing.listing_id}-cancelled", "property", "medium", "Repeated cancellations",
                              f"{cancelled} reservations on this property were cancelled.",
                              recommendation="Management may review the terms or any issues raised by clients.",
                              subject=subject, rule="≥2 cancelled transactions"))
    if sold:
        sale = next(t for t in transactions if t.transaction_type == "SOLD" and t.status == "COMPLETED")
        first = transactions[0]
        days = (sale.transaction_date - first.transaction_date).days
        items.append(_insight(f"property-{listing.listing_id}-sold", "property", "positive", "Sold",
                              f"Sold for {_peso(float(sale.amount))}"
                              + (f", {days} days after the first recorded transaction." if days > 0 else "."),
                              subject=subject, rule="completed sale recorded"))

    if listing.status == "AVAILABLE":
        if listing.lat is None or listing.lng is None:
            items.append(_insight(f"property-{listing.listing_id}-no-map", "property", "medium", "Not on the website map",
                                  "This available listing has no coordinates, so visitors can't find it on the map or "
                                  "see commute times.",
                                  recommendation="Add the latitude and longitude on the Properties page.",
                                  subject=subject, rule="AVAILABLE listing without coordinates"))
        if not listing.photos:
            items.append(_insight(f"property-{listing.listing_id}-no-photos", "property", "medium", "No photos",
                                  "This available listing has no photos on the website.",
                                  recommendation="Upload photos on the Digital Preview page.",
                                  subject=subject, rule="AVAILABLE listing without photos"))
        if not transactions:
            items.append(_insight(f"property-{listing.listing_id}-no-activity", "property", "info", "No recorded activity",
                                  "No reservation or sale has been recorded for this listing yet. ALTY doesn't record "
                                  "website views or inquiries, so interest before a reservation isn't visible.",
                                  subject=subject, rule="no transactions recorded"))
    return _sort(items)


# ------------------------------------------------------------------------ agent

def _conversion(agent: Agent) -> float | None:
    return agent.completed_sales / agent.transactions_count if agent.transactions_count else None


def agent_insights(db: Session, agent: Agent) -> list[dict]:
    subject = {"type": "agent", "id": agent.agent_id, "name": agent.full_name}
    items: list[dict] = []
    peers = db.execute(select(Agent).where(func.upper(Agent.status) == "ACTIVE")).scalars().all()
    rated = [(a, _conversion(a)) for a in peers if a.transactions_count >= MIN_AGENT_TRANSACTIONS]
    rated = [(a, c) for a, c in rated if c is not None]
    own = _conversion(agent)

    if own is not None and agent.transactions_count >= MIN_AGENT_TRANSACTIONS and len(rated) >= 3:
        average = sum(c for _, c in rated) / len(rated)
        factors = [f"{agent.completed_sales} completed sales of {agent.transactions_count} transactions ({_pct(own)})",
                   f"Average across {len(rated)} active agents: {_pct(average)}",
                   "From the agent records synced from the central database"]
        if own - average >= CONVERSION_GAP:
            items.append(_insight(f"agent-{agent.agent_id}-conversion-high", "agent", "positive",
                                  "Completed-sales rate above average",
                                  f"{agent.full_name}'s completed-sales rate is {(own - average) * 100:.1f} points above "
                                  "the active-agent average.",
                                  recommendation="Management may consider this agent's approach as a reference "
                                                 "for coaching other agents.",
                                  factors=factors, subject=subject, rule=f"≥{int(CONVERSION_GAP * 100)} points above average"))
        elif average - own >= CONVERSION_GAP:
            assignments_avg = sum(a.assignments_count for a in peers) / len(peers) if peers else 0
            heavy = agent.assignments_count >= assignments_avg * 1.25
            items.append(_insight(f"agent-{agent.agent_id}-conversion-low", "agent", "medium",
                                  "Completed-sales rate below average"
                                  + (" despite a high workload" if heavy else ""),
                                  f"{agent.full_name}'s completed-sales rate is {(average - own) * 100:.1f} points below "
                                  "the active-agent average"
                                  + (f", with {agent.assignments_count} assignments (average {assignments_avg:.0f})." if heavy else "."),
                                  recommendation=("Management may review workload distribution or provide additional "
                                                  "support." if heavy else
                                                  "Management may review this agent's open reservations and provide support."),
                                  factors=factors, subject=subject, rule=f"≥{int(CONVERSION_GAP * 100)} points below average"))
        else:
            items.append(_insight(f"agent-{agent.agent_id}-conversion-avg", "agent", "info",
                                  "Completed-sales rate near average",
                                  f"{agent.full_name}'s completed-sales rate ({_pct(own)}) is within "
                                  f"{int(CONVERSION_GAP * 100)} points of the active-agent average ({_pct(average)}).",
                                  factors=factors, subject=subject, rule="within the average band"))
    else:
        items.append(_insight(f"agent-{agent.agent_id}-conversion-na", "agent", "info", "Not enough data to compare",
                              f"Conversion is compared once an agent has {MIN_AGENT_TRANSACTIONS}+ recorded transactions "
                              "and at least 3 active agents qualify.",
                              subject=subject, rule="comparison needs enough transactions"))

    # Open reservations in ALTY (workload) vs the other active agents.
    loads = dict(db.execute(
        select(PropertyTransaction.agent_id, func.count()).where(
            PropertyTransaction.transaction_type == "RESERVED", PropertyTransaction.status == "RESERVED")
        .group_by(PropertyTransaction.agent_id)
    ).all())
    mine = int(loads.get(agent.agent_id, 0))
    mean = sum(int(loads.get(a.agent_id, 0)) for a in peers) / len(peers) if peers else 0
    if mine >= 3 and mine > 2 * mean:
        items.append(_insight(f"agent-{agent.agent_id}-workload", "agent", "medium", "Heavy reservation load",
                              f"{agent.full_name} holds {mine} open reservations; the active-agent average is {mean:.1f}.",
                              recommendation="Management may assign new clients to other agents for now.",
                              subject=subject, rule="≥3 open reservations and more than twice the average"))
    if str(agent.status or "").upper() != "ACTIVE" and mine:
        items.append(_insight(f"agent-{agent.agent_id}-inactive-open", "agent", "high", "Inactive agent with open reservations",
                              f"{agent.full_name} is {str(agent.status).lower()} but still has {mine} open reservation(s).",
                              recommendation="Management may reassign these clients to an active agent.",
                              subject=subject, rule="agent not ACTIVE with open reservations"))

    stats = review_service.stats_for(review_service.review_stats(db, [agent.agent_id]), agent.agent_id)
    if stats["review_count"] >= 3 and stats["client_rating"] is not None:
        if stats["client_rating"] <= 3:
            items.append(_insight(f"agent-{agent.agent_id}-rating-low", "agent", "high", "Low client rating",
                                  f"Average {stats['client_rating']:.1f}★ from {stats['review_count']} verified client reviews.",
                                  recommendation="Management may read the reviews with the agent and agree on improvements.",
                                  subject=subject, rule="≥3 reviews averaging 3★ or less"))
        elif stats["client_rating"] >= 4.5:
            items.append(_insight(f"agent-{agent.agent_id}-rating-high", "agent", "positive", "Highly rated by clients",
                                  f"Average {stats['client_rating']:.1f}★ from {stats['review_count']} verified client reviews.",
                                  subject=subject, rule="≥3 reviews averaging 4.5★ or more"))
    return _sort(items)


# ------------------------------------------------------------------ operations

def operations_insights(db: Session) -> list[dict]:
    items: list[dict] = []
    failed = dict(db.execute(select(Document.processing_stage, func.count())
                             .where(Document.status == "FAILED").group_by(Document.processing_stage)).all())
    total_failed = sum(int(v) for v in failed.values())
    if total_failed:
        items.append(_insight("ops-failed-documents", "operations", "high", "Documents failed processing",
                              f"{total_failed} document(s) failed: "
                              + ", ".join(f"{int(v)} at {str(k or 'unknown').replace('_', ' ').lower()}" for k, v in failed.items()) + ".",
                              recommendation="Open them in the Document Repository: fix the reason shown, then Reprocess.",
                              rule="documents with status FAILED"))
    pending = sum(int(db.scalar(select(func.count()).select_from(model).where(model.sync_status == "PENDING")) or 0)
                  for model in (PropertyListing, PropertyTransaction, Agent))
    if pending:
        items.append(_insight("ops-pending-sync", "operations", "medium", "Records waiting to sync",
                              f"{pending} record(s) are not yet saved to the central database.",
                              recommendation="An administrator can push them from Settings.",
                              rule="sync_status = PENDING"))
    unmapped = int(db.scalar(select(func.count()).select_from(PropertyListing).where(
        PropertyListing.status == "AVAILABLE", (PropertyListing.lat.is_(None)) | (PropertyListing.lng.is_(None)))) or 0)
    if unmapped:
        items.append(_insight("ops-unmapped", "operations", "medium", "Available listings missing from the map",
                              f"{unmapped} available listing(s) have no coordinates.",
                              recommendation="Add coordinates on the Properties page so clients can find them.",
                              rule="AVAILABLE listings without coordinates"))
    return items


# ------------------------------------------------------------------------ feed

def all_insights(db: Session) -> dict:
    """Central feed (Insights page): market, forecast, operations, and the
    property/agent insights that need attention or are positive."""
    data = breakdown(db)
    items = market_insights(db, data)
    items += forecast_insights(db, "revenue", analytics.forecast(db, "revenue"))
    items += operations_insights(db)
    for listing in db.execute(select(PropertyListing)).scalars():
        # Sold notes stay on the property itself; the feed shows what needs attention.
        items += [i for i in property_insights(db, listing) if i["severity"] in {"high", "medium"}]
    for agent in db.execute(select(Agent)).scalars():
        items += [i for i in agent_insights(db, agent) if i["severity"] in {"high", "medium", "positive"}]
    items = _sort(items)
    counts = {level: sum(i["severity"] == level for i in items) for level in SEVERITY_ORDER}
    return {"generated_at": _now().isoformat() + "Z", "counts": counts, "items": items}
