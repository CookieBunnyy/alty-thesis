"""Agent recruitment: applicants moving through screening and interviews to
onboarding. Onboarding creates the agent record (pushed to the central
agents table like any new ALTY record). Management roles only.
"""

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_management
from app.models.agent import DESIGNATIONS, Agent
from app.models.branch import Branch
from app.models.user import User
from app.models.workforce import (APPLICANT_CLOSED, APPLICANT_SOURCES, APPLICANT_STAGES, APPLICANT_STATUSES,
                                  AgentApplicant)
from app.services.audit import record_audit
from app.services.cloud_sync import try_push_pending

router = APIRouter(prefix="/recruitment", tags=["Recruitment"])
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Which stage can follow which (closing is allowed from any open stage).
NEXT = {"APPLIED": "SCREENING", "SCREENING": "INTERVIEW", "INTERVIEW": "APPROVED"}


class ApplicantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    branch_id: int | None = None
    desired_designation: str | None = None
    source: str | None = None
    experience_years: float | None = Field(default=None, ge=0, le=60)
    has_license: bool | None = None
    license_number: str | None = Field(default=None, max_length=60)
    screening_score: int | None = Field(default=None, ge=0, le=100)
    interview_on: date | None = None
    notes: str | None = None

    @field_validator("full_name", "email", "phone_number", "address", "desired_designation", "source",
                     "license_number", "notes", mode="before")
    @classmethod
    def blank_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value is not None and not EMAIL.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("desired_designation")
    @classmethod
    def known_designation(cls, value):
        if value is not None and value not in DESIGNATIONS:
            raise ValueError(f"Designation must be one of: {', '.join(DESIGNATIONS)}")
        return value

    @field_validator("source")
    @classmethod
    def known_source(cls, value):
        if value is not None and value.upper() not in APPLICANT_SOURCES:
            raise ValueError(f"Source must be one of: {', '.join(APPLICANT_SOURCES)}")
        return value.upper() if value else value


class StageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def known_status(cls, value):
        value = value.strip().upper()
        if value not in APPLICANT_STATUSES or value == "ONBOARDED":
            raise ValueError("Use the Onboard action to onboard an approved applicant")
        return value


class OnboardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    designation: str | None = None
    branch_id: int | None = None
    work_area: str | None = Field(default=None, max_length=255)
    hired_on: date | None = None

    @field_validator("designation")
    @classmethod
    def known_designation(cls, value):
        if value is not None and value not in DESIGNATIONS:
            raise ValueError(f"Designation must be one of: {', '.join(DESIGNATIONS)}")
        return value


def _serialize(applicant: AgentApplicant, branches: dict[int, str]) -> dict:
    return {
        "id": applicant.id, "full_name": applicant.full_name, "email": applicant.email,
        "phone_number": applicant.phone_number, "address": applicant.address,
        "branch_id": applicant.branch_id, "branch_name": branches.get(applicant.branch_id),
        "desired_designation": applicant.desired_designation, "source": applicant.source,
        "experience_years": float(applicant.experience_years) if applicant.experience_years is not None else None,
        "has_license": applicant.has_license, "license_number": applicant.license_number,
        "screening_score": applicant.screening_score, "interview_on": applicant.interview_on,
        "status": applicant.status, "notes": applicant.notes, "history": applicant.history or [],
        "agent_id": applicant.agent_id, "created_by": applicant.created_by,
        "created_at": applicant.created_at, "updated_at": applicant.updated_at,
    }


def _branch_names(db: Session) -> dict[int, str]:
    return dict(db.execute(select(Branch.id, Branch.name)).all())


def _applicant_or_404(db: Session, applicant_id: int) -> AgentApplicant:
    applicant = db.get(AgentApplicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=404, detail="Applicant not found")
    return applicant


def _check_branch(db: Session, branch_id: int | None) -> None:
    if branch_id is not None and db.get(Branch, branch_id) is None:
        raise HTTPException(status_code=422, detail="That branch doesn't exist")


def _log(applicant: AgentApplicant, status: str, actor: User, note: str | None = None) -> None:
    applicant.history = [*(applicant.history or []), {
        "status": status, "at": datetime.utcnow().isoformat(timespec="seconds"),
        "by": actor.full_name or actor.username, "note": note}]


