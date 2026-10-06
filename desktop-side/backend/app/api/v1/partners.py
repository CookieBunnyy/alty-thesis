"""Partners / Developers: the companies Abellar Realty works with.

All staff with the Partners page can view; management roles add, edit and
delete. A partner with listings can't be deleted (mark it INACTIVE instead),
so listing history keeps its developer.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.partner import PARTNER_STATUSES, PARTNER_TYPES, Partner
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/partners", tags=["Partners"])
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PartnerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    partner_type: str | None = None
    status: str | None = None
    contact_person: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("partner_type")
    @classmethod
    def known_type(cls, value):
        if value is not None and value.upper() not in PARTNER_TYPES:
            raise ValueError(f"Type must be one of: {', '.join(PARTNER_TYPES)}")
        return value.upper() if value else value

    @field_validator("status")
    @classmethod
    def known_status(cls, value):
        if value is not None and value.upper() not in PARTNER_STATUSES:
            raise ValueError("Status must be ACTIVE or INACTIVE")
        return value.upper() if value else value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value is not None and not EMAIL.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value is not None and not re.match(r"^https?://", value, re.IGNORECASE):
            value = f"https://{value}"
        return value


def _stats(db: Session, partner_ids: list[int]) -> dict[int, dict]:
    """Listings and recorded activity per partner."""
    if not partner_ids:
        return {}
    listing_rows = db.execute(
        select(PropertyListing.partner_id, func.count(),
               func.coalesce(func.sum(case((PropertyListing.status == "AVAILABLE", 1), else_=0)), 0))
        .where(PropertyListing.partner_id.in_(partner_ids)).group_by(PropertyListing.partner_id)
    ).all()
    sale = (PropertyTransaction.transaction_type == "SOLD") & (PropertyTransaction.status == "COMPLETED")
    tx_rows = db.execute(
        select(PropertyListing.partner_id,
               func.count(PropertyTransaction.transaction_id),
               func.coalesce(func.sum(case((sale, 1), else_=0)), 0),
               func.coalesce(func.sum(case((sale, PropertyTransaction.amount), else_=0)), 0))
        .join(PropertyTransaction, PropertyTransaction.property_id == PropertyListing.listing_id)
        .where(PropertyListing.partner_id.in_(partner_ids), PropertyTransaction.status != "CANCELLED")
        .group_by(PropertyListing.partner_id)
    ).all()
    stats = {pid: {"listings": 0, "available_listings": 0, "transactions": 0, "completed_sales": 0, "sales_value": 0.0}
             for pid in partner_ids}
    for pid, listings, available in listing_rows:
        stats[pid].update(listings=int(listings), available_listings=int(available))
    for pid, transactions, sales, value in tx_rows:
        stats[pid].update(transactions=int(transactions), completed_sales=int(sales), sales_value=float(value or 0))
    return stats


def _serialize(partner: Partner, stats: dict) -> dict:
    return {
        "id": partner.id, "name": partner.name, "partner_type": partner.partner_type, "status": partner.status,
        "contact_person": partner.contact_person, "email": partner.email, "phone_number": partner.phone_number,
        "website": partner.website, "address": partner.address, "notes": partner.notes,
        "created_at": partner.created_at, "updated_at": partner.updated_at,
        **stats.get(partner.id, {"listings": 0, "available_listings": 0, "transactions": 0,
                                 "completed_sales": 0, "sales_value": 0.0}),
    }


def _partner_or_404(db: Session, partner_id: int) -> Partner:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner


def _name_taken(db: Session, name: str, exclude: int | None = None) -> bool:
    statement = select(Partner.id).where(func.lower(Partner.name) == name.lower())
    if exclude is not None:
        statement = statement.where(Partner.id != exclude)
    return db.scalar(statement) is not None


@router.get("")
def list_partners(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    partners = db.execute(select(Partner).order_by(func.lower(Partner.name))).scalars().all()
    stats = _stats(db, [p.id for p in partners])
    return [_serialize(p, stats) for p in partners]


@router.get("/{partner_id}")
def get_partner(partner_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    partner = _partner_or_404(db, partner_id)
    listings = db.execute(
        select(PropertyListing).where(PropertyListing.partner_id == partner_id).order_by(PropertyListing.title)
    ).scalars().all()
    return {
        **_serialize(partner, _stats(db, [partner_id])),
        "listing_rows": [{"listing_id": l.listing_id, "title": l.title, "category": l.category, "status": l.status,
                          "price_total": float(l.price_total) if l.price_total is not None else None,
                          "village_name": l.village_name} for l in listings],
    }


@router.post("", status_code=201)
def create_partner(payload: PartnerInput, db: Session = Depends(get_db), actor: User = Depends(require_management)):
    if not payload.name:
        raise HTTPException(status_code=422, detail="Enter the partner's name")
    if _name_taken(db, payload.name):
        raise HTTPException(status_code=409, detail="A partner with that name already exists")
    partner = Partner(**{**payload.model_dump(), "status": payload.status or "ACTIVE"})
    db.add(partner)
    db.flush()
    record_audit(db, "PARTNER_CREATED", actor=actor, entity_type="partners", entity_id=partner.id,
                 details={"name": partner.name})
    db.commit()
    return _serialize(partner, _stats(db, [partner.id]))


@router.put("/{partner_id}")
def update_partner(partner_id: int, payload: PartnerInput, db: Session = Depends(get_db),
                   actor: User = Depends(require_management)):
    partner = _partner_or_404(db, partner_id)
    values = payload.model_dump(exclude_unset=True)
    if "name" in values and not values["name"]:
        raise HTTPException(status_code=422, detail="The name can't be empty")
    if values.get("name") and _name_taken(db, values["name"], exclude=partner_id):
        raise HTTPException(status_code=409, detail="A partner with that name already exists")
    if "status" in values and values["status"] is None:
        values.pop("status")
    changes = {}
    for field, value in values.items():
        if getattr(partner, field) != value:
            changes[field] = {"old": getattr(partner, field), "new": value}
            setattr(partner, field, value)
    if changes:
        record_audit(db, "PARTNER_UPDATED", actor=actor, entity_type="partners", entity_id=partner_id,
                     details={"name": partner.name, "changes": changes})
    db.commit()
    return _serialize(partner, _stats(db, [partner_id]))


@router.delete("/{partner_id}", status_code=204)
def delete_partner(partner_id: int, db: Session = Depends(get_db), actor: User = Depends(require_management)):
    partner = _partner_or_404(db, partner_id)
    linked = db.scalar(select(func.count()).select_from(PropertyListing).where(PropertyListing.partner_id == partner_id))
    if linked:
        raise HTTPException(status_code=409, detail=f"{partner.name} is the developer of {linked} listing(s). "
                                                    "Mark the partner Inactive instead, so listing history is kept.")
    record_audit(db, "PARTNER_DELETED", actor=actor, entity_type="partners", entity_id=partner_id,
                 details={"name": partner.name})
    db.delete(partner)
    db.commit()
    return Response(status_code=204)
