from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _months_back(count: int) -> list[str]:
    current = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for offset in range(count - 1, -1, -1):
        month = current.month - offset
        year = current.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        months.append(f"{year:04d}-{month:02d}")
    return months


def _monthly_completed_revenue(db: Session, months: list[str]) -> dict[str, float]:
    start = datetime.strptime(months[0], "%Y-%m").replace(tzinfo=timezone.utc)
    month_expression = func.to_char(PropertyTransaction.transaction_date, "YYYY-MM")
    rows = db.execute(
        select(
            month_expression,
            func.coalesce(func.sum(PropertyTransaction.amount), 0),
        )
        .where(
            PropertyTransaction.status == "COMPLETED",
            PropertyTransaction.transaction_date >= start,
        )
        .group_by(month_expression)
    ).all()
    return {str(month): float(amount or 0) for month, amount in rows}


@router.get("/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total_transactions = db.scalar(
        select(func.count(PropertyTransaction.transaction_id))
    ) or 0
    completed_revenue = db.scalar(
        select(func.coalesce(func.sum(PropertyTransaction.amount), 0)).where(
            PropertyTransaction.status == "COMPLETED"
        )
    ) or 0
    pending_documents = db.scalar(
        select(func.count(Document.id)).where(
            Document.status.in_({"PROCESSING", "PENDING_REVIEW"})
        )
    ) or 0
    active_agents = db.scalar(
        select(func.count(Agent.agent_id)).where(func.upper(Agent.status) == "ACTIVE")
    ) or 0
    return {
        "total_properties": int(
            db.scalar(select(func.count(PropertyListing.listing_id))) or 0
        ),
        "total_clients": int(db.scalar(select(func.count(Client.client_id))) or 0),
        "total_transactions": int(total_transactions),
        "completed_revenue": float(completed_revenue),
        "active_agents": int(active_agents),
        "pending_documents": int(pending_documents),
    }


@router.get("/property-status")
def get_dashboard_property_status(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(func.upper(PropertyListing.status), func.count(PropertyListing.listing_id))
        .group_by(func.upper(PropertyListing.status))
    ).all()
    counts = {str(status or "AVAILABLE"): int(total) for status, total in rows}
    return {
        "available": counts.get("AVAILABLE", 0),
        "reserved": counts.get("RESERVED", 0),
        "sold": counts.get("SOLD", 0),
        "on_hold": counts.get("ON_HOLD", 0),
        "unavailable": counts.get("UNAVAILABLE", 0),
        "total": sum(counts.values()),
    }


@router.get("/transaction-trend")
def get_dashboard_transaction_trend(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    months = _months_back(12)
    start = datetime.strptime(months[0], "%Y-%m").replace(tzinfo=timezone.utc)
    month_expression = func.to_char(PropertyTransaction.transaction_date, "YYYY-MM")
    rows = db.execute(
        select(
            month_expression,
            func.count(PropertyTransaction.transaction_id),
        )
        .where(PropertyTransaction.transaction_date >= start)
        .group_by(month_expression)
    ).all()
    counts = {str(month): int(total) for month, total in rows}
    return {
        "months": months,
        "counts": [counts.get(month, 0) for month in months],
    }


@router.get("/recent-transactions")
def get_dashboard_recent_transactions(
    limit: int = 6,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 20))
    rows = db.execute(
        select(PropertyTransaction)
        .join(PropertyTransaction.client)
        .join(PropertyTransaction.property_listing)
        .join(PropertyTransaction.agent)
        .order_by(PropertyTransaction.transaction_date.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "transaction_id": str(transaction.transaction_id),
            "client_name": transaction.client.full_name,
            "property_title": transaction.property_listing.title,
            "agent_name": transaction.agent.full_name,
            "transaction_type": transaction.transaction_type,
            "transaction_date": transaction.transaction_date,
            "amount": float(transaction.amount),
            "status": transaction.status,
        }
        for transaction in rows
    ]


@router.get("/agent-performance")
def get_dashboard_agent_performance(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(
            Agent.agent_id,
            Agent.full_name,
            Agent.status,
            func.count(PropertyTransaction.transaction_id),
            func.coalesce(
                func.sum(
                    case(
                        (PropertyTransaction.status == "COMPLETED", PropertyTransaction.amount),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .outerjoin(PropertyTransaction, PropertyTransaction.agent_id == Agent.agent_id)
        .group_by(Agent.agent_id, Agent.full_name, Agent.status)
        .order_by(func.count(PropertyTransaction.transaction_id).desc(), Agent.full_name)
        .limit(8)
    ).all()
    return [
        {
            "agent_id": agent_id,
            "full_name": full_name,
            "status": status,
            "transactions": int(transaction_count),
            "completed_revenue": float(revenue or 0),
        }
        for agent_id, full_name, status, transaction_count, revenue in rows
    ]


@router.get("/forecast")
def get_dashboard_forecast(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    months = _months_back(12)
    revenue_by_month = _monthly_completed_revenue(db, months)
    values = [revenue_by_month.get(month, 0.0) for month in months]
    observations = [(index, value) for index, value in enumerate(values) if value > 0]
    if len(observations) < 3:
        return {
            "status": "insufficient_data",
            "message": "Insufficient completed transaction history for a forecast.",
            "historical_months": len(observations),
            "next_month_revenue": None,
        }

    mean_x = sum(index for index, _ in observations) / len(observations)
    mean_y = sum(value for _, value in observations) / len(observations)
    denominator = sum((index - mean_x) ** 2 for index, _ in observations)
    slope = (
        sum((index - mean_x) * (value - mean_y) for index, value in observations)
        / denominator
        if denominator
        else 0.0
    )
    next_month_revenue = max(0.0, mean_y + slope * (len(months) - mean_x))
    return {
        "status": "estimated",
        "method": "linear trend of monthly completed transaction revenue",
        "historical_months": len(observations),
        "next_month_revenue": round(next_month_revenue, 2),
    }
