from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.partner import Partner
from app.models.payment import TransactionPayment
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.transaction import (
    PaymentCreate,
    SaleCompletion,
    TransactionCancel,
    TransactionResponse,
    TransactionSummary,
    TransactionSyncResult,
)
from app.services import closing_costs
from app.services.audit import record_audit
from app.services.payment_plan import build_plan
from app.services.client_sync import cancel_reservation
from app.services.cloud_sync import try_push_pending
from app.services.entity_matching import (
    find_client_by_external_reference,
    find_transaction_by_reference,
)
from app.services.transaction_queries import WITH_PARTIES
from app.services.transaction_sync import sync_transactions

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Revenue = completed sales. Reservations become COMPLETED when the sale is
# recorded, so counting every COMPLETED row would double-count.
REVENUE_CONDITION = (PropertyTransaction.transaction_type == "SOLD") & (
    PropertyTransaction.status == "COMPLETED"
)


def _response(transaction: PropertyTransaction) -> dict:
    return {
        "transaction_id": str(transaction.transaction_id),
        "external_transaction_id": transaction.external_transaction_id,
        "client_id": str(transaction.client_id),
        "client_name": transaction.client.full_name,
        "property_id": transaction.property_id,
        "property_external_id": transaction.property_listing.external_listing_id,
        "property_title": transaction.property_listing.title,
        "agent_id": transaction.agent_id,
        "agent_name": transaction.agent.full_name,
        "transaction_type": transaction.transaction_type,
        "transaction_date": transaction.transaction_date,
        "amount": transaction.amount,
        "status": transaction.status,
        "notes": transaction.notes,
        "cancellation_reason": transaction.cancellation_reason,
        "cancelled_at": transaction.cancelled_at,
        "cancelled_by": transaction.cancelled_by,
        "source": transaction.source,
        "source_document_id": transaction.source_document_id,
        "sync_status": transaction.sync_status,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


@router.get("", response_model=list[TransactionResponse])
def get_transactions(
    property_id: int | None = None,
    client_id: str | None = None,
    agent_id: str | None = None,
    transaction_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(PropertyTransaction).options(*WITH_PARTIES)
    if property_id is not None:
        statement = statement.where(PropertyTransaction.property_id == property_id)
    if client_id:
        client = find_client_by_external_reference(db, client_id)
        if client is None:
            raise HTTPException(status_code=404, detail="Client not found")
        statement = statement.where(PropertyTransaction.client_id == client.client_id)
    if agent_id:
        statement = statement.where(PropertyTransaction.agent_id == agent_id)
    if transaction_type:
        statement = statement.where(PropertyTransaction.transaction_type == transaction_type.upper())
    if status:
        statement = statement.where(PropertyTransaction.status == status.upper())
    rows = db.execute(
        statement.order_by(PropertyTransaction.transaction_date.desc(),
                           PropertyTransaction.created_at.desc())
        .offset(offset).limit(limit)
    ).scalars().all()
    return [_response(item) for item in rows]


@router.get("/summary", response_model=TransactionSummary)
def get_transaction_summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    total, reserved, completed_sales, cancelled, revenue = db.execute(
        select(
            func.count(PropertyTransaction.transaction_id),
            func.coalesce(func.sum(case((PropertyTransaction.status == "RESERVED", 1), else_=0)), 0),
            func.coalesce(func.sum(case((REVENUE_CONDITION, 1), else_=0)), 0),
            func.coalesce(func.sum(case((PropertyTransaction.status == "CANCELLED", 1), else_=0)), 0),
            func.coalesce(func.sum(case((REVENUE_CONDITION, PropertyTransaction.amount), else_=0)), 0),
        )
    ).one()
    return {
        "total": int(total),
        "reserved": int(reserved),
        "completed": int(completed_sales),
        "cancelled": int(cancelled),
        "amount_total": revenue,
    }


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    transaction = find_transaction_by_reference(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _response(transaction)


@router.post("/{transaction_id}/cancel", response_model=TransactionResponse)
def cancel_transaction(transaction_id: str, payload: TransactionCancel, db: Session = Depends(get_db),
                       user: User = Depends(require_management)):
    """Cancel an open reservation, with the reason. The property returns to
    AVAILABLE when no other open reservation holds it. Sales can't be cancelled
    here; completed records keep their history."""
    transaction = find_transaction_by_reference(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.transaction_type != "RESERVED" or transaction.status != "RESERVED":
        raise HTTPException(status_code=409, detail="Only an open reservation can be cancelled")
    reason = payload.reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Please give the reason for cancelling")
    cancel_reservation(transaction, reason, user.full_name or user.username)
    listing = transaction.property_listing
    still_reserved = db.scalar(select(func.count()).select_from(PropertyTransaction).where(
        PropertyTransaction.property_id == listing.listing_id,
        PropertyTransaction.transaction_type == "RESERVED",
        PropertyTransaction.status == "RESERVED",
        PropertyTransaction.transaction_id != transaction.transaction_id,
    ))
    property_note = None
    if listing.status == "RESERVED" and not still_reserved:
        listing.status = "AVAILABLE"
        listing.status_changed_at = datetime.utcnow()
        listing.sync_status = "PENDING"
        property_note = "property returned to AVAILABLE"
    record_audit(db, "TRANSACTION_CANCELLED", actor=user, entity_type="transactions",
                 entity_id=str(transaction.transaction_id),
                 details={"reason": reason, "client": transaction.client.full_name,
                          "property": listing.title, "consequence": property_note})
    db.commit()
    try_push_pending(db)
    db.refresh(transaction)
    return _response(transaction)


def _reservation_or_404(db: Session, transaction_id: str) -> PropertyTransaction:
    transaction = find_transaction_by_reference(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def _payments(db: Session, transaction: PropertyTransaction) -> list[TransactionPayment]:
    return list(db.execute(select(TransactionPayment)
                           .where(TransactionPayment.transaction_id == transaction.transaction_id)
                           .order_by(TransactionPayment.paid_at, TransactionPayment.id)).scalars())


def _plan_response(db: Session, transaction: PropertyTransaction) -> dict:
    payments = _payments(db, transaction)
    return {
        "plan": build_plan(transaction, payments),
        "payments": [{"id": p.id, "amount": p.amount, "paid_at": p.paid_at, "note": p.note,
                      "recorded_by": p.recorded_by, "created_at": p.created_at} for p in payments],
    }


@router.get("/{transaction_id}/payment-plan")
def get_payment_plan(transaction_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """A reservation's payment schedule (from the listing's terms) and the payments recorded for it."""
    return _plan_response(db, _reservation_or_404(db, transaction_id))


@router.get("/{transaction_id}/cost-breakdown")
def get_cost_breakdown(transaction_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """The property price plus the estimated taxes and fees of buying it
    (transfer tax, documentary stamp tax, registration, notarial, VAT)."""
    transaction = _reservation_or_404(db, transaction_id)
    listing = transaction.property_listing
    price = (listing.price_total if listing is not None and listing.price_total else None) or transaction.amount
    if transaction.transaction_type == "SOLD" and transaction.amount:
        price = transaction.amount  # the recorded sale price
    partner = db.get(Partner, listing.partner_id) if listing is not None and listing.partner_id else None
    return closing_costs.breakdown(listing, Decimal(price or 0), partner)


@router.post("/{transaction_id}/payments", status_code=201)
def add_payment(transaction_id: str, payload: PaymentCreate, db: Session = Depends(get_db),
                user: User = Depends(require_management)):
    transaction = _reservation_or_404(db, transaction_id)
    if transaction.transaction_type != "RESERVED" or transaction.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Payments are recorded on a reservation that isn't cancelled")
    if payload.paid_at > date.today() + timedelta(days=1):
        raise HTTPException(status_code=422, detail="The payment date can't be in the future")
    payment = TransactionPayment(transaction_id=transaction.transaction_id, amount=payload.amount,
                                 paid_at=payload.paid_at, note=(payload.note or "").strip() or None,
                                 recorded_by=user.full_name or user.username)
    db.add(payment)
    db.flush()
    record_audit(db, "PAYMENT_RECORDED", actor=user, entity_type="transactions",
                 entity_id=str(transaction.transaction_id),
                 details={"amount": str(payload.amount), "paid_at": payload.paid_at.isoformat(),
                          "client": transaction.client.full_name, "property": transaction.property_listing.title})
    db.commit()
    return _plan_response(db, transaction)


@router.delete("/{transaction_id}/payments/{payment_id}")
def delete_payment(transaction_id: str, payment_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_management)):
    transaction = _reservation_or_404(db, transaction_id)
    payment = db.get(TransactionPayment, payment_id)
    if payment is None or payment.transaction_id != transaction.transaction_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    record_audit(db, "PAYMENT_DELETED", actor=user, entity_type="transactions",
                 entity_id=str(transaction.transaction_id),
                 details={"amount": str(payment.amount), "paid_at": payment.paid_at.isoformat()})
    db.delete(payment)
    db.commit()
    return _plan_response(db, transaction)


@router.post("/{transaction_id}/complete-sale", response_model=TransactionResponse)
def complete_sale(transaction_id: str, payload: SaleCompletion, db: Session = Depends(get_db),
                  user: User = Depends(require_management)):
    """The reservation proceeded to a purchase: record the sale. Same rules as a
    sale read from a document: the reservation becomes COMPLETED (kept as
    history), the property and the client become SOLD."""
    reservation = _reservation_or_404(db, transaction_id)
    if reservation.transaction_type != "RESERVED" or reservation.status != "RESERVED":
        raise HTTPException(status_code=409, detail="Only an open reservation can proceed to a sale")
    listing = reservation.property_listing
    if listing.status not in {"AVAILABLE", "RESERVED"}:
        raise HTTPException(status_code=409, detail=f"The property is {listing.status}; it can't be sold")
    others = db.scalar(select(func.count()).select_from(PropertyTransaction).where(
        PropertyTransaction.property_id == listing.listing_id,
        PropertyTransaction.transaction_type == "RESERVED",
        PropertyTransaction.status == "RESERVED",
        PropertyTransaction.client_id != reservation.client_id,
    ))
    if others:
        raise HTTPException(status_code=409, detail="Another client also holds a reservation on this property")
    amount = payload.amount if payload.amount is not None else (
        Decimal(listing.price_total) if listing.price_total else None)
    if amount is None:
        raise HTTPException(status_code=422, detail="Enter the sale amount (the property has no price on record)")
    sold_day = payload.sale_date or date.today()
    if sold_day > date.today() + timedelta(days=1):
        raise HTTPException(status_code=422, detail="The sale date can't be in the future")
    if sold_day < reservation.transaction_date.date() - timedelta(days=1):
        raise HTTPException(status_code=422, detail="The sale can't be dated before its reservation")
    # Noon Philippine time on that day (date-only records stay on the right day).
    sold_at = datetime.combine(sold_day, time(12, 0), tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)

    sale = PropertyTransaction(
        client_id=reservation.client_id, property_id=listing.listing_id, agent_id=reservation.agent_id,
        transaction_type="SOLD", status="COMPLETED", transaction_date=sold_at, amount=amount,
        notes=(payload.note or "").strip() or f"Sale recorded from reservation {reservation.transaction_id}",
        source="MANAGEMENT", sync_status="PENDING",
    )
    db.add(sale)
    reservation.status = "COMPLETED"
    reservation.sync_status = "PENDING"
    old_status = listing.status
    listing.status = "SOLD"
    listing.status_changed_at = datetime.utcnow()
    listing.sync_status = "PENDING"
    client = reservation.client
    client.transaction_type = "SOLD"
    client.status = "SOLD"
    client.transaction_date = sold_at
    client.property_id = listing.listing_id
    client.sync_status = "PENDING"
    db.flush()
    record_audit(db, "RESERVATION_COMPLETED_AS_SALE", actor=user, entity_type="transactions",
                 entity_id=str(sale.transaction_id),
                 details={"reservation": str(reservation.transaction_id), "amount": str(amount),
                          "client": client.full_name, "property": listing.title,
                          "property_status": {"old": old_status, "new": "SOLD"}})
    db.commit()
    try_push_pending(db)
    db.refresh(sale)
    return _response(sale)


@router.post("/sync", response_model=TransactionSyncResult)
def sync_transaction_records(db: Session = Depends(get_db), user: User = Depends(require_management)):
    result = sync_transactions(db)
    record_audit(db, "TRANSACTIONS_SYNCED", actor=user, entity_type="transactions",
                 details={key: value for key, value in result.items() if key != "last_synced_at"})
    db.commit()
    return result
