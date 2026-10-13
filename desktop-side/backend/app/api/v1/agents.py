from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from decimal import Decimal

from app.models.agent import DESIGNATIONS, Agent
from app.models.branch import Branch
from app.models.workforce import ASSESSMENT_CRITERIA, AgentAssessment
from app.models.client import Client
from app.models.review import AgentReview
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.agent import AgentResponse, AgentSyncResult
from app.services import reviews as review_service
from app.services.agent_sync import sync_agents
from app.services.analytics import agent_recorded_stats
from app.services import workforce_planning
from app.services.audit import record_audit
from app.services.profile_photos import photo_version, remove_photo, save_photo


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
    agents = db.execute(select(Agent).order_by(Agent.full_name)).scalars().all()
    stats = review_service.review_stats(db, [agent.agent_id for agent in agents])
    recorded = agent_recorded_stats(db)
    return [_with_reviews(agent, stats, recorded) for agent in agents]


def _with_reviews(agent: Agent, stats: dict, recorded: dict) -> AgentResponse:
    """The agent record plus client-review and recorded-activity figures."""
    response = AgentResponse.model_validate(agent)
    return response.model_copy(update={
        **review_service.stats_for(stats, agent.agent_id),
        **recorded.get(agent.agent_id, {}),
        "photo_version": photo_version(agent),
    })


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

@router.get("/me/work")
def get_my_work(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The signed-in staff member's own agent work (accounts linked to an agent)."""
    if not user.agent_id:
        raise HTTPException(status_code=404, detail="This account isn't linked to an agent record. "
                                                    "Ask the Administrator to link it in Users & Access.")
    agent = db.get(Agent, user.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent": _with_reviews(agent, review_service.review_stats(db, [agent.agent_id]),
                               agent_recorded_stats(db, [agent.agent_id])).model_dump(mode="json"),
        "activity": get_agent_activity(agent.agent_id, db, user),
        "reviews": get_agent_reviews(agent.agent_id, 10, 0, db, user),
    }


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

    return _with_reviews(agent, review_service.review_stats(db, [agent_id]),
                         agent_recorded_stats(db, [agent_id]))


# =========================================================
# CLIENT REVIEWS OF AN AGENT
# =========================================================

