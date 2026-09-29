from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.transaction import TransactionResponse, TransactionSummary, TransactionSyncResult
from app.services.transaction_sync import sync_transactions

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def _query():
    return (
        select(PropertyTransaction)
        .join(PropertyTransaction.client)
        .join(PropertyTransaction.property_listing)
        .join(PropertyTransaction.agent)
        .order_by(PropertyTransaction.transaction_date.desc())
    )


def _response(transaction: PropertyTransaction) -> dict:
    return {
        "transaction_id": str(transaction.transaction_id),
        "client_id": str(transaction.client_id),
        "client_name": transaction.client.full_name,
        "property_id": transaction.property_id,
        "property_title": transaction.property_listing.title,
        "agent_id": transaction.agent_id,
        "agent_name": transaction.agent.full_name,
        "transaction_type": transaction.transaction_type,
        "transaction_date": transaction.transaction_date,
        "amount": transaction.amount,
        "status": transaction.status,
        "notes": transaction.notes,
        "created_at": transaction.created_at,
        "updated_at": transaction.updated_at,
    }


@router.get("", response_model=list[TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return [_response(item) for item in db.execute(_query()).scalars().all()]


@router.get("/summary", response_model=TransactionSummary)
def get_transaction_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total, reserved, completed, amount_total = db.execute(
        select(
            func.count(PropertyTransaction.transaction_id),
            func.coalesce(
                func.sum(case((func.upper(PropertyTransaction.status) == "RESERVED", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((func.upper(PropertyTransaction.status) == "COMPLETED", 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            func.upper(PropertyTransaction.status) == "COMPLETED",
                            PropertyTransaction.amount,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
    ).one()
    return {
        "total": int(total),
        "reserved": int(reserved),
        "completed": int(completed),
        "amount_total": amount_total,
    }


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    transaction = db.execute(
        _query().where(PropertyTransaction.transaction_id == transaction_id)
    ).scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _response(transaction)


@router.post("/sync", response_model=TransactionSyncResult)
def sync_transaction_records(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role.casefold() not in {"administrator", "general manager"}:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator or general manager can sync transactions.",
        )
    return sync_transactions(db)