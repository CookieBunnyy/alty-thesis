"""Aggregations over real records: analytics, forecasting, DSS, workforce.

Every number returned is computed from database rows at request time. When
data is insufficient the result says so explicitly instead of estimating.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import canonical_role
from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User

INSUFFICIENT_FORECAST = "Insufficient historical data for forecasting."
INSUFFICIENT = "Insufficient data"
SALE = (PropertyTransaction.transaction_type == "SOLD") & (PropertyTransaction.status == "COMPLETED")
LIVE = PropertyTransaction.status != "CANCELLED"
PROLONGED_DAYS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_key(value: datetime) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _month_range(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    months = []
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def _shift_month(key: str, delta: int) -> str:
    year, month = map(int, key.split("-"))
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def monthly_series(db: Session, months: int | None = None, agent_id: str | None = None) -> list[dict]:
    """Per-month transaction counts and sales revenue. ``months`` limits the
    window to the last N months (including the current one). With ``agent_id``
    only that agent's transactions are counted, over the company's full
    history (months with nothing for the agent count as zero)."""
    month = func.to_char(func.timezone("UTC", PropertyTransaction.transaction_date), "YYYY-MM")
    statement = select(
        month,
        func.count(PropertyTransaction.transaction_id),
        func.coalesce(func.sum(case((PropertyTransaction.transaction_type == "RESERVED", 1), else_=0)), 0),
        func.coalesce(func.sum(case((SALE, 1), else_=0)), 0),
        func.coalesce(func.sum(case((SALE, PropertyTransaction.amount), else_=0)), 0),
    ).where(LIVE)
    if agent_id is not None:
        statement = statement.where(PropertyTransaction.agent_id == agent_id)
    rows = db.execute(statement.group_by(month)).all()
    data = {
        str(key): {"transactions": int(count), "reservations": int(reservations),
                   "sales": int(sales), "revenue": float(revenue or 0)}
        for key, count, reservations, sales, revenue in rows
    }
    current = _month_key(_now())
    first = min(data) if data else None
    if agent_id is not None and not months:
        first = db.scalar(select(func.min(month)).where(LIVE))
    if months:
        keys = _month_range(_shift_month(current, -(months - 1)), current)
    elif first:
        keys = _month_range(str(first), current)
    else:
        keys = []
    empty = {"transactions": 0, "reservations": 0, "sales": 0, "revenue": 0.0}
    series = []
    for key in keys:
        entry = {"month": key, **data.get(key, empty)}
        entry["average_sale"] = round(entry["revenue"] / entry["sales"], 2) if entry["sales"] else None
        series.append(entry)
    return series


def overview(db: Session) -> dict:
    listing_rows = db.execute(
        select(PropertyListing.status, func.count()).group_by(PropertyListing.status)
    ).all()
    statuses = {str(name): int(count) for name, count in listing_rows}
    total_listings = sum(statuses.values())
    sales_count, revenue, reservations, transactions = db.execute(
        select(
            func.coalesce(func.sum(case((SALE, 1), else_=0)), 0),
            func.coalesce(func.sum(case((SALE, PropertyTransaction.amount), else_=0)), 0),
            func.coalesce(func.sum(case((
                (PropertyTransaction.transaction_type == "RESERVED") & LIVE, 1), else_=0)), 0),
            func.count(PropertyTransaction.transaction_id),
        )
    ).one()
    revenue = float(revenue or 0)
    sold = statuses.get("SOLD", 0)

    agent_rows = db.execute(
        select(
            Agent.agent_id, Agent.full_name, Agent.status, Agent.total_commission,
            func.count(PropertyTransaction.transaction_id),
            func.coalesce(func.sum(case((SALE, 1), else_=0)), 0),
            func.coalesce(func.sum(case((SALE, PropertyTransaction.amount), else_=0)), 0),
        ).outerjoin(PropertyTransaction, (PropertyTransaction.agent_id == Agent.agent_id) & LIVE)
        .group_by(Agent.agent_id, Agent.full_name, Agent.status, Agent.total_commission)
        .order_by(func.coalesce(func.sum(case((SALE, PropertyTransaction.amount), else_=0)), 0).desc(),
                  Agent.full_name)
    ).all()

    price_rows = db.execute(
        select(PropertyListing.category, func.count(), func.avg(PropertyListing.price_total),
               func.min(PropertyListing.price_total), func.max(PropertyListing.price_total))
        .where(PropertyListing.price_total.is_not(None)).group_by(PropertyListing.category)
    ).all()
    return {
        "generated_at": _now().isoformat(),
        "properties": {"total": total_listings, "by_status": statuses},
        "transactions": {
            "total": int(transactions),
            "active_reservations": int(reservations),
            "completed_sales": int(sales_count),
            "revenue": revenue,
            "average_sale_value": round(revenue / sales_count, 2) if sales_count else None,
        },
        # Share of all listings that are sold; None when there are no listings.
        "absorption_rate": round(sold / total_listings, 4) if total_listings else None,
        "clients": int(db.scalar(select(func.count(Client.client_id))) or 0),
        "agents": [
            {"agent_id": agent_id, "full_name": name, "status": status,
             "transactions": int(count), "completed_sales": int(sales),
             "sales_value": float(value or 0),
             "recorded_total_commission": float(commission) if commission is not None else None}
            for agent_id, name, status, commission, count, sales, value in agent_rows
        ],
        "price_by_category": [
            {"category": category or "Uncategorized", "listings": int(count),
             "average_price": float(avg) if avg is not None else None,
             "min_price": float(low) if low is not None else None,
             "max_price": float(high) if high is not None else None}
            for category, count, avg, low, high in price_rows
        ],
        "monthly": monthly_series(db, 12),
    }


def forecast(db: Session, metric: str = "revenue", horizon: int = 3, agent_id: str | None = None) -> dict:
    """Linear-trend forecast over complete months, only with enough history.
    With ``agent_id``, the forecast is for that agent's own activity."""
    if metric not in {"revenue", "transactions", "sales"}:
        raise ValueError("metric must be revenue, transactions or sales")
    current = _month_key(_now())
    history = [row for row in monthly_series(db, agent_id=agent_id) if row["month"] != current]  # complete months
    values = [float(row[metric]) for row in history]
    nonzero = sum(1 for value in values if value > 0)
    base = {"metric": metric, "observations": len(values), "nonzero_months": nonzero,
            "minimum_required": settings.FORECAST_MIN_MONTHS,
            "history": [{"month": row["month"], "value": row[metric]} for row in history]}
    if len(values) < settings.FORECAST_MIN_MONTHS or nonzero < 3:
        return {**base, "status": "insufficient_data", "message": INSUFFICIENT_FORECAST,
                "forecast": []}

    from sklearn.linear_model import LinearRegression

    x = np.arange(len(values)).reshape(-1, 1)
    y = np.array(values)
    model = LinearRegression().fit(x, y)
    fitted = model.predict(x)
    residual_std = float(np.std(y - fitted, ddof=1)) if len(values) > 2 else 0.0
    r2 = float(model.score(x, y)) if np.var(y) > 0 else None
    future_x = np.arange(len(values), len(values) + horizon).reshape(-1, 1)
    predictions = model.predict(future_x)
    next_month = _shift_month(current, 0)
    points = []
    for step, value in enumerate(predictions):
        point = max(0.0, float(value))
        points.append({
            "month": _shift_month(next_month, step),
            "value": round(point, 2),
            "lower": round(max(0.0, point - 1.96 * residual_std), 2),
            "upper": round(point + 1.96 * residual_std, 2),
        })
    return {
        **base,
        "status": "estimated",
        "method": "Ordinary least-squares linear trend over complete months (scikit-learn)",
        "slope_per_month": round(float(model.coef_[0]), 2),
        "r_squared": round(r2, 4) if r2 is not None else None,
        "interval": "approximate 95% band from residual standard deviation",
        "forecast": points,
    }