@router.get("/{agent_id}/reviews")
def get_agent_reviews(
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Client rating summary and recent reviews. Reviewers are shown as
    "First L." — staff don't need clients' contact details to read reviews."""
    if db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    stats = review_service.stats_for(review_service.review_stats(db, [agent_id]), agent_id)
    distribution = dict(db.execute(
        select(AgentReview.rating, func.count()).where(AgentReview.agent_id == agent_id)
        .group_by(AgentReview.rating)
    ).all())
    limit, offset = max(1, min(limit, 100)), max(0, offset)
    return {
        **stats,
        "distribution": {str(stars): int(distribution.get(stars, 0)) for stars in range(5, 0, -1)},
        "reviews": [
            {**review_service.public_review(review),
             "property_title": review.transaction.property_listing.title if review.transaction else None}
            for review in review_service.recent_reviews(db, agent_id, limit, offset)
        ],
    }


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
             "amount": float(t.amount), "status": t.status,
             "cancellation_reason": t.cancellation_reason}
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

# =========================================================
# PROFILE PHOTO (management roles)
# =========================================================

@router.put("/{agent_id}/photo", response_model=AgentResponse)
async def upload_agent_photo(agent_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                             user: User = Depends(require_management)):
    """Set the agent's profile photo (cropped to a square). It is shown to staff
    and on the public website's agent cards and agent page."""
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await save_photo(agent, "agents", agent_id, file)
    record_audit(db, "AGENT_PHOTO_UPDATED", actor=user, entity_type="agents", entity_id=agent_id)
    db.commit()
    db.refresh(agent)
    return _with_reviews(agent, review_service.review_stats(db, [agent_id]), agent_recorded_stats(db, [agent_id]))


@router.delete("/{agent_id}/photo", response_model=AgentResponse)
def delete_agent_photo(agent_id: str, db: Session = Depends(get_db), user: User = Depends(require_management)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    remove_photo(agent)
    record_audit(db, "AGENT_PHOTO_REMOVED", actor=user, entity_type="agents", entity_id=agent_id)
    db.commit()
    db.refresh(agent)
    return _with_reviews(agent, review_service.review_stats(db, [agent_id]), agent_recorded_stats(db, [agent_id]))


# =========================================================
# ASSIGNMENT: branch, designation, work area (management)
# =========================================================

class AssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int | None = None
    designation: str | None = None
    work_area: str | None = Field(default=None, max_length=255)
    hired_on: date | None = None

    @field_validator("designation", "work_area", mode="before")
    @classmethod
    def blank_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("designation")
    @classmethod
    def known_designation(cls, value):
        if value is not None and value not in DESIGNATIONS:
            raise ValueError(f"Designation must be one of: {', '.join(DESIGNATIONS)}")
        return value


@router.get("/designations/options")
def designation_options(_user: User = Depends(get_current_user)):
    return {"designations": DESIGNATIONS, "criteria": ASSESSMENT_CRITERIA}


@router.put("/{agent_id}/assignment", response_model=AgentResponse)
def update_assignment(agent_id: str, payload: AssignmentInput, db: Session = Depends(get_db),
                      actor: User = Depends(require_management)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("branch_id") is not None and db.get(Branch, values["branch_id"]) is None:
        raise HTTPException(status_code=422, detail="That branch doesn't exist")
    changes = {}
    for field, value in values.items():
        if getattr(agent, field) != value:
            changes[field] = {"from": getattr(agent, field), "to": value}
            setattr(agent, field, value)
    if changes:
        record_audit(db, "AGENT_ASSIGNMENT_UPDATED", actor=actor, entity_type="agents", entity_id=agent_id,
                     details=changes)
    db.commit()
    db.refresh(agent)
    return _with_reviews(agent, review_service.review_stats(db, [agent_id]), agent_recorded_stats(db, [agent_id]))


# =========================================================
# ASSESSMENTS (management)
# =========================================================

class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    scores: dict[str, int]
    remarks: str | None = Field(default=None, max_length=4000)
    recommendation: str | None = Field(default=None, max_length=60)

    @field_validator("scores")
    @classmethod
    def all_criteria(cls, value):
        missing = [c for c in ASSESSMENT_CRITERIA if c not in value]
        if missing or set(value) - set(ASSESSMENT_CRITERIA):
            raise ValueError(f"Score every criterion: {', '.join(ASSESSMENT_CRITERIA)}")
        if any(not 1 <= int(score) <= 5 for score in value.values()):
            raise ValueError("Scores are from 1 to 5")
        return {k: int(v) for k, v in value.items()}


def _assessment(row: AgentAssessment) -> dict:
    return {"id": row.id, "agent_id": row.agent_id, "period_start": row.period_start, "period_end": row.period_end,
            "scores": row.scores, "overall": float(row.overall), "rating": row.rating,
            "recommendation": row.recommendation, "kpis": row.kpis, "remarks": row.remarks,
            "assessed_by": row.assessed_by, "created_at": row.created_at}


def _agent_or_404(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{agent_id}/assessments")
def list_assessments(agent_id: str, db: Session = Depends(get_db), _user: User = Depends(require_management)):
    _agent_or_404(db, agent_id)
    rows = db.execute(select(AgentAssessment).where(AgentAssessment.agent_id == agent_id)
                      .order_by(AgentAssessment.period_end.desc(), AgentAssessment.id.desc())).scalars()
    return [_assessment(r) for r in rows]


@router.get("/{agent_id}/assessment-draft")
def draft_assessment(agent_id: str, start: date | None = None, end: date | None = None,
                     db: Session = Depends(get_db), _user: User = Depends(require_management)):
    """Recorded figures for the period and suggested scores for the criteria
    that the records can measure (default: the last full quarter)."""
    agent = _agent_or_404(db, agent_id)
    if start is None or end is None:
        today = date.today()
        quarter_start = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1)
        end = quarter_start - timedelta(days=1)
        start = date(end.year, 3 * ((end.month - 1) // 3) + 1, 1)
    if start > end:
        raise HTTPException(status_code=422, detail="The period must start before it ends")
    return workforce_planning.assessment_draft(db, agent, start, end)


@router.post("/{agent_id}/assessments", status_code=201)
def create_assessment(agent_id: str, payload: AssessmentInput, db: Session = Depends(get_db),
                      actor: User = Depends(require_management)):
    _agent_or_404(db, agent_id)
    if payload.period_start > payload.period_end:
        raise HTTPException(status_code=422, detail="The period must start before it ends")
    overall = round(sum(payload.scores.values()) / len(payload.scores), 2)
    rating = workforce_planning.rating_for(overall)
    row = AgentAssessment(
        agent_id=agent_id, period_start=payload.period_start, period_end=payload.period_end,
        scores=payload.scores, overall=overall, rating=rating,
        recommendation=payload.recommendation or workforce_planning.RECOMMENDATIONS[rating],
        kpis=jsonable_encoder(workforce_planning.agent_kpis(db, agent_id, payload.period_start, payload.period_end)),
        remarks=payload.remarks, assessed_by=actor.full_name or actor.username)
    db.add(row)
    db.flush()
    record_audit(db, "AGENT_ASSESSED", actor=actor, entity_type="agents", entity_id=agent_id,
                 details={"assessment_id": row.id, "overall": overall, "rating": rating})
    db.commit()
    return _assessment(row)


@router.delete("/{agent_id}/assessments/{assessment_id}", status_code=204)
def delete_assessment(agent_id: str, assessment_id: int, db: Session = Depends(get_db),
                      actor: User = Depends(require_management)):
    row = db.get(AgentAssessment, assessment_id)
    if row is None or row.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    record_audit(db, "AGENT_ASSESSMENT_DELETED", actor=actor, entity_type="agents", entity_id=agent_id,
                 details={"assessment_id": assessment_id})
    db.delete(row)
    db.commit()


@router.get("/{agent_id}/commission")
def agent_commission(agent_id: str, months: int = Query(default=12, ge=1, le=60), db: Session = Depends(get_db),
                     _user: User = Depends(require_management)):
    """Estimated commission per month (completed sales × the agent's rate)."""
    _agent_or_404(db, agent_id)
    return workforce_planning.agent_commission(db, agent_id, months)
