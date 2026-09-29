import hashlib
import logging
import mimetypes
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import String, and_, cast, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.document import Document, DocumentAuditEvent, DocumentFolder
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.schemas.document import (
    DocumentFolderCreate,
    DocumentFolderResponse,
    DocumentFolderUpdate,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.document_storage import (
    delete_document_metadata,
    download_document_file,
    remove_document_file,
    sync_document_metadata,
    upload_document_file,
)
from app.services.document_processing import process_document_content


router = APIRouter(prefix="/documents", tags=["Document Repository"])
logger = logging.getLogger(__name__)
DOCUMENT_TYPES = {
    "Receipt", "Voucher", "Contract", "Deed", "Invoice", "Proof of Payment",
    "Buyer Document", "Seller Document", "Transaction Document", "Property Document",
    "Other", "PROPERTY_INFORMATION", "RESERVATION_AGREEMENT", "SALE_AGREEMENT",
    "AGENT_INFORMATION",
}
MAX_FILE_SIZE = 25 * 1024 * 1024
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh"}


def _document_or_404(db: Session, document_id: str) -> Document:
    document = db.execute(
        select(Document).where(Document.document_id == document_id)
        .order_by(Document.version.desc())
    ).scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _serialize_document(db: Session, document: Document) -> dict:
    result = DocumentResponse.model_validate(document).model_dump(mode="json")
    folder = db.get(DocumentFolder, document.folder_id) if document.folder_id else None
    property_record = db.get(Property, document.property_id) if document.property_id else None
    listing = (
        db.get(PropertyListing, document.property_listing_id)
        if document.property_listing_id
        else None
    )
    uploader = db.get(User, document.uploaded_by)
    processing_event = db.execute(
        select(DocumentAuditEvent)
        .where(
            DocumentAuditEvent.document_row_id == document.id,
            DocumentAuditEvent.event_type == "DOCUMENT_PROCESSING",
        )
        .order_by(DocumentAuditEvent.created_at.desc())
        .limit(1)
    ).scalars().first()
    processing_details = processing_event.details if processing_event else {}
    result.update(
        folder_name=folder.name if folder else None,
        property_name=(
            listing.title if listing else property_record.title if property_record else None
        ),
        property_listing_id=document.property_listing_id,
        property_listing_external_id=document.property_listing_external_id,
        property_listing_title=(
            listing.title if listing else document.property_listing_title
        ),
        transaction_reference=(
            document.transaction_reference
            or (str(document.transaction_id) if document.transaction_id is not None else None)
        ),
        related_party_external_id=document.related_party_external_id,
        extracted_fields=processing_details.get("extracted_fields") or {},
        processing_error=processing_details.get("error_reason"),
        uploaded_by_name=uploader.full_name if uploader else None,
    )
    return result


def _record_event(
    db: Session,
    event_type: str,
    actor: User,
    document: Document | None = None,
    folder: DocumentFolder | None = None,
    details: dict | None = None,
) -> None:
    db.add(DocumentAuditEvent(
        document_row_id=document.id if document else None,
        folder_id=folder.id if folder else None,
        actor_id=actor.id,
        event_type=event_type,
        details=details or {},
    ))


def _require_filing_manager(actor: User) -> None:
    if actor.role.casefold() not in {"administrator", "general manager", "filing manager"}:
        raise HTTPException(
            status_code=403,
            detail="A filing manager or administrator must perform this action",
        )


def _validate_folder(db: Session, folder_id: int | None) -> DocumentFolder | None:
    if folder_id is None:
        return None
    folder = db.get(DocumentFolder, folder_id)
    if folder is None or folder.is_archived:
        raise HTTPException(status_code=404, detail="Active folder not found")
    return folder


def _validate_property(db: Session, property_id: int | None) -> None:
    if property_id is not None and db.get(Property, property_id) is None:
        raise HTTPException(status_code=404, detail="Property not found")


def _read_file(upload: UploadFile) -> tuple[str, str, bytes, str]:
    name = (upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not name:
        raise HTTPException(status_code=400, detail="Choose a file to upload")
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="This file type cannot be uploaded")
    content = upload.file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Files must be 25 MB or smaller")
    mime_type = mimetypes.guess_type(name)[0] or upload.content_type or "application/octet-stream"
    return name, mime_type, content, hashlib.sha256(content).hexdigest()


def _find_duplicate(db: Session, file_hash: str, document_id: str | None) -> Document | None:
    statement = select(Document).where(Document.file_hash == file_hash)
    if document_id:
        statement = statement.where(Document.document_id != document_id)
    return db.execute(statement.order_by(Document.created_at.desc())).scalars().first()


def _upload_record(
    db: Session,
    actor: User,
    upload: UploadFile,
    document_name: str | None,
    document_type: str,
    folder_id: int | None,
    property_id: int | None,
    transaction_id: int | None,
    related_party_id: int | None,
    related_party_name: str | None,
    description: str | None,
    document_id: str | None = None,
    version: int = 1,
    allow_duplicate: bool = False,
) -> Document:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported document type")
    folder = _validate_folder(db, folder_id)
    _validate_property(db, property_id)
    filename, mime_type, content, file_hash = _read_file(upload)
    duplicate = _find_duplicate(db, file_hash, document_id)
    if duplicate and not allow_duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Possible duplicate document detected.",
                "existing_document": _serialize_document(db, duplicate),
            },
        )

    document_id = document_id or str(uuid.uuid4())
    now = datetime.utcnow()
    storage_path = f"{document_id}/v{version}/{filename.replace('/', '_')}"
    document = Document(
        document_id=document_id,
        document_name=(document_name or filename).strip()[:255],
        document_type=document_type,
        folder_id=folder.id if folder else None,
        property_id=property_id,
        transaction_id=transaction_id,
        related_party_id=related_party_id,
        related_party_name=related_party_name,
        description=description,
        storage_path=storage_path,
        storage_bucket=settings.SUPABASE_DOCUMENTS_BUCKET,
        mime_type=mime_type,
        file_size=len(content),
        file_hash=file_hash,
        version=version,
        status="PROCESSING",
        uploaded_by=actor.id,
        duplicate_of_id=duplicate.id if duplicate else None,
        created_at=now,
        updated_at=now,
    )
    uploaded = False
    metadata_saved = False
    stage = "storage upload"
    try:
        upload_document_file(storage_path, content, mime_type)
        uploaded = True
        stage = "Supabase document metadata upsert"
        sync_document_metadata(document)
        metadata_saved = True
        stage = "local document record insert"
        db.add(document)
        db.flush()
        _record_event(
            db,
            "DOCUMENT_PROCESSING_STARTED",
            actor,
            document,
            details={
                "document_id": document.document_id,
                "filename": filename,
                "status": "PROCESSING",
                "processing_timestamp": datetime.utcnow().isoformat(),
            },
        )
        stage = "document processing"
        processing = process_document_content(db, document, filename, content)
        document.status = processing["status"]
        _record_event(
            db,
            "VERSION_REPLACED" if version > 1 else "DOCUMENT_UPLOADED",
            actor,
            document,
            details={"version": version, "possible_duplicate": bool(duplicate)},
        )
        _record_event(
            db,
            "DOCUMENT_PROCESSING",
            actor,
            document,
            details=processing,
        )
        stage = "Supabase document processing metadata update"
        sync_document_metadata(document)
        db.commit()
        db.refresh(document)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Document upload failed during %s (document_id=%s)",
            stage,
            document_id,
        )
        try:
            if uploaded:
                remove_document_file(storage_path)
            if metadata_saved:
                delete_document_metadata(document)
        except Exception:
            pass
        raise HTTPException(
            status_code=502,
            detail=(
                f"Upload failed during {stage} "
                f"({type(exc).__name__}): {exc}"
            ),
        ) from exc
    return document