def _pct_change(recent: float, previous: float) -> float | None:
    return round((recent - previous) / previous * 100, 1) if previous else None


def dss_insights(db: Session) -> dict:
    """Decision support built only from stored data. Each item states whether
    it is DATA, ANALYSIS, or a SYSTEM-GENERATED RECOMMENDATION with its rule."""
    items: list[dict] = []
    now = _now().replace(tzinfo=None)
    summary = overview(db)
    statuses = summary["properties"]["by_status"]

    items.append({"kind": "DATA", "title": "Inventory by status",
                  "detail": ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())) or INSUFFICIENT,
                  "evidence": statuses})

    # Prolonged availability (needs a known listing/status date).
    available = db.execute(
        select(PropertyListing).where(PropertyListing.status == "AVAILABLE")
    ).scalars().all()
    aged, unknown = [], 0
    for listing in available:
        since = listing.status_changed_at or listing.created_at
        if since is None:
            unknown += 1
        elif (now - since).days >= PROLONGED_DAYS:
            aged.append({"listing_id": listing.listing_id, "title": listing.title,
                         "days_available": (now - since).days})
    items.append({
        "kind": "ANALYSIS", "title": f"Listings available ≥ {PROLONGED_DAYS} days",
        "detail": (f"{len(aged)} listing(s) available for {PROLONGED_DAYS}+ days; "
                   f"{unknown} available listing(s) have no recorded listing date")
        if available else INSUFFICIENT,
        "evidence": {"listings": aged, "unknown_age": unknown},
    })

    # Trend: last 3 complete months vs the 3 before.
    series = [row for row in monthly_series(db) if row["month"] != _month_key(_now())]
    if len(series) >= 6:
        recent, previous = series[-3:], series[-6:-3]
        recent_tx, previous_tx = sum(r["transactions"] for r in recent), sum(r["transactions"] for r in previous)
        recent_rev, previous_rev = sum(r["revenue"] for r in recent), sum(r["revenue"] for r in previous)
        tx_change, rev_change = _pct_change(recent_tx, previous_tx), _pct_change(recent_rev, previous_rev)
        items.append({"kind": "ANALYSIS", "title": "Transaction trend (3 vs previous 3 months)",
                      "detail": f"{recent_tx} vs {previous_tx} transactions"
                                + (f" ({tx_change:+.1f}%)" if tx_change is not None else ""),
                      "evidence": {"recent": recent, "previous": previous, "change_pct": tx_change}})
        items.append({"kind": "ANALYSIS", "title": "Revenue change (3 vs previous 3 months)",
                      "detail": f"₱{recent_rev:,.2f} vs ₱{previous_rev:,.2f}"
                                + (f" ({rev_change:+.1f}%)" if rev_change is not None else ""),
                      "evidence": {"change_pct": rev_change}})
        if tx_change is not None and tx_change <= -30:
            items.append({"kind": "RECOMMENDATION", "title": "Review the decline in transactions",
                          "detail": f"Transactions fell {abs(tx_change):.1f}% versus the prior quarter; "
                                    "review lead sources and listing exposure.",
                          "rule": "3-month transaction count fell by 30% or more"})
        counts = [r["transactions"] for r in series[:-1]]
        if len(counts) >= 5 and np.std(counts) > 0:
            mean, std = float(np.mean(counts)), float(np.std(counts))
            latest = series[-1]
            if abs(latest["transactions"] - mean) > 2 * std:
                items.append({"kind": "ANALYSIS", "title": "Unusual activity",
                              "detail": f"{latest['month']}: {latest['transactions']} transactions vs "
                                        f"typical {mean:.1f} ± {std:.1f}",
                              "evidence": {"month": latest["month"], "mean": mean, "std": std}})
    else:
        items.append({"kind": "ANALYSIS", "title": "Transaction and revenue trend",
                      "detail": f"{INSUFFICIENT}: {len(series)} complete month(s) recorded; 6 required",
                      "evidence": {"complete_months": len(series)}})

    # Agent workload: live reservations per active agent.
    workload = db.execute(
        select(Agent.agent_id, Agent.full_name,
               func.coalesce(func.sum(case((
                   (PropertyTransaction.transaction_type == "RESERVED")
                   & (PropertyTransaction.status == "RESERVED"), 1), else_=0)), 0))
        .outerjoin(PropertyTransaction, PropertyTransaction.agent_id == Agent.agent_id)
        .where(func.upper(Agent.status) == "ACTIVE")
        .group_by(Agent.agent_id, Agent.full_name)
    ).all()
    loads = [{"agent_id": a, "full_name": n, "active_reservations": int(c)} for a, n, c in workload]
    total_load = sum(item["active_reservations"] for item in loads)
    if loads and total_load:
        mean = total_load / len(loads)
        items.append({"kind": "ANALYSIS", "title": "Agent workload distribution",
                      "detail": f"{total_load} active reservation(s) across {len(loads)} active agent(s); "
                                f"mean {mean:.2f}",
                      "evidence": {"agents": loads, "mean": round(mean, 2)}})
        for item in loads:
            if item["active_reservations"] >= 3 and item["active_reservations"] > 2 * mean:
                items.append({"kind": "RECOMMENDATION", "title": f"Rebalance assignments for {item['full_name']}",
                              "detail": f"{item['full_name']} holds {item['active_reservations']} active "
                                        f"reservations (mean {mean:.2f}); consider assigning new clients "
                                        "to other agents.",
                              "rule": "agent has ≥3 active reservations and more than twice the mean"})
    else:
        items.append({"kind": "ANALYSIS", "title": "Agent workload distribution",
                      "detail": f"{INSUFFICIENT}: no active reservations recorded", "evidence": {}})

    # Document processing outcomes.
    failed = db.execute(
        select(Document.processing_stage, func.count()).where(Document.status == "FAILED")
        .group_by(Document.processing_stage)
    ).all()
    failures = {str(stage): int(count) for stage, count in failed}
    items.append({"kind": "DATA", "title": "Failed documents by stage",
                  "detail": ", ".join(f"{k}: {v}" for k, v in failures.items()) or "No failed documents",
                  "evidence": failures})
    if failures.get("ENTITY_MATCHING"):
        items.append({"kind": "RECOMMENDATION", "title": "Resolve unmatched document references",
                      "detail": f"{failures['ENTITY_MATCHING']} document(s) reference properties, agents or "
                                "clients that do not exist yet. Upload the missing Property/Agent "
                                "Information documents, then use Reprocess.",
                      "rule": "documents FAILED at ENTITY_MATCHING"})

    # Forecast observation.
    revenue_forecast = forecast(db, "revenue")
    items.append({
        "kind": "ANALYSIS", "title": "Revenue forecast",
        "detail": revenue_forecast.get("message") if revenue_forecast["status"] != "estimated" else
        f"Next month ≈ ₱{revenue_forecast['forecast'][0]['value']:,.2f} "
        f"(trend {revenue_forecast['slope_per_month']:+,.2f}/month, R² {revenue_forecast['r_squared']})",
        "evidence": {key: revenue_forecast[key] for key in ("status", "observations", "nonzero_months")},
    })

    if unknown or aged:
        if aged:
            items.append({"kind": "RECOMMENDATION", "title": "Review long-available listings",
                          "detail": f"Review pricing and marketing for {len(aged)} listing(s) available "
                                    f"for {PROLONGED_DAYS}+ days.",
                          "rule": f"AVAILABLE for at least {PROLONGED_DAYS} days"})

    pending = sum(
        int(db.scalar(select(func.count()).select_from(model).where(model.sync_status == "PENDING")) or 0)
        for model in (PropertyListing, Client, PropertyTransaction, Agent)
    )
    if pending:
        items.append({"kind": "RECOMMENDATION", "title": "Synchronize pending records",
                      "detail": f"{pending} local record(s) are not yet in the central database; run Sync.",
                      "rule": "records with sync_status = PENDING"})
    return {"generated_at": _now().isoformat(), "items": items}


