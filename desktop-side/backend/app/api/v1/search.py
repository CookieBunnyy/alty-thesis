"""Global search used by the desktop top bar."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent import Agent
from app.models.client import Client
from app.models.document import Document
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
def global_search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Matches across properties, clients, transactions, agents and documents.

    Each result names the desktop page that shows it (``page``) and the text
    to put in that page's filter (``filter``).
    """
    pattern = f"%{q.strip()}%"
    results: dict[str, list[dict]] = {}

    listings = db.execute(select(PropertyListing).where(or_(
        PropertyListing.title.ilike(pattern), PropertyListing.village_name.ilike(pattern),
        PropertyListing.category.ilike(pattern), PropertyListing.external_listing_id.ilike(pattern),
        cast(PropertyListing.listing_id, String) == q.strip(),
    )).order_by(PropertyListing.title).limit(limit)).scalars().all()
    results["properties"] = [{
        "id": str(item.listing_id),
        "title": item.title or f"Listing {item.listing_id}",
        "subtitle": " · ".join(filter(None, [item.external_listing_id, item.village_name, item.status])),
        "page": "properties",
        "filter": item.title or str(item.listing_id),
    } for item in listings]

    clients = db.execute(select(Client).where(or_(
        Client.full_name.ilike(pattern), Client.email.ilike(pattern),
        Client.phone_number.ilike(pattern), Client.external_client_id.ilike(pattern),
        Client.location.ilike(pattern),
    )).order_by(Client.full_name).limit(limit)).unique().scalars().all()
    results["clients"] = [{
        "id": item.client_id,
        "title": item.full_name,
        "subtitle": " · ".join(filter(None, [item.external_client_id, item.email or item.phone_number,
                                             item.status])),
        "page": "clients",
        "filter": item.full_name,
    } for item in clients]

    transactions = db.execute(
        select(PropertyTransaction).join(PropertyTransaction.client).join(PropertyTransaction.property_listing)
        .where(or_(
            PropertyTransaction.external_transaction_id.ilike(pattern),
            cast(PropertyTransaction.transaction_id, String).ilike(pattern),
            Client.full_name.ilike(pattern), PropertyListing.title.ilike(pattern),
        )).order_by(PropertyTransaction.transaction_date.desc()).limit(limit)
    ).scalars().all()
    results["transactions"] = [{
        "id": item.transaction_id,
        "title": f"{item.transaction_type.title()} · {item.client.full_name}",
        "subtitle": " · ".join(filter(None, [item.external_transaction_id, item.property_listing.title,
                                             f"₱{item.amount:,.2f}", item.status])),
        "page": "transactions",
        "filter": item.client.full_name,
    } for item in transactions]

    agents = db.execute(select(Agent).where(or_(
        Agent.agent_id.ilike(pattern), Agent.full_name.ilike(pattern), Agent.agent_location.ilike(pattern),
    )).order_by(Agent.full_name).limit(limit)).scalars().all()
    results["agents"] = [{
        "id": item.agent_id,
        "title": item.full_name,
        "subtitle": " · ".join(filter(None, [item.agent_id, item.agent_location, item.status])),
        "page": "agents",
        "filter": item.full_name,
    } for item in agents]

    documents = db.execute(select(Document).where(or_(
        Document.document_name.ilike(pattern), Document.related_party_name.ilike(pattern),
        Document.property_listing_external_id.ilike(pattern), Document.property_listing_title.ilike(pattern),
        Document.transaction_reference.ilike(pattern), Document.document_type.ilike(pattern),
    ), Document.status != "SUPERSEDED").order_by(Document.created_at.desc()).limit(limit)).scalars().all()
    results["documents"] = [{
        "id": item.document_id,
        "title": item.document_name,
        "subtitle": " · ".join(filter(None, [item.document_type.replace("_", " ").title(), item.status,
                                             item.related_party_name])),
        "page": "documents",
        "filter": item.document_name,
    } for item in documents]

    partners = db.execute(select(Partner).where(or_(
        Partner.name.ilike(pattern), Partner.contact_person.ilike(pattern), Partner.email.ilike(pattern),
    )).order_by(Partner.name).limit(limit)).scalars().all()
    results["partners"] = [{
        "id": str(item.id),
        "title": item.name,
        "subtitle": " · ".join(filter(None, [(item.partner_type or "Partner").replace("_", " ").title(), item.status,
                                             item.contact_person])),
        "page": "partners",
        "filter": item.name,
    } for item in partners]

    return {"query": q, "total": sum(len(group) for group in results.values()), "results": results}
