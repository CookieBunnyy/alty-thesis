"""Website client accounts: sign up, sign in, my transactions, my reviews.

Client accounts live in the same ``users`` table, use the same bcrypt hashing
and JWT tokens as staff, and carry the role "Client". They are refused by
every internal endpoint (``get_current_user``) and staff accounts are refused
here, so the two audiences stay separate.
"""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.public import WebsiteTransaction, _RateLimiter, record_client_transaction
from app.core.database import get_db
from app.core.security import CLIENT, create_access_token, get_current_client, get_password_hash, \
    is_client, verify_password
from app.models.client import Client
from app.models.review import AgentReview
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services import reviews as review_service
from app.services.audit import record_audit, record_audit_now
from app.services.cloud_sync import try_push_pending

router = APIRouter(prefix="/client", tags=["Website clients"])

auth_limiter = _RateLimiter()
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^[0-9+()\-\s]{7,40}$")


def _clean(value: object) -> object:
    return (" ".join(value.split()) or None) if isinstance(value, str) else value


class ClientRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=100)
    phone_number: str = Field(min_length=7, max_length=40)
    location: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name", "phone_number", "location", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return _clean(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        value = str(value or "").strip().casefold()
        if not EMAIL.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("phone_number")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        if not PHONE.match(value):
            raise ValueError("Enter a valid phone number")
        return value


