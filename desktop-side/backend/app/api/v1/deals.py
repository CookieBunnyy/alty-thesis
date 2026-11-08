"""Deals: each buyer's path from inquiry to closing.

Company staff see and manage every deal. A seller sees only the deals they
handle and may record inquiries and viewings (physical or virtual) and mark a
deal lost; reservation, developer processing and closing are recorded by
management or come from the reservation and sale records.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import COMPANY_ROLES, MANAGEMENT_ROLES, SELLER, canonical_role, get_current_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.deal import DEAL_CLOSED, DEAL_STAGES, DEVELOPER_STATUSES, VIEWING_TYPES, Deal, DealEvent
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services import deal_pipeline
from app.services.audit import record_audit

router = APIRouter(prefix="/deals", tags=["Deals"])
STAGES = DEAL_STAGES + ("LOST",)
SELLER_STAGES = {"VIEWING", "LOST"}


class BuyerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=200)
    phone_number: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)


class DealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = None
    buyer: BuyerInput | None = None
    listing_id: int
    agent_id: str | None = None
    inquiry_date: date | None = None
    viewing_type: str | None = None
    viewing_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("viewing_type")
    @classmethod
    def known_viewing(cls, value):
        if value is not None and value.upper() not in VIEWING_TYPES:
            raise ValueError("Viewing type must be PHYSICAL or VIRTUAL")
        return value.upper() if value else value


class DealUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inquiry_date: date | None = None
    viewing_type: str | None = None
    viewing_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)
    agent_id: str | None = None
    developer_status: str | None = None
    reservation_date: date | None = None

    @field_validator("viewing_type")
    @classmethod
    def known_viewing(cls, value):
        if value is not None and value.upper() not in VIEWING_TYPES:
            raise ValueError("Viewing type must be PHYSICAL or VIRTUAL")
        return value.upper() if value else value

    @field_validator("developer_status")
    @classmethod
    def known_developer_status(cls, value):
        if value is not None and value.upper() not in DEVELOPER_STATUSES:
            raise ValueError(f"Developer status must be one of: {', '.join(DEVELOPER_STATUSES)}")
        return value.upper() if value else value


class StageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str
    note: str | None = Field(default=None, max_length=1000)
    reservation_date: date | None = None

    @field_validator("stage")
    @classmethod
    def known_stage(cls, value):
        value = value.strip().upper()
        if value not in STAGES:
            raise ValueError(f"Stage must be one of: {', '.join(STAGES)}")
        return value


def _actor(user: User) -> str:
    return user.full_name or user.username


def _access(user: User) -> str:
    """'company' (all deals) or 'seller' (own deals); anything else is refused."""
    role = canonical_role(user.role)
    if role in COMPANY_ROLES:
        return "company"
    if role == SELLER and user.agent_id:
        return "seller"
    raise HTTPException(status_code=403, detail="Your account can't open deals")


def _deal_or_404(db: Session, deal_id: int, user: User) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None or (_access(user) == "seller" and deal.agent_id != user.agent_id):
        raise HTTPException(status_code=404, detail="Deal not found")
    return deal


def _serialize(db: Session, deal: Deal, events: bool = False) -> dict:
    client = db.get(Client, deal.client_id)
    listing = db.get(PropertyListing, deal.listing_id) if deal.listing_id else None
    agent = db.get(Agent, deal.agent_id) if deal.agent_id else None
    body = {
        "id": deal.id, "stage": deal.stage, "client_id": deal.client_id,
        "buyer_name": client.full_name if client else None,
        "buyer_phone": client.phone_number if client else None, "buyer_email": client.email if client else None,
        "listing_id": deal.listing_id, "property_title": listing.title if listing else None,
        "project_name": listing.project_name if listing else None,
        "agent_id": deal.agent_id, "seller_name": agent.full_name if agent else None,
        "inquiry_date": deal.inquiry_date, "viewing_type": deal.viewing_type, "viewing_at": deal.viewing_at,
        "reservation_date": deal.reservation_date, "reservation_status": deal.reservation_status,
        "developer_status": deal.developer_status, "closing_date": deal.closing_date,
        "lost_reason": deal.lost_reason, "reservation_transaction_id": deal.reservation_transaction_id,
        "sale_transaction_id": deal.sale_transaction_id, "notes": deal.notes, "created_by": deal.created_by,
        "created_at": deal.created_at, "updated_at": deal.updated_at,
    }
    if events:
        body["events"] = [{"id": e.id, "from_stage": e.from_stage, "to_stage": e.to_stage, "changes": e.changes,
                           "note": e.note, "actor": e.actor, "created_at": e.created_at}
                          for e in db.execute(select(DealEvent).where(DealEvent.deal_id == deal.id)
                                              .order_by(DealEvent.id)).scalars()]
    return body


@router.get("")
def list_deals(stage: str | None = None, agent_id: str | None = None, listing_id: int | None = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Deal)
    if _access(user) == "seller":
        statement = statement.where(Deal.agent_id == user.agent_id)
    elif agent_id:
        statement = statement.where(Deal.agent_id == agent_id)
    if stage:
        statement = statement.where(Deal.stage == stage.upper())
    if listing_id:
        statement = statement.where(Deal.listing_id == listing_id)
    deals = db.execute(statement.order_by(Deal.updated_at.desc())).scalars().all()
    return [_serialize(db, d) for d in deals]


@router.get("/summary")
def deal_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(Deal.stage, func.count()).group_by(Deal.stage)
    if _access(user) == "seller":
        statement = statement.where(Deal.agent_id == user.agent_id)
    counts = dict(db.execute(statement).all())
    return {"by_stage": {stage: int(counts.get(stage, 0)) for stage in STAGES}, "stages": DEAL_STAGES,
            "viewing_types": VIEWING_TYPES, "developer_statuses": DEVELOPER_STATUSES}


@router.get("/{deal_id}")
def get_deal(deal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize(db, _deal_or_404(db, deal_id, user), events=True)


@router.post("", status_code=201)
def create_deal(payload: DealCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Record an inquiry (with the viewing, when already arranged)."""
    access = _access(user)
    if db.get(PropertyListing, payload.listing_id) is None:
        raise HTTPException(status_code=422, detail="Unknown property")
    agent_id = user.agent_id if access == "seller" else payload.agent_id
    if agent_id and db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=422, detail="Unknown seller")
    if payload.client_id:
        client = db.get(Client, payload.client_id)
        if client is None or (access == "seller" and client.agent_id not in (None, user.agent_id)):
            raise HTTPException(status_code=422, detail="Unknown buyer")
    elif payload.buyer:
        client = Client(full_name=payload.buyer.full_name.strip(), phone_number=payload.buyer.phone_number,
                        email=(payload.buyer.email or "").strip().lower() or None, agent_id=agent_id,
                        status="PROSPECT", source="MANAGEMENT", sync_status="PENDING")
        db.add(client)
        db.flush()
    else:
        raise HTTPException(status_code=422, detail="Choose the buyer or enter the new buyer's name")
    stage = "VIEWING" if payload.viewing_type or payload.viewing_at else "INQUIRY"
    deal = Deal(client_id=client.client_id, listing_id=payload.listing_id, agent_id=agent_id, stage=stage,
                inquiry_date=payload.inquiry_date or date.today(), viewing_type=payload.viewing_type,
                viewing_at=payload.viewing_at, notes=payload.notes, created_by=_actor(user))
    db.add(deal)
    db.flush()
    deal_pipeline.log(db, deal, _actor(user), note="Inquiry recorded" + (" with a viewing" if stage == "VIEWING" else ""))
    record_audit(db, "DEAL_CREATED", actor=user, entity_type="deals", entity_id=deal.id,
                 details={"client_id": client.client_id, "listing_id": deal.listing_id, "agent_id": agent_id,
                          "stage": stage})
    db.commit()
    return _serialize(db, deal, events=True)


