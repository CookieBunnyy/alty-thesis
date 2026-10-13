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


def commission_rates(db: Session) -> dict[str, float]:
    """Each agent's commission rate: recorded total commission ÷ recorded
    total sales when both are known, else DEFAULT_COMMISSION_RATE."""
    rates = {}
    for agent_id, total_sales, total_commission in db.execute(
            select(Agent.agent_id, Agent.total_sales, Agent.total_commission)).all():
        sales, commission = float(total_sales or 0), float(total_commission or 0)
        rates[agent_id] = commission / sales if sales > 0 and commission > 0 else settings.DEFAULT_COMMISSION_RATE
    return rates


def _branch_filter(statement, branch_id: int | None):
    """Transactions of one branch: the agent's branch, else the listing's.
    ``branch_id`` 0 means transactions with no branch at all."""
    if branch_id is None:
        return statement
    agent_branch = select(Agent.branch_id).where(Agent.agent_id == PropertyTransaction.agent_id).scalar_subquery()
    listing_branch = select(PropertyListing.branch_id).where(
        PropertyListing.listing_id == PropertyTransaction.property_id).scalar_subquery()
    branch = func.coalesce(agent_branch, listing_branch)
    return statement.where(branch.is_(None) if branch_id == 0 else branch == branch_id)


def monthly_series(db: Session, months: int | None = None, agent_id: str | None = None,
                   branch_id: int | None = None) -> list[dict]:
    """Per-month transaction counts, sales revenue and estimated commission.
    ``months`` limits the window to the last N months (including the current
    one). With ``agent_id`` (or ``branch_id``) only that agent's (branch's)
    transactions are counted, over the company's full history (months with
    nothing for them count as zero)."""
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
    statement = _branch_filter(statement, branch_id)
    rows = db.execute(statement.group_by(month)).all()
    data = {
        str(key): {"transactions": int(count), "reservations": int(reservations),
                   "sales": int(sales), "revenue": float(revenue or 0), "commission": 0.0}
        for key, count, reservations, sales, revenue in rows
    }
    # Commission: each completed sale × its agent's commission rate.
    rates = commission_rates(db)
    sales_statement = select(month, PropertyTransaction.agent_id, func.sum(PropertyTransaction.amount)).where(SALE)
    if agent_id is not None:
        sales_statement = sales_statement.where(PropertyTransaction.agent_id == agent_id)
    sales_statement = _branch_filter(sales_statement, branch_id)
    for key, sale_agent, amount in db.execute(sales_statement.group_by(month, PropertyTransaction.agent_id)).all():
        if str(key) in data:
            data[str(key)]["commission"] += float(amount or 0) * rates.get(sale_agent, settings.DEFAULT_COMMISSION_RATE)
    for entry in data.values():
        entry["commission"] = round(entry["commission"], 2)
    current = _month_key(_now())
    first = min(data) if data else None
    if (agent_id is not None or branch_id is not None) and not months:
        first = db.scalar(select(func.min(month)).where(LIVE))
    if months:
        keys = _month_range(_shift_month(current, -(months - 1)), current)
    elif first:
        keys = _month_range(str(first), current)
    else:
        keys = []
    empty = {"transactions": 0, "reservations": 0, "sales": 0, "revenue": 0.0, "commission": 0.0}
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


SEASONAL_MIN_MONTHS = 12   # a seasonal pattern needs at least one full year
METRICS = {"revenue", "transactions", "sales", "commission"}


def _trend(values: list[float]) -> dict:
    """The straight line closest to the values at month numbers 0..n-1
    (least squares), with the averages it is built from:
        trend          = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)²
        starting level = ȳ − trend × x̄"""
    n = len(values)
    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)
    mean_x, mean_y = float(x.mean()), float(y.mean())
    spread_x = float(((x - mean_x) ** 2).sum())
    slope = float(((x - mean_x) * (y - mean_y)).sum() / spread_x) if spread_x else 0.0
    return {"intercept": mean_y - slope * mean_x, "slope": slope, "mean_x": mean_x, "mean_y": mean_y}