RECORDED_AGENT_FIELDS = ("assigned_clients", "recorded_transactions", "open_reservations",
                         "recorded_completed_sales", "recorded_sales_value", "recorded_deals")


def agent_recorded_stats(db: Session, agent_ids: list[str] | None = None) -> dict[str, dict]:
    """Per agent, counted from the clients and transactions recorded in ALTY
    (the same basis as the Workforce page) — not the figures stored on the
    agent record by the Supabase import. Cancelled transactions are left out."""
    clients = select(Client.agent_id, func.count(func.distinct(Client.client_id))).group_by(Client.agent_id)
    activity = select(
        PropertyTransaction.agent_id,
        func.count(),
        func.coalesce(func.sum(case((
            (PropertyTransaction.transaction_type == "RESERVED")
            & (PropertyTransaction.status == "RESERVED"), 1), else_=0)), 0),
        func.coalesce(func.sum(case((SALE, 1), else_=0)), 0),
        func.coalesce(func.sum(case((SALE, PropertyTransaction.amount), else_=0)), 0),
    ).where(LIVE).group_by(PropertyTransaction.agent_id)
    # A deal is one client and one property: a reservation and its sale are
    # one deal; a cancelled reservation is a deal that didn't become a sale.
    deal = func.concat(PropertyTransaction.client_id, ":", PropertyTransaction.property_id)
    deals = select(PropertyTransaction.agent_id, func.count(func.distinct(deal))).group_by(PropertyTransaction.agent_id)
    if agent_ids is not None:
        clients = clients.where(Client.agent_id.in_(agent_ids))
        activity = activity.where(PropertyTransaction.agent_id.in_(agent_ids))
        deals = deals.where(PropertyTransaction.agent_id.in_(agent_ids))
    stats: dict[str, dict] = {}
    for agent_id, count in db.execute(clients).all():
        stats.setdefault(agent_id, dict.fromkeys(RECORDED_AGENT_FIELDS, 0))["assigned_clients"] = int(count)
    for agent_id, total, reservations, sales, value in db.execute(activity).all():
        entry = stats.setdefault(agent_id, dict.fromkeys(RECORDED_AGENT_FIELDS, 0))
        entry.update(recorded_transactions=int(total), open_reservations=int(reservations),
                     recorded_completed_sales=int(sales), recorded_sales_value=float(value or 0))
    for agent_id, count in db.execute(deals).all():
        stats.setdefault(agent_id, dict.fromkeys(RECORDED_AGENT_FIELDS, 0))["recorded_deals"] = int(count)
    for entry in stats.values():
        # Performance: share of recorded deals that became completed sales.
        entry["performance_rate"] = (round(entry["recorded_completed_sales"] / entry["recorded_deals"] * 100, 1)
                                     if entry["recorded_deals"] else None)
    return stats


