from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.core.supabase import supabase
from app.models.client import Client
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.client import (
    ClientResponse,
    ClientSummary,
    ClientSyncResult,
)
from app.services.client_sync import sync_clients

router = APIRouter(prefix="/clients", tags=["Clients"])


def _response(client: Client) -> dict:
    listing = client.property_listing
    transaction = max(
        client.transactions,
        key=lambda item: item.transaction_date,
        default=None,
    )
    return {
        "client_id": str(client.client_id),
        "full_name": client.full_name,
        "location": client.location,
        "phone_number": client.phone_number,
        "email": client.email,
        "agent_id": client.agent_id,
        "agent_name": client.agent.full_name,
        "property_id": client.property_id,
        "property_title": listing.title,
        "property_location": listing.village_name,
        "property_price": float(listing.price_total) if listing.price_total is not None else None,
        "transaction_type": client.transaction_type,
        "transaction_date": client.transaction_date,
        "status": client.status,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        "transaction_id": str(transaction.transaction_id) if transaction else None,
        "amount": float(transaction.amount) if transaction else None,
    }


def _active_clients_query():
    return (
        select(Client)
        .join(Client.property_listing)
        .order_by(Client.full_name)
    )


@router.get("", response_model=list[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    clients = db.execute(_active_clients_query()).scalars().all()
    return [_response(client) for client in clients]


@router.get("/count")
def get_client_count(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total = db.scalar(select(func.count(Client.client_id))) or 0
    return {"total": int(total)}


@router.get("/summary", response_model=ClientSummary)
def get_client_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    normalized_status = func.upper(Client.status)
    total, reserved, sold, cancelled = db.execute(
        select(
            func.count(Client.client_id),
            func.coalesce(
                func.sum(case((normalized_status == "RESERVED", 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((normalized_status == "SOLD", 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((normalized_status == "CANCELLED", 1), else_=0)), 0
            ),
        )
    ).one()
    return {
        "total": int(total),
        "reserved": int(reserved),
        "sold": int(sold),
        "cancelled": int(cancelled),
    }


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    client = db.execute(
        _active_clients_query().where(Client.client_id == client_id)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return _response(client)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if actor.role.casefold() not in {"administrator", "general manager"}:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator or general manager can delete clients.",
        )

    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    listing = db.get(PropertyListing, client.property_id)
    transactions = db.execute(
        select(PropertyTransaction).where(
            PropertyTransaction.client_id == client.client_id
        )
    ).scalars().all()
    release_listing = bool(
        listing
        and listing.status == "RESERVED"
        and any(
            transaction.transaction_type == "RESERVED"
            for transaction in transactions
        )
    )

    cloud_configured = bool(
        settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY
    )
    if cloud_configured:
        try:
            supabase.table("transactions").delete().eq(
                "client_id", str(client.client_id)
            ).execute()
            supabase.table("clients").delete().eq(
                "client_id", str(client.client_id)
            ).execute()
            if release_listing:
                supabase.table("listings").update({"status": "AVAILABLE"}).eq(
                    "listing_id", client.property_id
                ).eq("status", "RESERVED").execute()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Unable to delete the client from Supabase: {exc}",
            ) from exc

    for transaction in transactions:
        db.delete(transaction)
    db.delete(client)
    if release_listing and listing is not None:
        listing.status = "AVAILABLE"
        listing.sync_status = "SYNCED" if cloud_configured else "PENDING"
        listing.last_synced_at = datetime.utcnow() if cloud_configured else None

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to delete the client and linked transactions locally.",
        ) from exc
    return Response(status_code=204)


@router.post("/sync", response_model=ClientSyncResult)
def sync_client_records(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role.casefold() not in {"administrator", "general manager"}:
        raise HTTPException(
            status_code=403,
            detail="Only an administrator or general manager can sync clients.",
        )
    return sync_clients(db)