class ClientLogin(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    review: str | None = Field(default=None, max_length=review_service.MAX_REVIEW_LENGTH)

    @field_validator("review", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value


class ReviewCreate(ReviewIn):
    transaction_id: str = Field(min_length=1, max_length=64)


def _limit(request: Request, bucket: str, limit: int) -> None:
    host = request.client.host if request.client else "unknown"
    auth_limiter.check(f"{bucket}:{host}", limit, window=900.0,
                       detail="Too many attempts; please wait a few minutes and try again.")


def _profile(user: User, client: Client) -> dict:
    return {
        "full_name": client.full_name,
        "email": client.email,
        "phone_number": client.phone_number,
        "location": client.location,
        "member_since": user.created_at,
    }


def _session(user: User, client: Client) -> dict:
    return {"access_token": create_access_token(subject=user.username), "token_type": "bearer",
            "client": _profile(user, client)}


@router.post("/register", status_code=201)
def register_client(payload: ClientRegister, request: Request, db: Session = Depends(get_db)):
    """Create a website account and its client record, then sign in."""
    _limit(request, "register", 10)
    if db.scalar(select(User.id).where(func.lower(User.username) == payload.email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Sign in instead.")
    # An existing client record (from documents or an agent) is never linked
    # automatically: without email verification that would expose someone's
    # transactions to whoever registers their address first.
    existing = db.scalar(select(Client.client_id).where(or_(
        func.lower(Client.email) == payload.email,
        func.regexp_replace(Client.phone_number, r"\D", "", "g") == re.sub(r"\D", "", payload.phone_number),
    )))
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Abellar Realty already has a client record with this email or phone number. "
                   "Please contact your agent to activate your website account.",
        )
    client = Client(full_name=payload.full_name, email=payload.email, phone_number=payload.phone_number,
                    location=payload.location, status="PROSPECT", source="WEBSITE", sync_status="PENDING")
    db.add(client)
    db.flush()
    user = User(username=payload.email, full_name=payload.full_name, role=CLIENT, client_id=client.client_id,
                password_hash=get_password_hash(payload.password), is_active=True)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    record_audit(db, "CLIENT_REGISTERED", actor=user, entity_type="clients", entity_id=client.client_id,
                 details={"source": "WEBSITE"})
    db.commit()
    try_push_pending(db)
    return _session(user, client)


@router.post("/login")
def login_client(payload: ClientLogin, request: Request, db: Session = Depends(get_db)):
    _limit(request, "login", 20)
    email = payload.email.strip().casefold()
    user = db.execute(select(User).where(func.lower(User.username) == email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        record_audit_now(db, "CLIENT_LOGIN_FAILED", actor=email[:120] or "UNKNOWN", entity_type="users",
                         result="FAILED", details={"reason": "invalid credentials"})
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not is_client(user):
        raise HTTPException(status_code=403,
                            detail="Staff accounts sign in through the Abellar Realty desktop application.")
    client = db.get(Client, user.client_id) if user.client_id else None
    if not user.is_active or client is None:
        raise HTTPException(status_code=403, detail="This account is inactive. Contact Abellar Realty.")
    user.last_login_at = datetime.utcnow()
    record_audit(db, "CLIENT_LOGIN", actor=user, entity_type="users", entity_id=user.id)
    db.commit()
    return _session(user, client)


@router.get("/me")
def client_me(user: User = Depends(get_current_client), db: Session = Depends(get_db)):
    return _profile(user, db.get(Client, user.client_id))


def _own_transactions(db: Session, client_id: str) -> list[PropertyTransaction]:
    return list(db.execute(
        select(PropertyTransaction).where(PropertyTransaction.client_id == client_id)
        .order_by(PropertyTransaction.transaction_date.desc())
    ).scalars())


@router.get("/transactions")
def my_transactions(user: User = Depends(get_current_client), db: Session = Depends(get_db)):
    """The signed-in client's own transactions, with review eligibility."""
    transactions = _own_transactions(db, user.client_id)
    reviews = {r.transaction_id: r for r in db.execute(
        select(AgentReview).where(AgentReview.client_id == user.client_id)).scalars()}
    stats = review_service.review_stats(db, list({t.agent_id for t in transactions}))
    out = []
    for t in transactions:
        listing, agent, review = t.property_listing, t.agent, reviews.get(t.transaction_id)
        out.append({
            "transaction_id": t.transaction_id,
            "transaction_type": t.transaction_type,
            "status": t.status,
            "transaction_date": t.transaction_date,
            "amount": float(t.amount),
            "property": {"listing_id": listing.listing_id, "title": listing.title,
                         "village_name": listing.village_name, "status": listing.status,
                         "photo": (listing.photos or [None])[0]},
            "agent": {"agent_id": agent.agent_id, "full_name": agent.full_name,
                      "phone_number": agent.phone_number, "agent_location": agent.agent_location,
                      **review_service.stats_for(stats, agent.agent_id)},
            "review": {"id": review.id, "rating": review.rating, "review": review.review,
                       "updated_at": review.updated_at} if review else None,
            "can_review": t.status == "COMPLETED" and review is None,
        })
    return out


@router.post("/transactions", status_code=201)
def create_my_transaction(payload: WebsiteTransaction, request: Request,
                          user: User = Depends(get_current_client), db: Session = Depends(get_db)):
    return record_client_transaction(db, request, user, payload)


@router.get("/reviews")
def my_reviews(user: User = Depends(get_current_client), db: Session = Depends(get_db)):
    rows = db.execute(select(AgentReview).where(AgentReview.client_id == user.client_id)
                      .order_by(AgentReview.updated_at.desc())).scalars()
    return [{**review_service.public_review(r, include_agent=True), "transaction_id": r.transaction_id}
            for r in rows]


@router.post("/reviews", status_code=201)
def create_review(payload: ReviewCreate, user: User = Depends(get_current_client),
                  db: Session = Depends(get_db)):
    """Rate the agent of one of *your* completed transactions (once)."""
    transaction = db.get(PropertyTransaction, payload.transaction_id) if _is_uuid(payload.transaction_id) else None
    if transaction is None or transaction.client_id != user.client_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if transaction.status != "COMPLETED":
        raise HTTPException(status_code=409,
                            detail="You can rate your agent once this transaction is completed.")
    if db.scalar(select(AgentReview.id).where(AgentReview.transaction_id == transaction.transaction_id)):
        raise HTTPException(status_code=409,
                            detail="You already rated this transaction. You can edit your review instead.")
    review = AgentReview(agent_id=transaction.agent_id, client_id=user.client_id,
                         transaction_id=transaction.transaction_id, rating=payload.rating, review=payload.review)
    db.add(review)
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent duplicate
        db.rollback()
        raise HTTPException(status_code=409, detail="You already rated this transaction.") from exc
    record_audit(db, "AGENT_REVIEW_CREATED", actor=user, entity_type="agents", entity_id=transaction.agent_id,
                 details={"review_id": review.id, "rating": review.rating})
    db.commit()
    db.refresh(review)
    return {**review_service.public_review(review, include_agent=True), "transaction_id": review.transaction_id}


@router.put("/reviews/{review_id}")
def update_review(review_id: int, payload: ReviewIn, user: User = Depends(get_current_client),
                  db: Session = Depends(get_db)):
    """Edit your own review (the same row; no extra rating is added)."""
    review = db.get(AgentReview, review_id)
    if review is None or review.client_id != user.client_id:
        raise HTTPException(status_code=404, detail="Review not found")
    review.rating, review.review = payload.rating, payload.review
    record_audit(db, "AGENT_REVIEW_UPDATED", actor=user, entity_type="agents", entity_id=review.agent_id,
                 details={"review_id": review.id, "rating": review.rating})
    db.commit()
    db.refresh(review)
    return {**review_service.public_review(review, include_agent=True), "transaction_id": review.transaction_id}


def _is_uuid(value: str) -> bool:
    from uuid import UUID

    try:
        UUID(value)
        return True
    except ValueError:
        return False