def agent_forecasts(db: Session, horizon: int = 3, agent_id: str | None = None) -> list[dict]:
    """Each active agent's expected completed sales for the coming months,
    from that agent's own monthly history (same method as the company
    forecast). Agents without enough history get no numbers, only the reason."""
    statement = select(Agent).where(func.upper(Agent.status) == "ACTIVE").order_by(Agent.full_name)
    if agent_id is not None:
        statement = select(Agent).where(Agent.agent_id == agent_id)
    results = []
    for agent in db.execute(statement).scalars():
        result = forecast(db, "sales", horizon, agent_id=agent.agent_id)
        results.append({
            "agent_id": agent.agent_id, "full_name": agent.full_name, "status": result["status"],
            "observations": result["observations"], "nonzero_months": result["nonzero_months"],
            "minimum_required": result["minimum_required"],
            "recent_sales": sum(point["value"] for point in result["history"][-3:]),
            "expected_sales": round(sum(point["value"] for point in result["forecast"]), 1) if result["forecast"] else None,
            "trend_per_month": result.get("slope_per_month"),
            "forecast": result["forecast"],
        })
    return results


def workforce(db: Session) -> dict:
    now = _now().replace(tzinfo=None)
    users = db.execute(select(User)).scalars().all()
    roles: dict[str, dict] = {}
    for user in users:
        role = canonical_role(user.role)
        entry = roles.setdefault(role, {"role": role, "users": 0, "active": 0, "logged_in_30d": 0})
        entry["users"] += 1
        entry["active"] += int(user.is_active)
        entry["logged_in_30d"] += int(bool(user.last_login_at and (now - user.last_login_at).days <= 30))
    since = _now() - timedelta(days=90)
    agent_rows = db.execute(
        select(
            Agent.agent_id, Agent.full_name, Agent.status,
            func.count(func.distinct(Client.client_id)),
        ).outerjoin(Client, Client.agent_id == Agent.agent_id)
        .group_by(Agent.agent_id, Agent.full_name, Agent.status).order_by(Agent.full_name)
    ).all()
    activity = {
        agent_id: (int(total), int(reservations), int(sales))
        for agent_id, total, reservations, sales in db.execute(
            select(
                PropertyTransaction.agent_id,
                func.count(),
                func.coalesce(func.sum(case((
                    (PropertyTransaction.transaction_type == "RESERVED")
                    & (PropertyTransaction.status == "RESERVED"), 1), else_=0)), 0),
                func.coalesce(func.sum(case((SALE & (PropertyTransaction.transaction_date >= since), 1),
                                            else_=0)), 0),
            ).where(LIVE).group_by(PropertyTransaction.agent_id)
        ).all()
    }
    agents = []
    for agent_id, name, status, clients in agent_rows:
        total, reservations, recent_sales = activity.get(agent_id, (0, 0, 0))
        agents.append({"agent_id": agent_id, "full_name": name, "status": status,
                       "assigned_clients": int(clients), "transactions": total,
                       "active_reservations": reservations, "sales_last_90_days": recent_sales})
    return {
        "generated_at": _now().isoformat(),
        "users": {"total": len(users), "active": sum(1 for u in users if u.is_active),
                  "by_role": sorted(roles.values(), key=lambda item: item["role"])},
        "agents": {"total": len(agents),
                   "active": sum(1 for a in agents if str(a["status"]).upper() == "ACTIVE"),
                   "rows": agents},
    }


