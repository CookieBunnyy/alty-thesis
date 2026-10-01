from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from decimal import Decimal

from app.models.agent import Agent
from app.models.client import Client
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.agent import AgentResponse, AgentSyncResult
from app.services.agent_sync import sync_agents
from app.services.audit import record_audit


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


# =========================================================
# GET ALL AGENTS
# =========================================================

@router.get(
    "",
    response_model=list[AgentResponse],
)
def get_agents(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return (
        db.execute(
            select(Agent).order_by(
                Agent.full_name
            )
        )
        .scalars()
        .all()
    )


# =========================================================
# GET TOTAL AGENT COUNT
# =========================================================

@router.get("/count")
def get_agent_count(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total = db.scalar(
        select(
            func.count(Agent.agent_id)
        ).where(func.upper(Agent.status) == 'ACTIVE')
    ) or 0

    return {
        "total": int(total)
    }


# =========================================================
# GET SINGLE AGENT
# =========================================================

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    agent = db.get(
        Agent,
        agent_id,
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        )

    return agent


# =========================================================
# AGENT RELATIONSHIPS (clients, properties, transactions)
# =========================================================

@router.get("/{agent_id}/activity")
def get_agent_activity(
    agent_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    clients = db.execute(
        select(Client).where(Client.agent_id == agent_id).order_by(Client.full_name)
    ).unique().scalars().all()
    transactions = db.execute(
        select(PropertyTransaction).where(PropertyTransaction.agent_id == agent_id)
        .order_by(PropertyTransaction.transaction_date.desc())
    ).scalars().all()
    sales = [t for t in transactions if t.transaction_type == "SOLD" and t.status == "COMPLETED"]
    property_ids = sorted({t.property_id for t in transactions})
    return {
        "agent_id": agent.agent_id,
        "full_name": agent.full_name,
        "recorded": {
            "clients": len(clients),
            "transactions": len(transactions),
            "active_reservations": sum(
                1 for t in transactions if t.transaction_type == "RESERVED" and t.status == "RESERVED"
            ),
            "completed_sales": len(sales),
            "sales_value": float(sum((t.amount for t in sales), Decimal("0"))),
            "properties": len(property_ids),
        },
        "clients": [
            {"client_id": c.client_id, "full_name": c.full_name, "status": c.status,
             "property_id": c.property_id}
            for c in clients
        ],
        "transactions": [
            {"transaction_id": t.transaction_id, "client_name": t.client.full_name,
             "property_id": t.property_id, "property_title": t.property_listing.title,
             "transaction_type": t.transaction_type, "transaction_date": t.transaction_date,
             "amount": float(t.amount), "status": t.status}
            for t in transactions
        ],
    }


# =========================================================
# SYNC AGENTS FROM SUPABASE
# =========================================================

@router.post(
    "/sync",
    response_model=AgentSyncResult,
)
def sync_agent_records(
    db: Session = Depends(get_db),
    user: User = Depends(require_management),
):
    result = sync_agents(db)
    record_audit(db, "AGENTS_SYNCED", actor=user, entity_type="agents",
                 details={key: value for key, value in result.items() if key != "last_synced_at"})
    db.commit()
    return result