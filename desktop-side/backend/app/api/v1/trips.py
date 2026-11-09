"""Tripping schedule: site visits with buyers (date, pick-up, time,
subdivision, agent).

* Company staff see and manage every trip; a seller sees and manages their own.
* The board refreshes live: pages ask GET /trips/version every few seconds
  and reload only when something changed.
* "Notify buyers" puts the schedule in each buyer's website account (buyers
  with a client record) and returns a ready text message with an SMS link
  for every buyer with a phone number (no SMS gateway is used).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import COMPANY_ROLES, SELLER, canonical_role, get_current_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.trip import TRIP_STATUSES, Trip, TripBuyer, TripNotice
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/trips", tags=["Tripping schedule"])
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class BuyerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str | None = None
    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)


class TripIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_date: date
    pickup_time: str = Field(pattern=TIME_PATTERN)
    pickup_point: str = Field(min_length=1, max_length=200)
    subdivision: str = Field(min_length=1, max_length=200)
    listing_id: int | None = None
    partner_id: int | None = None
    agent_id: str | None = None
    status: str = "SCHEDULED"
    notes: str | None = Field(default=None, max_length=2000)
    buyers: list[BuyerIn] = Field(default_factory=list, max_length=30)

    @field_validator("pickup_point", "subdivision", "notes", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class NotifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str | None = Field(default=None, max_length=1000)


def _staff(user: User) -> tuple[bool, str | None]:
    """(company staff?, the seller's own agent id)."""
    role = canonical_role(user.role)
    if role in COMPANY_ROLES:
        return True, None
    if role == SELLER and user.agent_id:
        return False, user.agent_id
    raise HTTPException(status_code=403, detail="The tripping schedule is for company staff and sellers")


def _trip_or_404(db: Session, trip_id: int, user: User) -> Trip:
    trip = db.get(Trip, trip_id)
    company, own_agent = _staff(user)
    if trip is None or (not company and trip.agent_id != own_agent):
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def _when(trip: Trip) -> str:
    day = trip.trip_date.strftime("%a, %b %d, %Y").replace(" 0", " ")
    hour, minute = map(int, trip.pickup_time.split(":"))
    clock = f"{(hour % 12) or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    return f"{day} at {clock}"


def default_message(trip: Trip, buyer_name: str) -> str:
    agent = trip.agent
    contact = f" ({agent.phone_number})" if agent and agent.phone_number else ""
    status = "is confirmed" if trip.status == "CONFIRMED" else (
        "was cancelled" if trip.status == "CANCELLED" else "is scheduled")
    first = (buyer_name or "").split(" ")[0] or "there"
    if trip.status == "CANCELLED":
        return (f"Hi {first}! Your site tripping to {trip.subdivision} on {_when(trip)} {status}. "
                f"Your agent {agent.full_name if agent else ''}{contact} will contact you to reschedule. - Abellar Realty")
    return (f"Hi {first}! Your site tripping to {trip.subdivision} {status} on {_when(trip)}. "
            f"Pick-up: {trip.pickup_point}. Your agent: {agent.full_name if agent else ''}{contact}. - Abellar Realty")


def _serialize(db: Session, trip: Trip, names: dict | None = None) -> dict:
    names = names or {}
    return {
        "id": trip.id, "trip_date": trip.trip_date, "pickup_time": trip.pickup_time,
        "pickup_point": trip.pickup_point, "subdivision": trip.subdivision,
        "listing_id": trip.listing_id, "listing_title": names.get("listings", {}).get(trip.listing_id),
        "partner_id": trip.partner_id, "partner_name": names.get("partners", {}).get(trip.partner_id),
        "agent_id": trip.agent_id, "agent_name": trip.agent.full_name if trip.agent else trip.agent_id,
        "agent_phone": trip.agent.phone_number if trip.agent else None,
        "status": trip.status, "notes": trip.notes,
        "buyers": [{"id": b.id, "client_id": b.client_id, "name": b.name, "phone": b.phone,
                    "notified_at": b.notified_at} for b in trip.buyers],
        # Buyers not yet told about the latest version of the schedule.
        "needs_notice": any(b.notified_at is None or b.notified_at < trip.updated_at for b in trip.buyers),
        "created_at": trip.created_at, "updated_at": trip.updated_at, "updated_by": trip.updated_by_name,
    }


def _names(db: Session, trips: list[Trip]) -> dict:
    listing_ids = {t.listing_id for t in trips if t.listing_id}
    partner_ids = {t.partner_id for t in trips if t.partner_id}
    return {
        "listings": dict(db.execute(select(PropertyListing.listing_id, PropertyListing.title)
                                    .where(PropertyListing.listing_id.in_(listing_ids or [-1]))).all()),
        "partners": dict(db.execute(select(Partner.id, Partner.name).where(Partner.id.in_(partner_ids or [-1]))).all()),
    }


def _apply(db: Session, trip: Trip, payload: TripIn, user: User) -> None:
    company, own_agent = _staff(user)
    status = payload.status.upper()
    if status not in TRIP_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(TRIP_STATUSES)}")
    agent_id = payload.agent_id if company else own_agent
    if not agent_id or db.get(Agent, agent_id) is None:
        raise HTTPException(status_code=422, detail="Choose the agent handling the trip")
    if payload.listing_id is not None and db.get(PropertyListing, payload.listing_id) is None:
        raise HTTPException(status_code=422, detail="Unknown property")
    if payload.partner_id is not None and db.get(Partner, payload.partner_id) is None:
        raise HTTPException(status_code=422, detail="Unknown developer")
    buyers: list[TripBuyer] = []
    kept = {b.client_id or f"name:{b.name.casefold()}": b for b in trip.buyers}
    for item in payload.buyers:
        client = None
        if item.client_id:
            client = db.get(Client, item.client_id)
            if client is None or (not company and client.agent_id != own_agent):
                raise HTTPException(status_code=422, detail="Unknown buyer")
        name = (client.full_name if client else (item.name or "").strip())
        if not name:
            raise HTTPException(status_code=422, detail="Each buyer needs a name")
        phone = (item.phone or "").strip() or (client.phone_number if client else None)
        key = client.client_id if client else f"name:{name.casefold()}"
        existing = kept.get(key)
        if existing is not None:
            existing.name, existing.phone = name, phone
            buyers.append(existing)
        else:
            buyers.append(TripBuyer(client_id=client.client_id if client else None, name=name, phone=phone))
    trip.trip_date, trip.pickup_time = payload.trip_date, payload.pickup_time
    trip.pickup_point, trip.subdivision = payload.pickup_point, payload.subdivision
    trip.listing_id, trip.partner_id, trip.agent_id = payload.listing_id, payload.partner_id, agent_id
    trip.status, trip.notes = status, payload.notes or None
    trip.buyers = buyers
    trip.updated_by_name = user.full_name or user.username
    trip.updated_at = datetime.utcnow()


