from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentResponse, AgentSyncResult
from app.services.agent_sync import sync_agents


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


def _require_sync_permission(user: User) -> None:
    if user.role.casefold() not in {
        "administrator",
        "general manager",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only an administrator or general manager "
                "can sync agents"
            ),
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
# SYNC AGENTS FROM SUPABASE
# =========================================================

@router.post(
    "/sync",
    response_model=AgentSyncResult,
)
def sync_agent_records(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_sync_permission(user)

    return sync_agents(db)