def _seasonal(months: list[str], values: list[float], line: dict) -> dict[int, dict]:
    """How each calendar month usually compares with the trend line.

    For every past month: actual ÷ trend-line value. A calendar month's factor
    is the average of those, damped toward 1 by n/(n+1) (half weight when the
    month has been seen once, two-thirds when twice...), so one unusual year
    can't swing the forecast. Factors are then scaled to average 1 across the
    year, so the seasonal step only moves sales between months."""
    ratios: dict[int, list[float]] = {}
    for index, (key, value) in enumerate(zip(months, values)):
        expected = line["intercept"] + line["slope"] * index
        if expected > 0:
            ratios.setdefault(int(key[5:7]), []).append(value / expected)
    factors = {}
    for month in range(1, 13):
        seen = ratios.get(month, [])
        raw = float(np.mean(seen)) if seen else 1.0
        weight = len(seen) / (len(seen) + 1)
        factors[month] = {"seen": len(seen), "raw": raw, "weight": weight, "factor": 1 + weight * (raw - 1)}
    mean = float(np.mean([f["factor"] for f in factors.values()])) or 1.0
    for item in factors.values():
        item["factor"] /= mean
    return factors


def _predict(months: list[str], values: list[float], target_index: int, target_month: str, seasonal: bool) -> dict:
    """Forecast one month from the months before it, with every input kept so
    the page can show the working."""
    line = _trend(values)
    use_season = seasonal and len(values) >= SEASONAL_MIN_MONTHS
    factors = _seasonal(months, values, line) if use_season else {}
    fitted = []
    for index, key in enumerate(months):
        base = line["intercept"] + line["slope"] * index
        fitted.append(base * (factors[int(key[5:7])]["factor"] if use_season else 1.0))
    residuals = np.array(values) - np.array(fitted)
    sigma = float(np.std(residuals, ddof=1)) if len(values) > 2 else 0.0
    trend_value = line["intercept"] + line["slope"] * target_index
    season = factors.get(int(target_month[5:7])) if use_season else None
    value = max(0.0, trend_value * (season["factor"] if season else 1.0))
    return {
        "value": value, "lower": max(0.0, value - 1.96 * sigma), "upper": value + 1.96 * sigma,
        "model": {
            "months_used": len(values), "first_month": months[0], "last_month": months[-1],
            "average_month_number": round(line["mean_x"], 2), "average_value": round(line["mean_y"], 2),
            "intercept": round(line["intercept"], 2), "slope": round(line["slope"], 2), "x": target_index,
            "trend_value": round(trend_value, 2),
            "seasonal": bool(season),
            "seasonal_months_needed": SEASONAL_MIN_MONTHS,
            "seasonal_factor": round(season["factor"], 4) if season else None,
            "seasonal_seen": season["seen"] if season else 0,
            "seasonal_raw": round(season["raw"], 4) if season else None,
            "seasonal_weight": round(season["weight"], 4) if season else None,
            "sigma": round(sigma, 2),
        },
    }


def forecast(db: Session, metric: str = "revenue", horizon: int = 3, agent_id: str | None = None,
             seasonal: bool = True, branch_id: int | None = None) -> dict:
    """Trend line plus each calendar month's usual pattern, over complete
    months, only with enough history. With ``agent_id``, the forecast is for
    that agent's own activity (trend only: too few sales for a pattern)."""
    if metric not in METRICS:
        raise ValueError("metric must be revenue, transactions, sales or commission")
    current = _month_key(_now())
    history = [row for row in monthly_series(db, agent_id=agent_id, branch_id=branch_id)
               if row["month"] != current]  # complete months
    values = [float(row[metric]) for row in history]
    months = [row["month"] for row in history]
    nonzero = sum(1 for value in values if value > 0)
    base = {"metric": metric, "observations": len(values), "nonzero_months": nonzero,
            "minimum_required": settings.FORECAST_MIN_MONTHS,
            "history": [{"month": row["month"], "value": row[metric]} for row in history]}
    if len(values) < settings.FORECAST_MIN_MONTHS or nonzero < 3:
        return {**base, "status": "insufficient_data", "message": INSUFFICIENT_FORECAST,
                "forecast": []}

    seasonal = seasonal and agent_id is None
    points = []
    for step in range(horizon):
        month = _shift_month(current, step)
        predicted = _predict(months, values, len(values) + step, month, seasonal)
        points.append({"month": month, "value": round(predicted["value"], 2), "lower": round(predicted["lower"], 2),
                       "upper": round(predicted["upper"], 2), "model": predicted["model"]})
    line = _trend(values)
    y = np.array(values)
    fitted = line["intercept"] + line["slope"] * np.arange(len(values))
    r2 = float(1 - ((y - fitted) ** 2).sum() / ((y - y.mean()) ** 2).sum()) if np.var(y) > 0 else None
    uses_season = bool(points and points[0]["model"]["seasonal"])
    return {
        **base,
        "status": "estimated",
        "method": ("Least-squares trend line over complete months, adjusted by each calendar month's usual "
                   "pattern" if uses_season else "Least-squares trend line over complete months"),
        "seasonal": uses_season,
        "slope_per_month": round(line["slope"], 2),
        "r_squared": round(r2, 4) if r2 is not None else None,
        "interval": "approximate 95% band from the spread of past months around the forecast line",
        "forecast": points,
    }