@router.get("")
def list_trips(start: date | None = Query(default=None, alias="from"), end: date | None = Query(default=None, alias="to"),
               agent_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    company, own_agent = _staff(user)
    start = start or (date.today() - timedelta(days=7))
    query = select(Trip).where(Trip.trip_date >= start)
    if end:
        query = query.where(Trip.trip_date <= end)
    if not company:
        query = query.where(Trip.agent_id == own_agent)
    elif agent_id:
        query = query.where(Trip.agent_id == agent_id)
    trips = list(db.execute(query.order_by(Trip.trip_date, Trip.pickup_time)).scalars().unique())
    names = _names(db, trips)
    return {"trips": [_serialize(db, trip, names) for trip in trips], "version": _version(db, own_agent)}


def _version(db: Session, own_agent: str | None) -> str:
    query = select(func.count(Trip.id), func.max(Trip.updated_at))
    if own_agent:
        query = query.where(Trip.agent_id == own_agent)
    count, latest = db.execute(query).one()
    return f"{count}:{latest.isoformat() if latest else '-'}"


@router.get("/version")
def trips_version(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cheap change check for the live board (count and last change)."""
    _, own_agent = _staff(user)
    return {"version": _version(db, own_agent)}


@router.get("/buyer-options")
def buyer_options(q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Buyers to add to a trip: every client for company staff, a seller's own clients."""
    company, own_agent = _staff(user)
    query = select(Client)
    if not company:
        query = query.where(Client.agent_id == own_agent)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Client.full_name.ilike(like), Client.phone_number.ilike(like)))
    rows = db.execute(query.order_by(Client.full_name).limit(50)).scalars()
    with_account = set(db.scalars(select(User.client_id).where(User.client_id.is_not(None))))
    return [{"client_id": c.client_id, "name": c.full_name, "phone": c.phone_number,
             "has_account": c.client_id in with_account} for c in rows]