def _commit_document_change(
    db: Session, document: Document, actor: User, event_type: str,
    details: dict | None = None,
) -> None:
    document.updated_at = datetime.utcnow()
    _record_event(db, event_type, actor, document, details=details)
    try:
        sync_document_metadata(document)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="The document change could not be synchronized. No local change was saved.",
        ) from exc


@router.get("/folders", response_model=list[DocumentFolderResponse])
def get_folders(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    financial = None
    for name in ("Properties", "Buyers", "Sellers", "Transactions", "Financial", "Contracts", "Archived"):
        folder = db.execute(select(DocumentFolder).where(
            DocumentFolder.name == name, DocumentFolder.parent_id.is_(None)
        )).scalars().first()
        if folder is None:
            folder = DocumentFolder(name=name, created_by=actor.id)
            db.add(folder)
            db.flush()
            _record_event(db, "FOLDER_CREATED", actor, folder=folder, details={"name": name})
        if name == "Financial":
            financial = folder
    for name in ("Receipts", "Vouchers", "Proof of Payment"):
        folder = db.execute(select(DocumentFolder).where(
            DocumentFolder.name == name, DocumentFolder.parent_id == financial.id
        )).scalars().first()
        if folder is None:
            folder = DocumentFolder(name=name, parent_id=financial.id, created_by=actor.id)
            db.add(folder)
            db.flush()
            _record_event(db, "FOLDER_CREATED", actor, folder=folder, details={"name": name})
    db.commit()
    statement = select(DocumentFolder).order_by(DocumentFolder.name)
    if not include_archived:
        statement = statement.where(DocumentFolder.is_archived.is_(False))
    return db.execute(statement).scalars().all()


@router.post("/folders", response_model=DocumentFolderResponse, status_code=201)
def create_folder(
    payload: DocumentFolderCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    parent = _validate_folder(db, payload.parent_id)
    name = payload.name.strip()
    existing = db.execute(select(DocumentFolder).where(
        DocumentFolder.name == name,
        DocumentFolder.parent_id == (parent.id if parent else None),
        DocumentFolder.is_archived.is_(False),
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="A folder with that name already exists here")
    folder = DocumentFolder(name=name, parent_id=parent.id if parent else None, created_by=actor.id)
    db.add(folder)
    db.flush()
    _record_event(db, "FOLDER_CREATED", actor, folder=folder, details={"name": name})
    db.commit()
    db.refresh(folder)
    return folder


@router.put("/folders/{folder_id}", response_model=DocumentFolderResponse)
def update_folder(
    folder_id: int,
    payload: DocumentFolderUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    folder = db.get(DocumentFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    changes = payload.model_dump(exclude_unset=True)
    if "is_archived" in changes:
        _require_filing_manager(actor)
    parent = _validate_folder(db, changes.get("parent_id", folder.parent_id))
    cursor = parent
    while cursor is not None:
        if cursor.id == folder.id:
            raise HTTPException(status_code=400, detail="A folder cannot be moved inside itself")
        cursor = db.get(DocumentFolder, cursor.parent_id) if cursor.parent_id else None
    if "name" in changes:
        folder.name = changes["name"].strip()
    if "parent_id" in changes:
        folder.parent_id = parent.id if parent else None
    if "is_archived" in changes:
        folder.is_archived = changes["is_archived"]
    folder.updated_at = datetime.utcnow()
    _record_event(
        db,
        "FOLDER_ARCHIVED" if folder.is_archived else "FOLDER_UPDATED",
        actor,
        folder=folder,
        details=changes,
    )
    db.commit()
    db.refresh(folder)
    return folder


@router.get("", response_model=list[DocumentResponse])
def get_documents(
    search: str | None = None,
    document_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    folder_id: int | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    _actor: User = Depends(get_current_user),
):
    latest = select(
        Document.document_id.label("document_id"),
        func.max(Document.version).label("version"),
    ).group_by(Document.document_id).subquery()
    statement = select(Document).join(latest, and_(
        Document.document_id == latest.c.document_id,
        Document.version == latest.c.version,
    )).outerjoin(DocumentFolder, DocumentFolder.id == Document.folder_id).outerjoin(
        Property, Property.id == Document.property_id
    ).order_by(Document.created_at.desc()).limit(limit)
    if document_type:
        statement = statement.where(Document.document_type == document_type)
    if status_filter:
        statement = statement.where(Document.status == status_filter.upper())
    if folder_id is not None:
        statement = statement.where(Document.folder_id == folder_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(
            Document.document_name.ilike(pattern),
            Document.storage_path.ilike(pattern),
            Document.document_type.ilike(pattern),
            Document.document_id.ilike(pattern),
            Document.related_party_name.ilike(pattern),
            cast(Document.transaction_id, String).ilike(pattern),
            cast(Document.property_id, String).ilike(pattern),
            Document.transaction_reference.ilike(pattern),
            Document.property_listing_external_id.ilike(pattern),
            Document.property_listing_title.ilike(pattern),
            Document.related_party_external_id.ilike(pattern),
            DocumentFolder.name.ilike(pattern),
            Property.title.ilike(pattern),
        ))
    rows = db.execute(statement).scalars().all()
    return [_serialize_document(db, row) for row in rows]


@router.get("/{document_id}/versions", response_model=list[DocumentResponse])
def get_document_versions(
    document_id: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(get_current_user),
):
    versions = db.execute(
        select(Document).where(Document.document_id == document_id)
        .order_by(Document.version.desc())
    ).scalars().all()
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")
    return [_serialize_document(db, row) for row in versions]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    _actor: User = Depends(get_current_user),
):
    return _serialize_document(db, _document_or_404(db, document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_filing_manager(actor)
    versions = db.execute(
        select(Document)
        .where(Document.document_id == document_id)
        .order_by(Document.version.desc())
    ).scalars().all()
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")

    for version in versions:
        try:
            remove_document_file(version.storage_path)
            delete_document_metadata(version)
        except Exception as exc:
            logger.exception(
                "Document deletion failed (document_id=%s, version=%s)",
                document_id,
                version.version,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Could not delete document version {version.version} "
                    f"from storage ({type(exc).__name__}): {exc}"
                ),
            ) from exc

    row_ids = [version.id for version in versions]
    db.execute(
        delete(DocumentAuditEvent).where(
            DocumentAuditEvent.document_row_id.in_(row_ids)
        )
    )
    for version in versions:
        db.delete(version)
    _record_event(
        db,
        "DOCUMENT_DELETED",
        actor,
        details={
            "document_id": document_id,
            "versions": [version.version for version in versions],
            "deleted_at": datetime.utcnow().isoformat(),
        },
    )
    db.commit()
    return Response(status_code=204)


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    document_name: str | None = Form(default=None),
    document_type: str = Form(...),
    folder_id: int | None = Form(default=None),
    property_id: int | None = Form(default=None),
    transaction_id: int | None = Form(default=None),
    related_party_id: int | None = Form(default=None),
    related_party_name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    allow_duplicate: bool = Form(default=False),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    row = _upload_record(
        db, actor, file, document_name, document_type, folder_id, property_id,
        transaction_id, related_party_id, related_party_name, description,
        allow_duplicate=allow_duplicate,
    )
    return _serialize_document(db, row)


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_filing_manager(actor)
    document = _document_or_404(db, document_id)
    changes = payload.model_dump(exclude_unset=True)
    if "folder_id" in changes:
        folder = _validate_folder(db, changes["folder_id"])
        changes["folder_id"] = folder.id if folder else None
    if "property_id" in changes:
        _validate_property(db, changes["property_id"])
    old_folder_id = document.folder_id
    for key, value in changes.items():
        setattr(document, key, value.strip() or None if isinstance(value, str) else value)
    event = "DOCUMENT_MOVED" if old_folder_id != document.folder_id else "DOCUMENT_CLASSIFIED"
    _commit_document_change(db, document, actor, event, changes)
    return _serialize_document(db, document)


def _set_status(db: Session, document_id: str, actor: User, action: str) -> dict:
    _require_filing_manager(actor)
    document = _document_or_404(db, document_id)
    now = datetime.utcnow()
    if action == "confirm":
        if document.status not in {"PENDING_REVIEW", "DUPLICATE"}:
            raise HTTPException(status_code=409, detail="Only documents pending review can be confirmed")
        document.status = "CONFIRMED"
        document.confirmed_by = actor.id
        document.confirmed_at = now
        event = "DOCUMENT_CONFIRMED"
    elif action == "reject":
        if document.status not in {"PENDING_REVIEW", "DUPLICATE"}:
            raise HTTPException(status_code=409, detail="Only documents pending review can be rejected")
        document.status = "REJECTED"
        document.rejected_by = actor.id
        document.rejected_at = now
        event = "DOCUMENT_REJECTED"
    elif action == "archive":
        if document.status == "ARCHIVED":
            raise HTTPException(status_code=409, detail="Document is already archived")
        document.status = "ARCHIVED"
        document.archived_by = actor.id
        document.archived_at = now
        event = "DOCUMENT_ARCHIVED"
    else:
        if document.status != "ARCHIVED":
            raise HTTPException(status_code=409, detail="Only archived documents can be restored")
        document.status = "PENDING_REVIEW"
        document.archived_by = None
        document.archived_at = None
        event = "DOCUMENT_RESTORED"
    _commit_document_change(db, document, actor, event)
    return _serialize_document(db, document)


@router.post("/{document_id}/confirm", response_model=DocumentResponse)
def confirm_document(document_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return _set_status(db, document_id, actor, "confirm")


@router.post("/{document_id}/archive", response_model=DocumentResponse)
def archive_document(document_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return _set_status(db, document_id, actor, "archive")


@router.post("/{document_id}/restore", response_model=DocumentResponse)
def restore_document(document_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return _set_status(db, document_id, actor, "restore")


@router.post("/{document_id}/reject", response_model=DocumentResponse)
def reject_document(document_id: str, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return _set_status(db, document_id, actor, "reject")


@router.post("/{document_id}/new-version", response_model=DocumentResponse, status_code=201)
def create_document_version(
    document_id: str,
    file: UploadFile = File(...),
    document_name: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    folder_id: int | None = Form(default=None),
    property_id: int | None = Form(default=None),
    transaction_id: int | None = Form(default=None),
    related_party_id: int | None = Form(default=None),
    related_party_name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    allow_duplicate: bool = Form(default=False),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    _require_filing_manager(actor)
    previous = _document_or_404(db, document_id)
    if previous.status in {"ARCHIVED", "REJECTED"}:
        raise HTTPException(status_code=409, detail="Archived or rejected documents cannot be replaced")
    values = {
        "document_name": document_name or previous.document_name,
        "document_type": document_type or previous.document_type,
        "folder_id": folder_id if folder_id is not None else previous.folder_id,
        "property_id": property_id if property_id is not None else previous.property_id,
        "transaction_id": transaction_id if transaction_id is not None else previous.transaction_id,
        "related_party_id": related_party_id if related_party_id is not None else previous.related_party_id,
        "related_party_name": related_party_name or previous.related_party_name,
        "description": description if description is not None else previous.description,
    }
    previous_status = previous.status
    previous.status = "SUPERSEDED"
    previous.updated_at = datetime.utcnow()
    try:
        sync_document_metadata(previous)
        row = _upload_record(
            db, actor, file, values["document_name"], values["document_type"],
            values["folder_id"], values["property_id"], values["transaction_id"],
            values["related_party_id"], values["related_party_name"], values["description"],
            document_id=previous.document_id, version=previous.version + 1,
            allow_duplicate=allow_duplicate,
        )
    except Exception:
        db.rollback()
        previous.status = previous_status
        previous.updated_at = datetime.utcnow()
        try:
            sync_document_metadata(previous)
        except Exception:
            pass
        raise
    _record_event(db, "VERSION_REPLACED", actor, previous, details={"new_version": row.version})
    db.commit()
    return _serialize_document(db, row)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _actor: User = Depends(get_current_user),
):
    statement = select(Document).where(Document.document_id == document_id)
    if version is not None:
        statement = statement.where(Document.version == version)
    document = db.execute(statement.order_by(Document.version.desc())).scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    try:
        content = download_document_file(document.storage_path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The document file is currently unavailable") from exc
    from urllib.parse import quote

    filename = quote(document.document_name, safe="")
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )