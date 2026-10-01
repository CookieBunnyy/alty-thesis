from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_management
from app.models.client import Client
from app.models.document import Document
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.schemas.client import ClientProfile, ClientResponse, ClientSummary, ClientSyncResult
from app.services.audit import record_audit
from app.services.client_sync import sync_clients
from app.services.entity_matching import find_client_by_external_reference

router = APIRouter(prefix="/clients", tags=["Clients"])


def _latest_transaction(client: Client) -> PropertyTransaction | None:
    return max(client.transactions, key=lambda item: item.transaction_date, default=None)


def _response(client: Client) -> dict:
    listing = client.property_listing
    transaction = _latest_transaction(client)
    return {
        "client_id": str(client.client_id),
        "external_client_id": client.external_client_id,
        "full_name": client.full_name,
        "location": client.location,
        "phone_number": client.phone_number,
        "email": client.email,
        "occupation": client.occupation,
        "civil_status": client.civil_status,
        "preferred_contact": client.preferred_contact,
        "purpose_of_purchase": client.purpose_of_purchase,
        "agent_id": client.agent_id,
        "agent_name": client.agent.full_name if client.agent else None,
        "property_id": client.property_id,
        "property_external_id": listing.external_listing_id if listing else None,
        "property_title": listing.title if listing else None,
        "property_location": listing.village_name if listing else None,
        "property_price": float(listing.price_total) if listing and listing.price_total is not None else None,
        "transaction_type": client.transaction_type,
        "transaction_date": client.transaction_date,
        "status": client.status,
        "source": client.source,
        "sync_status": client.sync_status,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        "transaction_id": str(transaction.transaction_id) if transaction else None,
        "amount": float(transaction.amount) if transaction else None,
        "transaction_count": len(client.transactions),
    }


@router.get("", response_model=list[ClientResponse])
def get_clients(
    search: str | None = None,
    status: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    statement = select(Client).order_by(Client.full_name)
    if status:
        statement = statement.where(Client.status == status.upper())
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(
            Client.full_name.ilike(pattern), Client.email.ilike(pattern),
            Client.phone_number.ilike(pattern), Client.external_client_id.ilike(pattern),
            Client.location.ilike(pattern),
        ))
    clients = db.execute(statement.offset(offset).limit(limit)).unique().scalars().all()
    return [_response(client) for client in clients]


@router.get("/count")
def get_client_count(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return {"total": int(db.scalar(select(func.count(Client.client_id))) or 0)}


@router.get("/summary", response_model=ClientSummary)
def get_client_summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.execute(select(Client.status, func.count()).group_by(Client.status)).all()
    counts = {str(status).upper(): int(total) for status, total in rows}
    return {
        "total": sum(counts.values()),
        "prospect": counts.get("PROSPECT", 0),
        "reserved": counts.get("RESERVED", 0),
        "sold": counts.get("SOLD", 0),
        "cancelled": counts.get("CANCELLED", 0),
    }


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(client_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    client = _client_or_404(db, client_id)
    return _response(client)


def _client_or_404(db: Session, client_id: str) -> Client:
    client = find_client_by_external_reference(db, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/{client_id}/profile", response_model=ClientProfile)
def get_client_profile(client_id: str, db: Session = Depends(get_db),
                       _user: User = Depends(get_current_user)):
    """Client information with full transaction history and related documents."""
    client = _client_or_404(db, client_id)
    transactions = sorted(client.transactions, key=lambda item: item.transaction_date)
    references = {client.client_id}
    if client.external_client_id:
        references.add(client.external_client_id)
    transaction_refs = {t.transaction_id for t in transactions} | {
        t.external_transaction_id for t in transactions if t.external_transaction_id
    }
    source_ids = {t.source_document_id for t in transactions if t.source_document_id}
    conditions = [Document.related_party_external_id.in_(references)]
    if transaction_refs:
        conditions.append(Document.transaction_reference.in_(transaction_refs))
    if source_ids:
        conditions.append(Document.document_id.in_(source_ids))
    documents = db.execute(
        select(Document).where(or_(*conditions)).order_by(Document.created_at.desc())
    ).scalars().all()
    return {
        "client": _response(client),
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "external_transaction_id": t.external_transaction_id,
                "property_id": t.property_id,
                "property_title": t.property_listing.title if t.property_listing else None,
                "agent_id": t.agent_id,
                "agent_name": t.agent.full_name if t.agent else None,
                "transaction_type": t.transaction_type,
                "transaction_date": t.transaction_date,
                "amount": float(t.amount),
                "status": t.status,
                "source": t.source,
                "source_document_id": t.source_document_id,
            }
            for t in transactions
        ],
        "documents": [
            {
                "document_id": d.document_id,
                "document_name": d.document_name,
                "document_type": d.document_type,
                "status": d.status,
                "version": d.version,
                "created_at": d.created_at,
            }
            for d in documents
        ],
    }


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, db: Session = Depends(get_db),
                  actor: User = Depends(require_management)):
    """Remove a client created in error. Clients with a completed sale keep
    their history and cannot be deleted."""
    client = _client_or_404(db, client_id)
    if any(t.transaction_type == "SOLD" and t.status == "COMPLETED" for t in client.transactions):
        raise HTTPException(
            status_code=409,
            detail="This client has a completed sale; sales history cannot be deleted.",
        )
    released: list[int] = []
    for transaction in list(client.transactions):
        listing = transaction.property_listing
        if transaction.status == "RESERVED" and listing is not None and listing.status == "RESERVED":
            listing.status = "AVAILABLE"
            listing.status_changed_at = datetime.utcnow()
            listing.sync_status = "PENDING"
            released.append(listing.listing_id)
        db.delete(transaction)
    record_audit(db, "CLIENT_DELETED", actor=actor, entity_type="clients", entity_id=client.client_id,
                 details={"full_name": client.full_name, "released_properties": released,
                          "transactions_removed": len(client.transactions)})
    db.delete(client)
    db.commit()
    return Response(status_code=204)


@router.post("/sync", response_model=ClientSyncResult)
def sync_client_records(db: Session = Depends(get_db), user: User = Depends(require_management)):
    result = sync_clients(db)
    record_audit(db, "CLIENTS_SYNCED", actor=user, entity_type="clients",
                 details={key: value for key, value in result.items() if key != "last_synced_at"})
    db.commit()
    return result
