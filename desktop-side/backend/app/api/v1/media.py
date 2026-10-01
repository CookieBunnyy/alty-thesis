"""Digital property preview: uploaded images with OpenCV quality analysis."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import FILING_ROLES, get_current_user, require_roles
from app.models.media import PropertyMedia
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.services.audit import record_audit
from app.services.document_storage import (
    StorageError,
    UnsupportedFileError,
    delete_file,
    detect_file_kind,
    read_file,
    store_file,
)
from app.services.media_analysis import THRESHOLDS, analyze_image

router = APIRouter(prefix="/media", tags=["Media"])
require_editor = require_roles(*FILING_ROLES)


def _serialize(media: PropertyMedia) -> dict:
    return {
        "id": media.id,
        "listing_id": media.listing_id,
        "file_name": media.file_name,
        "mime_type": media.mime_type,
        "file_size": media.file_size,
        "width": media.width,
        "height": media.height,
        "orientation": media.orientation,
        "blur_score": media.blur_score,
        "brightness": media.brightness,
        "contrast": media.contrast,
        "quality_status": media.quality_status,
        "quality_issues": media.quality_issues,
        "created_at": media.created_at,
        "file_url": f"/api/v1/media/{media.id}/file",
    }


@router.get("/thresholds")
def get_thresholds(_user: User = Depends(get_current_user)):
    return {**THRESHOLDS, "note": "Quality analysis only; room/feature recognition is not performed."}


@router.get("")
def list_media(listing_id: int | None = None, quality_status: str | None = None,
               db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    statement = select(PropertyMedia).order_by(PropertyMedia.created_at.desc())
    if listing_id is not None:
        statement = statement.where(PropertyMedia.listing_id == listing_id)
    if quality_status:
        statement = statement.where(PropertyMedia.quality_status == quality_status.upper())
    return [_serialize(item) for item in db.execute(statement).scalars()]


@router.get("/summary")
def media_summary(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.execute(
        select(PropertyMedia.quality_status, func.count()).group_by(PropertyMedia.quality_status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    listings_with_media = db.scalar(select(func.count(func.distinct(PropertyMedia.listing_id)))) or 0
    return {"total": sum(counts.values()), "by_quality": counts,
            "listings_with_media": int(listings_with_media)}


@router.post("/properties/{listing_id}", status_code=201)
def upload_media(listing_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                 actor: User = Depends(require_editor)):
    listing = db.get(PropertyListing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Property listing not found")
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
        raise HTTPException(status_code=415, detail="Property media must be an image")

    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.execute(select(PropertyMedia).where(
        PropertyMedia.listing_id == listing_id, PropertyMedia.file_hash == file_hash
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail={"message": "This image is already attached",
                                                     "existing": jsonable_encoder(_serialize(existing))})

    report = analyze_image(content)
    storage_path = f"property-{listing_id}/{uuid.uuid4().hex}{kind.extension}"
    try:
        bucket = store_file("media", storage_path, content, kind.mime_type)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail={"message": "The image could not be stored",
                                                     "stage": "STORAGE", "reason": str(exc)}) from exc
    media = PropertyMedia(
        listing_id=listing_id, file_name=name or f"image{kind.extension}", storage_path=storage_path,
        storage_bucket=bucket, mime_type=kind.mime_type, file_size=len(content), file_hash=file_hash,
        width=report.width, height=report.height, orientation=report.orientation,
        blur_score=report.blur_score, brightness=report.brightness, contrast=report.contrast,
        quality_status=report.status, quality_issues=report.issues, uploaded_by=actor.id,
    )
    db.add(media)
    db.flush()
    record_audit(db, "MEDIA_UPLOADED", actor=actor, entity_type="property_media", entity_id=media.id,
                 details={"listing_id": listing_id, "quality_status": report.status,
                          "issues": report.issues})
    db.commit()
    db.refresh(media)
    return _serialize(media)


@router.get("/{media_id}/file")
def get_media_file(media_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    media = db.get(PropertyMedia, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        content = read_file(media.storage_bucket, media.storage_path)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The media file is currently unavailable") from exc
    return Response(content=content, media_type=media.mime_type,
                    headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: int, db: Session = Depends(get_db), actor: User = Depends(require_editor)):
    media = db.get(PropertyMedia, media_id)
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        delete_file(media.storage_bucket, media.storage_path)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail=f"Could not delete the stored image: {exc}") from exc
    record_audit(db, "MEDIA_DELETED", actor=actor, entity_type="property_media", entity_id=media_id,
                 details={"listing_id": media.listing_id, "file_name": media.file_name})
    db.delete(media)
    db.commit()
    return Response(status_code=204)


@router.get("/listing/{listing_id}/count")
def count_listing_media(listing_id: int, db: Session = Depends(get_db),
                        _user: User = Depends(get_current_user)):
    total = db.scalar(select(func.count(PropertyMedia.id)).where(PropertyMedia.listing_id == listing_id))
    return {"listing_id": listing_id, "total": int(total or 0)}