@router.post("", status_code=201)
def create_trip(payload: TripIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = Trip(created_by_user_id=user.id)
    _apply(db, trip, payload, user)
    db.add(trip)
    db.flush()
    record_audit(db, "TRIP_SCHEDULED", actor=user, entity_type="trips", entity_id=trip.id,
                 details={"date": trip.trip_date.isoformat(), "subdivision": trip.subdivision,
                          "agent_id": trip.agent_id, "buyers": len(trip.buyers)})
    db.commit()
    db.refresh(trip)
    return _serialize(db, trip, _names(db, [trip]))


@router.put("/{trip_id}")
def update_trip(trip_id: int, payload: TripIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _trip_or_404(db, trip_id, user)
    before = {"date": trip.trip_date.isoformat(), "time": trip.pickup_time, "status": trip.status}
    _apply(db, trip, payload, user)
    record_audit(db, "TRIP_UPDATED", actor=user, entity_type="trips", entity_id=trip.id,
                 details={"before": before, "after": {"date": trip.trip_date.isoformat(), "time": trip.pickup_time,
                                                      "status": trip.status}})
    db.commit()
    db.refresh(trip)
    return _serialize(db, trip, _names(db, [trip]))


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str


@router.post("/{trip_id}/status")
def set_status(trip_id: int, payload: StatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _trip_or_404(db, trip_id, user)
    status = payload.status.upper()
    if status not in TRIP_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(TRIP_STATUSES)}")
    old, trip.status = trip.status, status
    trip.updated_by_name, trip.updated_at = user.full_name or user.username, datetime.utcnow()
    record_audit(db, "TRIP_STATUS_CHANGED", actor=user, entity_type="trips", entity_id=trip.id,
                 details={"old": old, "new": status})
    db.commit()
    db.refresh(trip)
    return _serialize(db, trip, _names(db, [trip]))


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _trip_or_404(db, trip_id, user)
    record_audit(db, "TRIP_DELETED", actor=user, entity_type="trips", entity_id=trip.id,
                 details={"date": trip.trip_date.isoformat(), "subdivision": trip.subdivision})
    db.delete(trip)
    db.commit()
    return Response(status_code=204)


@router.post("/{trip_id}/notify")
def notify_buyers(trip_id: int, payload: NotifyIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """Tell the buyers about the schedule (or a change to it)."""
    trip = _trip_or_404(db, trip_id, user)
    if not trip.buyers:
        raise HTTPException(status_code=409, detail="Add the buyers joining this trip first")
    now = datetime.utcnow()
    sent_in_app, messages = 0, []
    for buyer in trip.buyers:
        text = (payload.message or "").strip() or default_message(trip, buyer.name)
        if buyer.client_id:
            db.add(TripNotice(trip_id=trip.id, client_id=buyer.client_id, message=text,
                              sent_by_name=user.full_name or user.username))
            sent_in_app += 1
        buyer.notified_at = now
        phone = "".join(ch for ch in (buyer.phone or "") if ch.isdigit() or ch == "+")
        messages.append({"name": buyer.name, "phone": buyer.phone, "in_app": bool(buyer.client_id), "text": text,
                         "sms_link": f"sms:{phone}?body={quote(text)}" if phone else None})
    record_audit(db, "TRIP_BUYERS_NOTIFIED", actor=user, entity_type="trips", entity_id=trip.id,
                 details={"buyers": len(trip.buyers), "in_app": sent_in_app})
    db.commit()
    return {"sent_in_app": sent_in_app, "messages": messages}
