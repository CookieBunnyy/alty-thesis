"""Dashboard aggregates. Every value is computed from stored records."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services import analytics
from app.services.transaction_queries import WITH_PARTIES

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return analytics.dashboard_summary(db)


@router.get("/property-status")
def get_dashboard_property_status(db: Session = Depends(get_db),
                                  _user: User = Depends(get_current_user)):
    rows = db.execute(
        select(func.upper(PropertyListing.status), func.count()).group_by(func.upper(PropertyListing.status))
    ).all()
    counts = {str(status): int(total) for status, total in rows}
    return {
        "available": counts.get("AVAILABLE", 0),
        "reserved": counts.get("RESERVED", 0),
        "sold": counts.get("SOLD", 0),
        "on_hold": counts.get("ON_HOLD", 0),
        "unavailable": counts.get("UNAVAILABLE", 0),
        "total": sum(counts.values()),
    }


@router.get("/transaction-trend")
def get_dashboard_transaction_trend(months: int = Query(default=12, ge=1, le=60),
                                    db: Session = Depends(get_db),
                                    _user: User = Depends(get_current_user)):
    series = analytics.monthly_series(db, months)
    return {
        "months": [row["month"] for row in series],
        "counts": [row["transactions"] for row in series],
        "reservations": [row["reservations"] for row in series],
        "sales": [row["sales"] for row in series],
        "has_data": any(row["transactions"] for row in series),
    }


@router.get("/revenue-trend")
def get_dashboard_revenue_trend(months: int = Query(default=12, ge=1, le=60),
                                db: Session = Depends(get_db),
                                _user: User = Depends(get_current_user)):
    series = analytics.monthly_series(db, months)
    return {
        "months": [row["month"] for row in series],
        "revenue": [row["revenue"] for row in series],
        "has_data": any(row["revenue"] for row in series),
    }


@router.get("/recent-transactions")
def get_dashboard_recent_transactions(limit: int = Query(default=6, ge=1, le=20),
                                      db: Session = Depends(get_db),
                                      _user: User = Depends(get_current_user)):
    rows = db.execute(
        select(PropertyTransaction).options(*WITH_PARTIES)
        .order_by(PropertyTransaction.transaction_date.desc(), PropertyTransaction.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "transaction_id": str(t.transaction_id),
            "client_name": t.client.full_name,
            "property_title": t.property_listing.title,
            "agent_name": t.agent.full_name,
            "transaction_type": t.transaction_type,
            "transaction_date": t.transaction_date,
            "amount": float(t.amount),
            "status": t.status,
            "cancellation_reason": t.cancellation_reason,
        }
        for t in rows
    ]


@router.get("/agent-performance")
def get_dashboard_agent_performance(limit: int = Query(default=8, ge=1, le=100),
                                    db: Session = Depends(get_db),
                                    _user: User = Depends(get_current_user)):
    agents = analytics.overview(db)["agents"]
    agents.sort(key=lambda row: (-row["transactions"], row["full_name"]))
    return [
        {"agent_id": row["agent_id"], "full_name": row["full_name"], "status": row["status"],
         "transactions": row["transactions"], "completed_sales": row["completed_sales"],
         "completed_revenue": row["sales_value"]}
        for row in agents[:limit]
    ]


@router.get("/forecast")
def get_dashboard_forecast(metric: str = Query(default="revenue", pattern="^(revenue|transactions|sales)$"),
                           db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    result = analytics.forecast(db, metric)
    result["next_month_revenue"] = (
        result["forecast"][0]["value"] if result["status"] == "estimated" and metric == "revenue" else None
    )
    result["historical_months"] = result["observations"]
    return result