def outlook(db: Session, metric: str = "revenue", horizon: int = 3) -> dict:
    """The forecast plus a look back: for each past complete month with
    enough earlier history, what the same method would have predicted from
    the months before it, and whether the recorded value landed in its range.
    Every point carries its inputs, so the page can show the working."""
    result = forecast(db, metric, horizon)
    values = [float(point["value"]) for point in result["history"]]
    months = [point["month"] for point in result["history"]]
    backtest = []
    for index, month in enumerate(months):
        prior = values[:index]
        if len(prior) < settings.FORECAST_MIN_MONTHS or sum(1 for v in prior if v > 0) < 3:
            continue
        predicted = _predict(months[:index], prior, index, month, True)
        actual = values[index]
        lower, upper = predicted["lower"], predicted["upper"]
        verdict = "WITHIN" if lower <= actual <= upper else ("ABOVE" if actual > upper else "BELOW")
        backtest.append({
            "month": month, "actual": round(actual, 2), "value": round(predicted["value"], 2),
            "lower": round(lower, 2), "upper": round(upper, 2), "verdict": verdict, "model": predicted["model"],
        })
    result["backtest"] = backtest
    result["accuracy"] = {"months": len(backtest), "within": sum(1 for b in backtest if b["verdict"] == "WITHIN"),
                          "above": sum(1 for b in backtest if b["verdict"] == "ABOVE"),
                          "below": sum(1 for b in backtest if b["verdict"] == "BELOW")}
    return result


def month_breakdown(db: Session, month: str, metric: str = "revenue") -> dict:
    """The records behind one month's figure: completed sales for revenue and
    sales, every live transaction for transactions (same rules as the chart)."""
    key = func.to_char(func.timezone("UTC", PropertyTransaction.transaction_date), "YYYY-MM")
    condition = SALE if metric in {"revenue", "sales", "commission"} else LIVE
    rates = commission_rates(db) if metric == "commission" else {}
    rows = db.execute(select(PropertyTransaction).where(key == month, condition)
                      .order_by(PropertyTransaction.transaction_date)).scalars().all()
    items = [{
        "transaction_id": str(row.transaction_id),
        "date": row.transaction_date,
        "type": row.transaction_type,
        "status": row.status,
        "amount": round(float(row.amount or 0) * rates.get(row.agent_id, settings.DEFAULT_COMMISSION_RATE), 2)
        if metric == "commission" else float(row.amount or 0),
        "sale_amount": float(row.amount or 0),
        "commission_rate": rates.get(row.agent_id, settings.DEFAULT_COMMISSION_RATE) if metric == "commission" else None,
        "client": row.client.full_name if row.client else None,
        "property": row.property_listing.title if row.property_listing else None,
        "agent": row.agent.full_name if row.agent else None,
    } for row in rows]
    total = sum(item["amount"] for item in items) if metric in {"revenue", "commission"} else float(len(items))
    return {"month": month, "metric": metric, "count": len(items), "total": round(total, 2), "items": items}


def _pct_change(recent: float, previous: float) -> float | None:
    return round((recent - previous) / previous * 100, 1) if previous else None


DIAG_PRICE_DROP = 0.10     # average sale price down by 10% or more counts as a cause
DIAG_LOW_STOCK = 2         # a category that sells, with this many or fewer available listings


