"""Bulletin board: announcements and memos for everyone in the Management
System. The Administrator posts; every new post is a notification for all
staff (services.notifications)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import COMPANY_ROLES, canonical_role, get_company_user, get_current_user, require_management
from app.models.branch import Branch
from app.models.bulletin import BOARDS, CATEGORIES, BulletinPost
from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.models.user import User
from app.services import bulletin as figures
from app.services.audit import record_audit
from app.services.document_storage import StorageError, UnsupportedFileError, delete_file, detect_file_kind, read_file, store_file
from app.services.transaction_queries import WITH_PARTIES

router = APIRouter(prefix="/bulletin", tags=["Bulletin board"])


class Tier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=80)
    minimum_sales: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    reward: str | None = Field(default=None, max_length=200)


class PostIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    board: str
    category: str
    title: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=5000)
    event_at: datetime | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    tiers: list[Tier] | None = Field(default=None, max_length=10)
    reward_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    branch_id: int | None = None
    partner_id: int | None = None
    listing_id: int | None = None
    transaction_id: str | None = Field(default=None, max_length=64)
    pinned: bool = False
    archived: bool = False

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _check(db: Session, data: dict) -> dict:
    board = str(data["board"]).upper()
    category = str(data["category"]).upper()
    if board not in BOARDS:
        raise HTTPException(status_code=422, detail="board must be ANNOUNCEMENT or MEMO")
    if category not in CATEGORIES[board]:
        raise HTTPException(status_code=422, detail=f"category must be one of {', '.join(CATEGORIES[board])}")
    data.update(board=board, category=category, body=data.get("body") or None)
    if data.get("valid_from") and data.get("valid_until") and data["valid_until"] < data["valid_from"]:
        raise HTTPException(status_code=422, detail="The end date is before the start date")
    if category == "TARGET" and not data.get("target_amount"):
        raise HTTPException(status_code=422, detail="Enter the target sales amount")
    if category == "INCENTIVE" and not (data.get("tiers") or data.get("reward_amount")):
        raise HTTPException(status_code=422, detail="Add the reward tiers or the incentive per sale")
    if category == "SALES_NOTICE" and not data.get("transaction_id"):
        raise HTTPException(status_code=422, detail="Choose the recorded reservation or sale")
    if category == "MEETING" and not data.get("event_at"):
        raise HTTPException(status_code=422, detail="Enter when the meeting is")
    for key, model in (("branch_id", Branch), ("partner_id", Partner), ("listing_id", PropertyListing)):
        if data.get(key) is not None and db.get(model, data[key]) is None:
            raise HTTPException(status_code=422, detail=f"Unknown {key.replace('_id', '')}")
    if data.get("transaction_id") and db.get(PropertyTransaction, data["transaction_id"]) is None:
        raise HTTPException(status_code=422, detail="Unknown transaction")
    if data.get("tiers") is not None:
        data["tiers"] = [{**tier, "minimum_sales": float(tier["minimum_sales"])} for tier in data["tiers"]]
    return data


def _sale(db: Session, transaction_id: str | None) -> dict | None:
    if not transaction_id:
        return None
    tx = db.execute(select(PropertyTransaction).options(*WITH_PARTIES)
                    .where(PropertyTransaction.transaction_id == transaction_id)).scalar_one_or_none()
    if tx is None:
        return None
    listing = tx.property_listing
    return {"date": tx.transaction_date.date().isoformat(), "buyer": tx.client.full_name if tx.client else None,
            "agent": tx.agent.full_name if tx.agent else tx.agent_id,
            "project": (listing.project_name or listing.title) if listing else None,
            "tcp": float(tx.amount), "status": tx.status, "type": tx.transaction_type}


def _serialize(db: Session, post: BulletinPost, user: User, names: dict) -> dict:
    company = canonical_role(user.role) in COMPANY_ROLES
    return {
        "id": post.id, "board": post.board, "category": post.category, "title": post.title, "body": post.body,
        "event_at": post.event_at, "valid_from": post.valid_from, "valid_until": post.valid_until,
        "target_amount": float(post.target_amount) if post.target_amount is not None else None,
        "tiers": post.tiers, "reward_amount": float(post.reward_amount) if post.reward_amount is not None else None,
        "branch_id": post.branch_id, "branch_name": names["branches"].get(post.branch_id),
        "partner_id": post.partner_id, "partner_name": names["partners"].get(post.partner_id),
        "listing_id": post.listing_id, "transaction_id": post.transaction_id,
        # Sales notices show the buyer, agent, project and TCP of the recorded sale.
        "sale": _sale(db, post.transaction_id) if company or post.category == "SALES_NOTICE" else None,
        "has_image": bool(post.image_path), "image_url": f"/api/v1/bulletin/{post.id}/image" if post.image_path else None,
        "pinned": post.pinned, "archived": post.archived,
        "created_by": post.created_by_name, "created_at": post.created_at, "updated_at": post.updated_at,
        "progress": figures.progress(db, post, viewer_agent_id=user.agent_id, company=company),
    }


def _names(db: Session) -> dict:
    return {"branches": dict(db.execute(select(Branch.id, Branch.name)).all()),
            "partners": dict(db.execute(select(Partner.id, Partner.name)).all())}


def _post_or_404(db: Session, post_id: int) -> BulletinPost:
    post = db.get(BulletinPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.get("")
def list_posts(board: str | None = None, include_archived: bool = False, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    query = select(BulletinPost)
    if board:
        query = query.where(BulletinPost.board == board.upper())
    if not include_archived:
        query = query.where(BulletinPost.archived.is_(False))
    rows = db.execute(query.order_by(BulletinPost.pinned.desc(), BulletinPost.created_at.desc()).limit(200)).scalars()
    names = _names(db)
    return [_serialize(db, post, user, names) for post in rows]


@router.get("/sales-options")
def sales_options(db: Session = Depends(get_db), _user: User = Depends(get_company_user)):
    """Recent recorded reservations and sales, for a sales notice memo."""
    rows = db.execute(select(PropertyTransaction).options(*WITH_PARTIES)
                      .where(PropertyTransaction.status != "CANCELLED")
                      .order_by(PropertyTransaction.transaction_date.desc()).limit(100)).scalars()
    return [{"transaction_id": str(tx.transaction_id), **_sale(db, str(tx.transaction_id))} for tx in rows]


@router.post("", status_code=201)
def create_post(payload: PostIn, db: Session = Depends(get_db), user: User = Depends(require_management)):
    data = _check(db, payload.model_dump())
    post = BulletinPost(**data, created_by_user_id=user.id, created_by_name=user.full_name or user.username)
    db.add(post)
    db.flush()
    record_audit(db, "BULLETIN_POSTED", actor=user, entity_type="bulletin_posts", entity_id=post.id,
                 details={"board": post.board, "category": post.category, "title": post.title})
    db.commit()
    db.refresh(post)
    return _serialize(db, post, user, _names(db))


@router.put("/{post_id}")
def update_post(post_id: int, payload: PostIn, db: Session = Depends(get_db), user: User = Depends(require_management)):
    post = _post_or_404(db, post_id)
    data = _check(db, payload.model_dump())
    for key, value in data.items():
        setattr(post, key, value)
    record_audit(db, "BULLETIN_UPDATED", actor=user, entity_type="bulletin_posts", entity_id=post.id,
                 details={"title": post.title, "archived": post.archived})
    db.commit()
    db.refresh(post)
    return _serialize(db, post, user, _names(db))


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(require_management)):
    post = _post_or_404(db, post_id)
    if post.image_path:
        try:
            delete_file(post.image_bucket, post.image_path)
        except StorageError:
            pass  # an orphaned file is harmless; the post still goes
    record_audit(db, "BULLETIN_DELETED", actor=user, entity_type="bulletin_posts", entity_id=post.id,
                 details={"title": post.title})
    db.delete(post)
    db.commit()
    return Response(status_code=204)


@router.put("/{post_id}/image")
def upload_image(post_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(require_management)):
    """The flyer or poster shown with the post."""
    post = _post_or_404(db, post_id)
    name = (file.filename or "").replace("\\", "/").split("/")[-1].strip()[:255]
    content = file.file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty")
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Files must be {settings.MAX_UPLOAD_MB} MB or smaller")
    try:
        kind = detect_file_kind(name, content)
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    if kind.source_format != "IMAGE":
        raise HTTPException(status_code=415, detail="The flyer must be an image")
    path = f"bulletin/{post.id}-{uuid.uuid4().hex}{kind.extension}"
    try:
        bucket = store_file("media", path, content, kind.mime_type)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The image could not be stored") from exc
    old = (post.image_bucket, post.image_path)
    post.image_bucket, post.image_path, post.image_mime = bucket, path, kind.mime_type
    record_audit(db, "BULLETIN_IMAGE_SET", actor=user, entity_type="bulletin_posts", entity_id=post.id)
    db.commit()
    if old[1]:
        try:
            delete_file(*old)
        except StorageError:
            pass
    db.refresh(post)
    return _serialize(db, post, user, _names(db))


@router.get("/{post_id}/image")
def get_image(post_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    post = _post_or_404(db, post_id)
    if not post.image_path:
        raise HTTPException(status_code=404, detail="This post has no image")
    try:
        content = read_file(post.image_bucket, post.image_path)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The image is currently unavailable") from exc
    return Response(content=content, media_type=post.image_mime or "image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