def next_agent_id(db: Session) -> str:
    """AGT-0001 style, one above the highest number in use."""
    highest = 0
    for (agent_id,) in db.execute(select(Agent.agent_id)).all():
        match = re.fullmatch(r"AGT-(\d+)", agent_id or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"AGT-{highest + 1:04d}"


@router.get("/applicants")
def list_applicants(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    names = _branch_names(db)
    rows = db.execute(select(AgentApplicant).order_by(AgentApplicant.created_at.desc())).scalars()
    return [_serialize(a, names) for a in rows]


@router.get("/summary")
def recruitment_summary(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    counts = dict(db.execute(select(AgentApplicant.status, func.count()).group_by(AgentApplicant.status)).all())
    total = sum(counts.values())
    onboarded = counts.get("ONBOARDED", 0)
    decided = onboarded + counts.get("APPROVED", 0) + counts.get("REJECTED", 0)
    return {"by_status": {status: int(counts.get(status, 0)) for status in APPLICANT_STATUSES},
            "total": int(total), "open": int(sum(counts.get(s, 0) for s in APPLICANT_STAGES[:4])),
            "acceptance_rate": round((onboarded + counts.get("APPROVED", 0)) / decided * 100, 1) if decided else None,
            "stages": APPLICANT_STAGES, "closed": APPLICANT_CLOSED, "sources": APPLICANT_SOURCES,
            "designations": DESIGNATIONS}


@router.post("/applicants", status_code=201)
def create_applicant(payload: ApplicantInput, db: Session = Depends(get_db),
                     actor: User = Depends(require_management)):
    if not payload.full_name:
        raise HTTPException(status_code=422, detail="Enter the applicant's name")
    _check_branch(db, payload.branch_id)
    values = payload.model_dump()
    values["has_license"] = bool(values["has_license"])
    applicant = AgentApplicant(**values, status="APPLIED", history=[],
                               created_by=actor.full_name or actor.username)
    _log(applicant, "APPLIED", actor, "Application recorded")
    db.add(applicant)
    db.flush()
    record_audit(db, "APPLICANT_CREATED", actor=actor, entity_type="agent_applicants", entity_id=applicant.id,
                 details={"name": applicant.full_name})
    db.commit()
    return _serialize(applicant, _branch_names(db))


@router.put("/applicants/{applicant_id}")
def update_applicant(applicant_id: int, payload: ApplicantInput, db: Session = Depends(get_db),
                     actor: User = Depends(require_management)):
    applicant = _applicant_or_404(db, applicant_id)
    values = payload.model_dump(exclude_unset=True)
    if "full_name" in values and not values["full_name"]:
        raise HTTPException(status_code=422, detail="The name can't be empty")
    _check_branch(db, values.get("branch_id"))
    if "has_license" in values:
        values["has_license"] = bool(values["has_license"])
    changes = {}
    for field, value in values.items():
        if getattr(applicant, field) != value:
            changes[field] = {"from": getattr(applicant, field), "to": value}
            setattr(applicant, field, value)
    if changes:
        record_audit(db, "APPLICANT_UPDATED", actor=actor, entity_type="agent_applicants", entity_id=applicant.id,
                     details=changes)
    db.commit()
    return _serialize(applicant, _branch_names(db))


@router.post("/applicants/{applicant_id}/stage")
def move_applicant(applicant_id: int, payload: StageInput, db: Session = Depends(get_db),
                   actor: User = Depends(require_management)):
    """Advance to the next stage, or close (rejected / withdrawn)."""
    applicant = _applicant_or_404(db, applicant_id)
    if applicant.status in APPLICANT_CLOSED or applicant.status == "ONBOARDED":
        raise HTTPException(status_code=409, detail="This application is already closed")
    target = payload.status
    if target not in APPLICANT_CLOSED and NEXT.get(applicant.status) != target:
        raise HTTPException(status_code=409, detail=f"From {applicant.status} the next stage is "
                                                    f"{NEXT.get(applicant.status, 'onboarding')}")
    if target == "REJECTED" and not payload.note:
        raise HTTPException(status_code=422, detail="Give a reason for rejecting the applicant")
    previous = applicant.status
    applicant.status = target
    _log(applicant, target, actor, payload.note)
    record_audit(db, "APPLICANT_STAGE_CHANGED", actor=actor, entity_type="agent_applicants", entity_id=applicant.id,
                 details={"from": previous, "to": target, "note": payload.note})
    db.commit()
    return _serialize(applicant, _branch_names(db))


@router.post("/applicants/{applicant_id}/onboard")
def onboard_applicant(applicant_id: int, payload: OnboardInput, db: Session = Depends(get_db),
                      actor: User = Depends(require_management)):
    """Create the agent record for an approved applicant."""
    applicant = _applicant_or_404(db, applicant_id)
    if applicant.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved applicants can be onboarded")
    branch_id = payload.branch_id if payload.branch_id is not None else applicant.branch_id
    _check_branch(db, branch_id)
    agent = Agent(agent_id=next_agent_id(db), full_name=applicant.full_name, phone_number=applicant.phone_number,
                  agent_location=applicant.address, status="ACTIVE", sync_status="PENDING",
                  branch_id=branch_id, designation=payload.designation or applicant.desired_designation or "Trainee Agent",
                  work_area=payload.work_area, hired_on=payload.hired_on or date.today())
    db.add(agent)
    db.flush()
    applicant.status = "ONBOARDED"
    applicant.agent_id = agent.agent_id
    _log(applicant, "ONBOARDED", actor, f"Agent record {agent.agent_id} created")
    record_audit(db, "APPLICANT_ONBOARDED", actor=actor, entity_type="agent_applicants", entity_id=applicant.id,
                 details={"agent_id": agent.agent_id, "name": agent.full_name})
    db.commit()
    try_push_pending(db)
    return {**_serialize(applicant, _branch_names(db)), "agent": {"agent_id": agent.agent_id,
                                                                  "full_name": agent.full_name}}


@router.delete("/applicants/{applicant_id}", status_code=204)
def delete_applicant(applicant_id: int, db: Session = Depends(get_db), actor: User = Depends(require_management)):
    applicant = _applicant_or_404(db, applicant_id)
    if applicant.status == "ONBOARDED":
        raise HTTPException(status_code=409, detail="Onboarded applicants are kept as the agent's hiring record")
    record_audit(db, "APPLICANT_DELETED", actor=actor, entity_type="agent_applicants", entity_id=applicant.id,
                 details={"name": applicant.full_name, "status": applicant.status})
    db.delete(applicant)
    db.commit()