def _month_stats(db: Session, month: str) -> dict:
    """What happened in one month, in the pieces a drop can be traced to."""
    key = func.to_char(func.timezone("UTC", PropertyTransaction.transaction_date), "YYYY-MM")
    sales = db.execute(select(PropertyTransaction).where(key == month, SALE)).scalars().all()
    revenue = sum(float(row.amount or 0) for row in sales)
    reservations = db.scalar(select(func.count()).select_from(PropertyTransaction).where(
        key == month, PropertyTransaction.transaction_type == "RESERVED")) or 0
    cancelled_key = func.to_char(func.coalesce(PropertyTransaction.cancelled_at,
                                               func.timezone("UTC", PropertyTransaction.transaction_date)), "YYYY-MM")
    cancelled = db.execute(select(PropertyTransaction.cancellation_reason).where(
        cancelled_key == month, PropertyTransaction.status == "CANCELLED")).scalars().all()
    reasons: dict[str, int] = {}
    for reason in cancelled:
        label = (reason or "").strip() or "No reason recorded"
        reasons[label] = reasons.get(label, 0) + 1
    new_clients = db.scalar(select(func.count()).select_from(Client).where(
        func.to_char(Client.created_at, "YYYY-MM") == month)) or 0
    agents: dict[str, dict] = {}
    categories: dict[str, dict] = {}
    for row in sales:
        amount = float(row.amount or 0)
        agent = agents.setdefault(str(row.agent_id), {"name": row.agent.full_name if row.agent else None,
                                                      "sales": 0, "revenue": 0.0})
        agent["sales"] += 1
        agent["revenue"] += amount
        category = (row.property_listing.category if row.property_listing else None) or "Uncategorized"
        group = categories.setdefault(category, {"sales": 0, "revenue": 0.0})
        group["sales"] += 1
        group["revenue"] += amount
    return {
        "sales": len(sales), "revenue": round(revenue, 2),
        "average_sale": round(revenue / len(sales), 2) if sales else None,
        "reservations": int(reservations), "cancellations": len(cancelled),
        "cancellation_reasons": sorted(({"reason": r, "count": c} for r, c in reasons.items()),
                                       key=lambda item: -item["count"])[:3],
        "new_clients": int(new_clients), "agents": agents, "categories": categories,
    }


def _drops(before: dict, now: dict, label: str) -> list[dict]:
    """Groups (agents or categories) whose sales revenue fell, biggest fall first."""
    dropped = []
    for key, was in before.items():
        is_now = now.get(key, {"sales": 0, "revenue": 0.0})
        if is_now["revenue"] < was["revenue"]:
            item = {label: key, "before": round(was["revenue"], 2), "now": round(is_now["revenue"], 2),
                    "sales_before": was["sales"], "sales_now": is_now["sales"]}
            if "name" in was:
                item["name"] = was["name"]
            dropped.append(item)
    return sorted(dropped, key=lambda item: item["now"] - item["before"])


DIAG_ORDER = ["FEWER_SALES", "LOWER_PRICE", "CANCELLATIONS", "FEWER_RESERVATIONS", "FEWER_NEW_CLIENTS",
              "AGENT_DROP", "CATEGORY_DROP", "LOW_STOCK", "SEASONAL_LOW", "NO_CLEAR_CAUSE"]


