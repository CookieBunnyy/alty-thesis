from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.transaction import (
    TransactionCancel,
    TransactionResponse,
    TransactionSummary,
    TransactionSyncResult,
)
from app.services.audit import record_audit
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


@router.post("/sync", response_model=TransactionSyncResult)
def sync_transaction_records(db: Session = Depends(get_db), user: User = Depends(require_management)):
    result = sync_transactions(db)
    record_audit(db, "TRANSACTIONS_SYNCED", actor=user, entity_type="transactions",
                 details={key: value for key, value in result.items() if key != "last_synced_at"})
    db.commit()
    return result