def dashboard_summary(db: Session) -> dict:
    data = overview(db)
    statuses = data["properties"]["by_status"]
    latest = select(Document.document_id, func.max(Document.version).label("version")).group_by(
        Document.document_id).subquery()
    document_rows = db.execute(
        select(Document.status, func.count()).join(
            latest, (Document.document_id == latest.c.document_id) & (Document.version == latest.c.version)
        ).group_by(Document.status)
    ).all()
    documents = {str(status): int(count) for status, count in document_rows}
    return {
        "total_properties": data["properties"]["total"],
        "available_properties": statuses.get("AVAILABLE", 0),
        "reserved_properties": statuses.get("RESERVED", 0),
        "sold_properties": statuses.get("SOLD", 0),
        "total_clients": data["clients"],
        "total_transactions": data["transactions"]["total"],
        "completed_revenue": data["transactions"]["revenue"],
        "active_agents": int(db.scalar(
            select(func.count(Agent.agent_id)).where(func.upper(Agent.status) == "ACTIVE")) or 0),
        "total_agents": int(db.scalar(select(func.count(Agent.agent_id))) or 0),
        "processing_documents": documents.get("PROCESSING", 0),
        "failed_documents": documents.get("FAILED", 0),
        "successful_documents": documents.get("SUCCESS", 0),
        "pending_documents": documents.get("PROCESSING", 0) + documents.get("FAILED", 0),
    }


__all__ = ["overview", "monthly_series", "forecast", "dss_insights", "workforce",
           "dashboard_summary", "INSUFFICIENT", "INSUFFICIENT_FORECAST"]