def month_diagnosis(db: Session, month: str, metric: str = "revenue") -> dict:
    """Decision support for a month that missed its likely range or did worse
    than the month before. First what changed (fewer deals, lower prices, a
    thinner pipeline, cancellations, agents, categories, stock), then the
    causes, biggest first. Rule-based and computed from recorded data only;
    the page turns each cause into a suggestion and management decides."""
    if metric not in METRICS:
        raise ValueError("metric must be revenue, transactions, sales or commission")
    previous_month = _shift_month(month, -1)
    series = {row["month"]: row for row in monthly_series(db)}
    actual = float(series.get(month, {}).get(metric, 0) or 0)
    previous = float(series.get(previous_month, {}).get(metric, 0) or 0)
    checked = next((b for b in outlook(db, metric, 1)["backtest"] if b["month"] == month), None)

    reasons = []
    if checked and checked["verdict"] == "BELOW":
        reasons.append("BELOW_RANGE")
    if previous_month in series and actual < previous:
        reasons.append("BELOW_PREVIOUS")
    base = {"month": month, "previous_month": previous_month, "metric": metric, "actual": actual,
            "previous": previous, "change_pct": _pct_change(actual, previous),
            "expected": ({"value": checked["value"], "lower": checked["lower"], "upper": checked["upper"]}
                         if checked else None),
            "reasons": reasons, "triggered": bool(reasons), "findings": []}
    if not reasons:
        return base

    now, before = _month_stats(db, month), _month_stats(db, previous_month)
    findings: list[dict] = []
    # Revenue change = (change in number of sales × last month's average price)
    #                + (this month's sales × change in average price); the two add up exactly.
    before_avg = before["average_sale"] or 0.0
    now_avg = now["average_sale"] if now["average_sale"] is not None else before_avg
    from_count = (now["sales"] - before["sales"]) * before_avg
    from_price = now["sales"] * (now_avg - before_avg)
    if now["sales"] < before["sales"]:
        findings.append({"code": "FEWER_SALES", "impact": round(-from_count, 2),
                         "params": {"now": now["sales"], "before": before["sales"]}})
    if before_avg and now["average_sale"] and now["average_sale"] < before_avg * (1 - DIAG_PRICE_DROP):
        findings.append({"code": "LOWER_PRICE", "impact": round(-from_price, 2),
                         "params": {"now": now["average_sale"], "before": before_avg,
                                    "pct": round((before_avg - now["average_sale"]) / before_avg * 100)}})
    if now["cancellations"] and now["cancellations"] >= before["cancellations"]:
        findings.append({"code": "CANCELLATIONS", "impact": None,
                         "params": {"now": now["cancellations"], "before": before["cancellations"],
                                    "reasons": now["cancellation_reasons"]}})
    if now["reservations"] < before["reservations"]:
        findings.append({"code": "FEWER_RESERVATIONS", "impact": None,
                         "params": {"now": now["reservations"], "before": before["reservations"]}})
    if before["new_clients"] and now["new_clients"] < before["new_clients"]:
        findings.append({"code": "FEWER_NEW_CLIENTS", "impact": None,
                         "params": {"now": now["new_clients"], "before": before["new_clients"]}})
    agents = _drops(before["agents"], now["agents"], "agent_id")
    if agents:
        findings.append({"code": "AGENT_DROP", "impact": round(sum(a["before"] - a["now"] for a in agents), 2),
                         "params": {"agents": agents[:3]}})
    categories = _drops(before["categories"], now["categories"], "category")
    if categories:
        findings.append({"code": "CATEGORY_DROP",
                         "impact": round(sum(c["before"] - c["now"] for c in categories), 2),
                         "params": {"categories": categories[:3]}})
    stock = {category or "Uncategorized": int(count) for category, count in db.execute(
        select(PropertyListing.category, func.count()).where(PropertyListing.status == "AVAILABLE")
        .group_by(PropertyListing.category)).all()}
    low = [{"category": c, "available": stock.get(c, 0)}
           for c in sorted(set(before["categories"]) | set(now["categories"])) if stock.get(c, 0) <= DIAG_LOW_STOCK]
    if low:
        findings.append({"code": "LOW_STOCK", "impact": None, "params": {"categories": low}})
    model = checked["model"] if checked else None
    if model and model.get("seasonal") and (model.get("seasonal_factor") or 1) < 1:
        findings.append({"code": "SEASONAL_LOW", "impact": None,
                         "params": {"pct": round((1 - model["seasonal_factor"]) * 100)}})
    if not findings:
        findings.append({"code": "NO_CLEAR_CAUSE", "impact": None, "params": {}})

    # The two parts of the revenue change first, the bigger one on top; then the rest in a fixed order.
    money = {"FEWER_SALES", "LOWER_PRICE"}
    findings.sort(key=lambda f: (f["code"] not in money, -(f["impact"] or 0) if f["code"] in money else 0,
                                 DIAG_ORDER.index(f["code"])))
    summary = lambda stats: {k: v for k, v in stats.items() if k not in {"agents", "categories"}}  # noqa: E731
    return {**base, "now": summary(now), "before": summary(before),
            "revenue_change": {"total": round(now["revenue"] - before["revenue"], 2),
                               "from_sales_count": round(from_count, 2), "from_average_price": round(from_price, 2)},
            "findings": findings}


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
        result = forecast(db, "sales", horizon, agent_id=agent.agent_id, seasonal=False)
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