@router.put("/{deal_id}")
def update_deal(deal_id: int, payload: DealUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    deal = _deal_or_404(db, deal_id, user)
    values = payload.model_dump(exclude_unset=True)
    if _access(user) == "seller":
        refused = sorted(set(values) - {"inquiry_date", "viewing_type", "viewing_at", "notes"})
        if refused:
            raise HTTPException(status_code=403, detail=f"Sellers can't change: {', '.join(refused)}")
    elif canonical_role(user.role) not in MANAGEMENT_ROLES and set(values) - {"notes"}:
        raise HTTPException(status_code=403, detail="Only management can change deals")
    if values.get("agent_id") and db.get(Agent, values["agent_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown seller")
    if deal.stage in DEAL_CLOSED and set(values) - {"notes"}:
        raise HTTPException(status_code=409, detail="This deal is closed")
    changes = {}
    for field, value in values.items():
        if getattr(deal, field) != value:
            changes[field] = {"old": str(getattr(deal, field)) if getattr(deal, field) is not None else None,
                              "new": str(value) if value is not None else None}
            setattr(deal, field, value)
    if changes:
        to_stage = None
        if ("viewing_type" in changes or "viewing_at" in changes) and deal.stage == "INQUIRY":
            to_stage = "VIEWING"
        if changes.get("developer_status") and deal.developer_status != "NOT_STARTED" and deal.stage == "RESERVED":
            to_stage = "DEVELOPER_PROCESSING"
        deal_pipeline.log(db, deal, _actor(user), to_stage=to_stage, changes=changes)
        record_audit(db, "DEAL_UPDATED", actor=user, entity_type="deals", entity_id=deal.id, details=changes)
    db.commit()
    return _serialize(db, deal, events=True)


@router.post("/{deal_id}/stage")
def move_deal(deal_id: int, payload: StageInput, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    deal = _deal_or_404(db, deal_id, user)
    target, access = payload.stage, _access(user)
    if deal.stage in DEAL_CLOSED:
        raise HTTPException(status_code=409, detail="This deal is already closed")
    if access == "seller" and target not in SELLER_STAGES:
        raise HTTPException(status_code=403, detail="Reservation, developer processing and closing are recorded "
                                                    "by Abellar Realty")
    if access == "company" and canonical_role(user.role) not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Only management can move deals")
    if target == "LOST" and not (payload.note or "").strip():
        raise HTTPException(status_code=422, detail="Say why the buyer didn't proceed")
    if target == "RESERVED":
        deal.reservation_date = payload.reservation_date or deal.reservation_date or date.today()
        deal.reservation_status = deal.reservation_status or "RESERVED"
    if target == "DEVELOPER_PROCESSING" and deal_pipeline.ORDER.get(deal.stage, 0) < deal_pipeline.ORDER["RESERVED"]:
        raise HTTPException(status_code=409, detail="Developer processing starts after the reservation")
    if target == "CLOSED" and not deal.sale_transaction_id:
        raise HTTPException(status_code=409, detail="A deal closes when its sale is recorded (from the sale "
                                                    "document or Proceed to sale on the reservation)")
    if target == "LOST":
        deal.lost_reason = payload.note.strip()
    previous = deal.stage
    deal_pipeline.log(db, deal, _actor(user), to_stage=target, note=payload.note)
    record_audit(db, "DEAL_STAGE_CHANGED", actor=user, entity_type="deals", entity_id=deal.id,
                 details={"from": previous, "to": target, "note": payload.note})
    db.commit()
    return _serialize(db, deal, events=True)
