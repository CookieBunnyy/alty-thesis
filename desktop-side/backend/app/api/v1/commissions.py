"""Commission records (sales and rentals) and configurable structures.

Company staff can read them; the Administrator records,
approves and releases them; the Filing Manager and management attach the
supporting commission vouchers. A seller sees their own records only when
management has turned that on for them (``agents.commission_visible``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_company_user, get_seller_user, require_filing, require_management
from app.models.agent import Agent
from app.models.commission import (APPROVAL_STATUSES, COMMISSION_BASES, COMMISSION_KINDS, COMMISSION_STATUSES,
                                   CommissionRecord, CommissionStructure)
from app.models.document import Document
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services import commissions
from app.services.audit import record_audit

router = APIRouter(prefix="/commissions", tags=["Commissions"])
seller_router = APIRouter(prefix="/seller", tags=["Seller"])

Money = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class StructureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = None
    partner_id: int | None = None
    listing_id: int | None = None
    basis: str | None = None
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=3)
    fixed_amount: Decimal | None = Money
    months_of_rent: Decimal | None = Field(default=None, ge=0, le=60, max_digits=5, decimal_places=2)
    seller_share_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=6, decimal_places=3)
    effective_from: date | None = None
    effective_until: date | None = None
    is_active: bool | None = None
    notes: str | None = None

    @field_validator("kind")
    @classmethod
    def known_kind(cls, value):
        if value is not None and value.upper() not in COMMISSION_KINDS:
            raise ValueError("Kind must be SALE or RENTAL")
        return value.upper() if value else value

    @field_validator("basis")
    @classmethod
    def known_basis(cls, value):
        if value is not None and value.upper() not in COMMISSION_BASES:
            raise ValueError(f"Basis must be one of: {', '.join(COMMISSION_BASES)}")
        return value.upper() if value else value


class RecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str | None = None
    transaction_id: str | None = None
    agent_id: str | None = None
    listing_id: int | None = None
    property_description: str | None = Field(default=None, max_length=500)
    lessor_name: str | None = Field(default=None, max_length=200)
    lessee_name: str | None = Field(default=None, max_length=200)
    monthly_rent: Decimal | None = Money
    lease_term_months: int | None = Field(default=None, ge=1, le=600)
    basis_amount: Decimal | None = Money
    structure_id: int | None = None
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=3)
    amount: Decimal | None = Money
    seller_share_amount: Decimal | None = Money
    agreement_reference: str | None = Field(default=None, max_length=120)
    agreement_notes: str | None = None
    record_date: date | None = None

    @field_validator("kind")
    @classmethod
    def known_kind(cls, value):
        if value is not None and value.upper() not in COMMISSION_KINDS:
            raise ValueError("Kind must be SALE or RENTAL")
        return value.upper() if value else value


class ApprovalInput(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: str | None = Field(default=None, max_length=1000)


class ReleaseInput(BaseModel):
    released_on: date
    amount: Decimal | None = Money


class VoucherInput(BaseModel):
    document_id: int | None = None


class PreviewInput(BaseModel):
    structure_id: int
    basis_amount: Decimal | None = Money
    monthly_rent: Decimal | None = Money


def _actor(user: User) -> str:
    return user.full_name or user.username


def _num(value) -> float | None:
    return float(value) if value is not None else None


def _structure(s: CommissionStructure, partners: dict[int, str]) -> dict:
    return {"id": s.id, "name": s.name, "kind": s.kind, "partner_id": s.partner_id,
            "partner_name": partners.get(s.partner_id), "listing_id": s.listing_id, "basis": s.basis,
            "rate_percent": _num(s.rate_percent), "fixed_amount": _num(s.fixed_amount),
            "months_of_rent": _num(s.months_of_rent), "seller_share_percent": _num(s.seller_share_percent),
            "effective_from": s.effective_from, "effective_until": s.effective_until, "is_active": s.is_active,
            "notes": s.notes, "created_by": s.created_by, "updated_at": s.updated_at}


def _record(db: Session, r: CommissionRecord) -> dict:
    agent = db.get(Agent, r.agent_id) if r.agent_id else None
    listing = db.get(PropertyListing, r.listing_id) if r.listing_id else None
    transaction = db.get(PropertyTransaction, r.transaction_id) if r.transaction_id else None
    voucher = db.get(Document, r.voucher_document_id) if r.voucher_document_id else None
    return {
        "id": r.id, "kind": r.kind, "transaction_id": r.transaction_id,
        "transaction_date": transaction.transaction_date if transaction else None,
        "buyer_name": transaction.client.full_name if transaction and transaction.client else None,
        "agent_id": r.agent_id, "seller_name": agent.full_name if agent else None,
        "listing_id": r.listing_id, "property_title": listing.title if listing else None,
        "project_name": listing.project_name if listing else None,
        "property_description": r.property_description, "lessor_name": r.lessor_name, "lessee_name": r.lessee_name,
        "monthly_rent": _num(r.monthly_rent), "lease_term_months": r.lease_term_months,
        "basis_amount": _num(r.basis_amount), "structure_id": r.structure_id, "rate_percent": _num(r.rate_percent),
        "amount": _num(r.amount), "seller_share_amount": _num(r.seller_share_amount),
        "agreement_reference": r.agreement_reference, "agreement_notes": r.agreement_notes,
        "status": r.status, "approval_status": r.approval_status, "approved_by": r.approved_by,
        "approved_at": r.approved_at, "approval_note": r.approval_note,
        "released_amount": _num(r.released_amount), "released_on": r.released_on,
        "voucher_document_id": r.voucher_document_id,
        "voucher": {"id": voucher.id, "document_id": voucher.document_id, "name": voucher.document_name} if voucher else None,
        "record_date": r.record_date, "created_by": r.created_by, "created_at": r.created_at, "updated_at": r.updated_at,
    }


def _partners(db: Session) -> dict[int, str]:
    return dict(db.execute(select(Partner.id, Partner.name)).all())


def _record_or_404(db: Session, record_id: int) -> CommissionRecord:
    record = db.get(CommissionRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Commission record not found")
    return record


# ---- structures ---------------------------------------------------------------------

@router.get("/structures")
def list_structures(db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    partners = _partners(db)
    return [_structure(s, partners) for s in db.execute(select(CommissionStructure)
                                                        .order_by(CommissionStructure.name)).scalars()]


@router.post("/structures", status_code=201)
def create_structure(payload: StructureInput, db: Session = Depends(get_db), user: User = Depends(require_management)):
    if not payload.name:
        raise HTTPException(status_code=422, detail="Name the commission structure")
    values = payload.model_dump()
    values["kind"] = values["kind"] or "SALE"
    values["basis"] = values["basis"] or "AS_AGREED"
    values["is_active"] = True if values["is_active"] is None else values["is_active"]
    structure = CommissionStructure(**values, created_by=_actor(user))
    db.add(structure)
    db.flush()
    record_audit(db, "COMMISSION_STRUCTURE_CREATED", actor=user, entity_type="commission_structures",
                 entity_id=structure.id, details={k: str(v) for k, v in values.items() if v is not None})
    db.commit()
    return _structure(structure, _partners(db))


@router.put("/structures/{structure_id}")
def update_structure(structure_id: int, payload: StructureInput, db: Session = Depends(get_db),
                     user: User = Depends(require_management)):
    structure = db.get(CommissionStructure, structure_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Commission structure not found")
    changes = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in {"name", "kind", "basis", "is_active"} and value is None:
            continue
        if getattr(structure, field) != value:
            changes[field] = {"old": str(getattr(structure, field)), "new": str(value)}
            setattr(structure, field, value)
    if changes:
        record_audit(db, "COMMISSION_STRUCTURE_UPDATED", actor=user, entity_type="commission_structures",
                     entity_id=structure_id, details=changes)
    db.commit()
    return _structure(structure, _partners(db))


@router.post("/preview")
def preview(payload: PreviewInput, db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    """What a structure suggests for an amount (nothing is saved)."""
    structure = db.get(CommissionStructure, payload.structure_id)
    if structure is None:
        raise HTTPException(status_code=404, detail="Commission structure not found")
    amount = commissions.suggest(structure, payload.basis_amount, payload.monthly_rent)
    share = (amount * Decimal(structure.seller_share_percent) / 100).quantize(commissions.CENT) \
        if amount is not None and structure.seller_share_percent is not None else None
    return {"amount": _num(amount), "seller_share_amount": _num(share), "rate_percent": _num(structure.rate_percent)}


# ---- records ----------------------------------------------------------------------------

@router.get("")
def list_records(kind: str | None = None, status: str | None = None, agent_id: str | None = None,
                 db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    statement = select(CommissionRecord)
    if kind:
        statement = statement.where(CommissionRecord.kind == kind.upper())
    if status:
        statement = statement.where(CommissionRecord.status == status.upper())
    if agent_id:
        statement = statement.where(CommissionRecord.agent_id == agent_id)
    return [_record(db, r) for r in db.execute(statement.order_by(CommissionRecord.record_date.desc(),
                                                                   CommissionRecord.id.desc())).scalars()]


@router.get("/summary")
def summary(db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    rows = db.execute(select(CommissionRecord.approval_status, CommissionRecord.status, func.count(),
                             func.coalesce(func.sum(CommissionRecord.amount), 0))
                      .group_by(CommissionRecord.approval_status, CommissionRecord.status)).all()
    total = lambda pred: (sum(int(c) for a, s, c, _ in rows if pred(a, s)),  # noqa: E731
                          float(sum(v for a, s, _, v in rows if pred(a, s))))
    pending = total(lambda a, s: a == "PENDING" and s != "CANCELLED")
    unreleased = total(lambda a, s: a == "APPROVED" and s in {"UNRELEASED", "PARTIALLY_RELEASED"})
    released = total(lambda a, s: s == "RELEASED")
    without_voucher = db.scalar(select(func.count()).select_from(CommissionRecord).where(
        CommissionRecord.voucher_document_id.is_(None), CommissionRecord.status != "CANCELLED")) or 0
    return {"pending_approval": {"count": pending[0], "amount": pending[1]},
            "approved_unreleased": {"count": unreleased[0], "amount": unreleased[1]},
            "released": {"count": released[0], "amount": released[1]},
            "without_voucher": int(without_voucher),
            "kinds": COMMISSION_KINDS, "statuses": COMMISSION_STATUSES, "approval_statuses": APPROVAL_STATUSES,
            "bases": COMMISSION_BASES}


@router.get("/{record_id}")
def get_record(record_id: int, db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    return _record(db, _record_or_404(db, record_id))


def _apply(db: Session, record: CommissionRecord, values: dict) -> dict:
    """Validate links and fill what the linked records already say."""
    if values.get("transaction_id"):
        transaction = db.get(PropertyTransaction, values["transaction_id"])
        if transaction is None or transaction.status == "CANCELLED":
            raise HTTPException(status_code=422, detail="Choose a recorded, not cancelled, transaction")
        values.setdefault("agent_id", transaction.agent_id)
        values["agent_id"] = values["agent_id"] or transaction.agent_id
        values["listing_id"] = values.get("listing_id") or transaction.property_id
        values["basis_amount"] = values.get("basis_amount") or transaction.amount
    if values.get("agent_id") and db.get(Agent, values["agent_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown seller")
    if values.get("listing_id") and db.get(PropertyListing, values["listing_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown property")
    structure = db.get(CommissionStructure, values["structure_id"]) if values.get("structure_id") else None
    if values.get("structure_id") and structure is None:
        raise HTTPException(status_code=422, detail="Unknown commission structure")
    if values.get("amount") is None and structure is not None:
        values["amount"] = commissions.suggest(structure, values.get("basis_amount") or record.basis_amount,
                                               values.get("monthly_rent") or record.monthly_rent)
        values["rate_percent"] = values.get("rate_percent") or structure.rate_percent
    changes = {}
    for field, value in values.items():
        if getattr(record, field) != value:
            changes[field] = {"old": str(getattr(record, field)), "new": str(value)}
            setattr(record, field, value)
    return changes


@router.post("", status_code=201)
def create_record(payload: RecordInput, db: Session = Depends(get_db), user: User = Depends(require_management)):
    values = {k: v for k, v in payload.model_dump().items() if v is not None}
    values["kind"] = values.get("kind") or "SALE"
    if values["kind"] == "SALE" and not values.get("transaction_id") and not values.get("listing_id"):
        raise HTTPException(status_code=422, detail="Link the sale's transaction or property")
    if values["kind"] == "RENTAL" and not (values.get("listing_id") or values.get("property_description")):
        raise HTTPException(status_code=422, detail="Describe the rented property")
    record = CommissionRecord(created_by=_actor(user), record_date=values.pop("record_date", None) or date.today(),
                              amount=Decimal(0))
    _apply(db, record, values)
    if values.get("amount") is None and record.amount == 0:
        raise HTTPException(status_code=422, detail="Enter the agreed commission amount (or choose a structure "
                                                    "that gives one)")
    db.add(record)
    db.flush()
    record_audit(db, "COMMISSION_RECORDED", actor=user, entity_type="commission_records", entity_id=record.id,
                 details={"kind": record.kind, "amount": str(record.amount), "agent_id": record.agent_id,
                          "transaction_id": record.transaction_id})
    db.commit()
    return _record(db, record)


@router.put("/{record_id}")
def update_record(record_id: int, payload: RecordInput, db: Session = Depends(get_db),
                  user: User = Depends(require_management)):
    record = _record_or_404(db, record_id)
    if record.status in {"RELEASED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="Released or cancelled commissions can't be edited")
    changes = _apply(db, record, payload.model_dump(exclude_unset=True))
    if changes and record.approval_status == "APPROVED" and {"amount", "rate_percent", "basis_amount"} & set(changes):
        record.approval_status, record.approved_by, record.approved_at = "PENDING", None, None
        changes["approval_status"] = {"old": "APPROVED", "new": "PENDING (amount changed)"}
    if changes:
        record_audit(db, "COMMISSION_UPDATED", actor=user, entity_type="commission_records", entity_id=record_id,
                     details=changes)
    db.commit()
    return _record(db, record)


@router.post("/{record_id}/approval")
def decide(record_id: int, payload: ApprovalInput, db: Session = Depends(get_db),
           user: User = Depends(require_management)):
    record = _record_or_404(db, record_id)
    if record.status in {"RELEASED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="This commission is already released or cancelled")
    if payload.decision == "REJECTED" and not (payload.note or "").strip():
        raise HTTPException(status_code=422, detail="Give the reason for rejecting")
    record.approval_status, record.approval_note = payload.decision, payload.note
    record.approved_by, record.approved_at = _actor(user), datetime.utcnow()
    record_audit(db, "COMMISSION_" + payload.decision, actor=user, entity_type="commission_records",
                 entity_id=record_id, details={"note": payload.note})
    db.commit()
    return _record(db, record)


@router.post("/{record_id}/release")
def release(record_id: int, payload: ReleaseInput, db: Session = Depends(get_db),
            user: User = Depends(require_management)):
    """Record that the commission (or part of it) was paid out."""
    record = _record_or_404(db, record_id)
    if record.approval_status != "APPROVED":
        raise HTTPException(status_code=409, detail="Approve the commission before releasing it")
    if record.status in {"RELEASED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail="This commission is already released or cancelled")
    if payload.released_on > date.today():
        raise HTTPException(status_code=422, detail="The release date can't be in the future")
    # No amount given: release whatever is still unpaid.
    amount = payload.amount if payload.amount is not None else Decimal(record.amount) - Decimal(record.released_amount or 0)
    paid = Decimal(record.released_amount or 0) + Decimal(amount)
    if paid > Decimal(record.amount):
        raise HTTPException(status_code=422, detail="That is more than the commission amount")
    record.released_amount, record.released_on = paid, payload.released_on
    record.status = "RELEASED" if paid >= Decimal(record.amount) else "PARTIALLY_RELEASED"
    record_audit(db, "COMMISSION_RELEASED", actor=user, entity_type="commission_records", entity_id=record_id,
                 details={"amount": str(amount), "released_on": payload.released_on.isoformat()})
    db.commit()
    return _record(db, record)


@router.post("/{record_id}/cancel")
def cancel(record_id: int, payload: ApprovalInput | None = None, db: Session = Depends(get_db),
           user: User = Depends(require_management)):
    record = _record_or_404(db, record_id)
    if record.status == "RELEASED":
        raise HTTPException(status_code=409, detail="A released commission can't be cancelled")
    record.status = "CANCELLED"
    record_audit(db, "COMMISSION_CANCELLED", actor=user, entity_type="commission_records", entity_id=record_id)
    db.commit()
    return _record(db, record)


@router.put("/{record_id}/voucher")
def attach_voucher(record_id: int, payload: VoucherInput, db: Session = Depends(get_db),
                   user: User = Depends(require_filing)):
    """Link (or unlink) the supporting commission voucher document."""
    record = _record_or_404(db, record_id)
    if payload.document_id is not None and db.get(Document, payload.document_id) is None:
        raise HTTPException(status_code=422, detail="Unknown document")
    record.voucher_document_id = payload.document_id
    record_audit(db, "COMMISSION_VOUCHER_LINKED", actor=user, entity_type="commission_records", entity_id=record_id,
                 details={"document_id": payload.document_id})
    db.commit()
    return _record(db, record)


# ---- the seller's own -----------------------------------------------------------------

@seller_router.get("/commissions")
def my_commissions(db: Session = Depends(get_db), user: User = Depends(get_seller_user)):
    """My commission records, when management has allowed me to see them."""
    agent = db.get(Agent, user.agent_id)
    if agent is None or not agent.commission_visible:
        raise HTTPException(status_code=403, detail="Your commission records aren't shared with you yet. "
                                                    "Ask Abellar Realty's management.")
    rows = db.execute(select(CommissionRecord).where(CommissionRecord.agent_id == user.agent_id,
                                                     CommissionRecord.status != "CANCELLED")
                      .order_by(CommissionRecord.record_date.desc())).scalars()
    keep = ("id", "kind", "transaction_date", "buyer_name", "property_title", "project_name", "property_description",
            "amount", "seller_share_amount", "status", "approval_status", "released_amount", "released_on",
            "record_date", "agreement_reference")
    return [{k: v for k, v in _record(db, r).items() if k in keep} for r in rows]
