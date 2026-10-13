"""Branches: the offices agents and listings belong to.

All staff can read the branch list (for pickers); management roles add, edit
and delete branches and see the branch-to-branch comparison. A branch with
agents or listings can't be deleted (mark it inactive instead).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.agent import Agent
from app.models.branch import Branch
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services import workforce_planning
from app.services.audit import record_audit

router = APIRouter(prefix="/branches", tags=["Branches"])


class BranchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    contact_number: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name", "code", "address", "contact_number", "email", "notes", mode="before")
    @classmethod
    def blank_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


def _counts(db: Session) -> tuple[dict, dict]:
    agents = dict(db.execute(select(Agent.branch_id, func.count()).where(Agent.branch_id.is_not(None))
                             .group_by(Agent.branch_id)).all())
    listings = dict(db.execute(select(PropertyListing.branch_id, func.count())
                               .where(PropertyListing.branch_id.is_not(None))
                               .group_by(PropertyListing.branch_id)).all())
    return agents, listings


def _serialize(branch: Branch, agents: dict, listings: dict) -> dict:
    return {"id": branch.id, "name": branch.name, "code": branch.code, "address": branch.address,
            "contact_number": branch.contact_number, "email": branch.email, "notes": branch.notes,
            "is_active": branch.is_active, "created_at": branch.created_at, "updated_at": branch.updated_at,
            "agents": int(agents.get(branch.id, 0)), "listings": int(listings.get(branch.id, 0))}


def _branch_or_404(db: Session, branch_id: int) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


def _check_unique(db: Session, branch_id: int | None, name: str | None, code: str | None) -> None:
    for column, value, label in ((Branch.name, name, "name"), (Branch.code, code, "code")):
        if value is None:
            continue
        statement = select(Branch.id).where(func.lower(column) == value.lower())
        if branch_id is not None:
            statement = statement.where(Branch.id != branch_id)
        if db.scalar(statement) is not None:
            raise HTTPException(status_code=409, detail=f"Another branch already uses that {label}")


@router.get("")
def list_branches(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    agents, listings = _counts(db)
    return [_serialize(b, agents, listings) for b in db.execute(select(Branch).order_by(Branch.name)).scalars()]


@router.get("/comparison")
def compare_branches(db: Session = Depends(get_db), _user: User = Depends(require_management)):
    """Branch-to-branch performance and trends."""
    return workforce_planning.branch_comparison(db)


@router.get("/{branch_id}")
def get_branch(branch_id: int, db: Session = Depends(get_db), _user: User = Depends(require_management)):
    branch = _branch_or_404(db, branch_id)
    agents, listings = _counts(db)
    members = db.execute(select(Agent).where(Agent.branch_id == branch_id).order_by(Agent.full_name)).scalars()
    return {**_serialize(branch, agents, listings),
            "agent_rows": [{"agent_id": a.agent_id, "full_name": a.full_name, "status": a.status,
                            "designation": a.designation, "work_area": a.work_area} for a in members]}


@router.post("", status_code=201)
def create_branch(payload: BranchInput, db: Session = Depends(get_db), actor: User = Depends(require_management)):
    if not payload.name:
        raise HTTPException(status_code=422, detail="Enter the branch name")
    _check_unique(db, None, payload.name, payload.code)
    values = payload.model_dump()
    values["is_active"] = True if values["is_active"] is None else values["is_active"]
    branch = Branch(**values)
    db.add(branch)
    db.flush()
    record_audit(db, "BRANCH_CREATED", actor=actor, entity_type="branches", entity_id=branch.id,
                 details={"name": branch.name})
    db.commit()
    return _serialize(branch, {}, {})


@router.put("/{branch_id}")
def update_branch(branch_id: int, payload: BranchInput, db: Session = Depends(get_db),
                  actor: User = Depends(require_management)):
    branch = _branch_or_404(db, branch_id)
    values = payload.model_dump(exclude_unset=True)
    if "name" in values and not values["name"]:
        raise HTTPException(status_code=422, detail="The name can't be empty")
    if values.get("is_active") is None:
        values.pop("is_active", None)
    _check_unique(db, branch_id, values.get("name"), values.get("code"))
    changes = {}
    for field, value in values.items():
        if getattr(branch, field) != value:
            changes[field] = {"from": getattr(branch, field), "to": value}
            setattr(branch, field, value)
    if changes:
        record_audit(db, "BRANCH_UPDATED", actor=actor, entity_type="branches", entity_id=branch.id, details=changes)
    db.commit()
    agents, listings = _counts(db)
    return _serialize(branch, agents, listings)


@router.delete("/{branch_id}", status_code=204)
def delete_branch(branch_id: int, db: Session = Depends(get_db), actor: User = Depends(require_management)):
    branch = _branch_or_404(db, branch_id)
    agents, listings = _counts(db)
    staff = db.scalar(select(func.count()).select_from(User).where(User.branch_id == branch_id)) or 0
    if agents.get(branch_id) or listings.get(branch_id) or staff:
        raise HTTPException(status_code=409, detail="This branch still has agents, listings or staff. Move them to "
                                                    "another branch first, or mark the branch inactive.")
    record_audit(db, "BRANCH_DELETED", actor=actor, entity_type="branches", entity_id=branch.id,
                 details={"name": branch.name})
    db.delete(branch)
    db.commit()
