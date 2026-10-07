import hashlib
import logging
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import String, and_, cast, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_filing
from app.models.document import Document, DocumentAuditEvent, DocumentFolder
from app.models.property_listing import PropertyListing
from app.models.user import User
from app.schemas.document import (
    DocumentFolderCreate,
    DocumentFolderResponse,
    DocumentFolderUpdate,
    DocumentReprocess,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.document_filing import (
    DEFAULT_FOLDERS,
    FINANCIAL_SUBFOLDERS,
    file_document,
    folder_path,
    is_category_folder,
)
from app.services.audit import record_audit
from app.services.cloud_sync import try_push_pending
from app.services.document_classification import AUTO, canonical_type, type_catalog
from app.services.document_processing import process_document_content
from app.services.document_storage import (
    FileKind,
    StorageError,
    UnsupportedFileError,
    delete_document_metadata,
    detect_file_kind,
    download_document_file,
    generated_storage_path,
    remove_document_file,
    try_sync_document_metadata,
    upload_document_file,
    cloud_metadata_enabled,
)

router = APIRouter(prefix="/documents", tags=["Document Repository"])
logger = logging.getLogger(__name__)

PROCESSING_STATUSES = {"PROCESSING", "SUCCESS", "FAILED"}
DOCUMENT_STATUSES = PROCESSING_STATUSES | {"ARCHIVED", "SUPERSEDED"}
# Category folders and automatic filing: services/document_filing.py


def _document_or_404(db: Session, document_id: str) -> Document:
    document = db.execute(
        select(Document).where(Document.document_id == document_id)
        .order_by(Document.version.desc())
    ).scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _latest_processing(db: Session, document: Document) -> dict:
    event = db.execute(
        select(DocumentAuditEvent)
        .where(
            DocumentAuditEvent.document_row_id == document.id,
            DocumentAuditEvent.event_type == "DOCUMENT_PROCESSING",
        )
        .order_by(DocumentAuditEvent.id.desc())
        .limit(1)
    ).scalars().first()
    return dict(event.details) if event else {}


def _serialize_document(db: Session, document: Document, processing: dict | None = None) -> dict:
    extra = {document.id: processing} if processing is not None else None
    return _serialize_documents(db, [document], processing=extra)[0]


def _serialize_documents(db: Session, documents: list[Document],
                         processing: dict[int, dict] | None = None) -> list[dict]:
    """Serialize many documents with a fixed number of queries.

    Folders, listings, uploaders and the latest processing result are loaded
    for the whole page at once — one query each — instead of per document,
    because every query is a network round trip to the database."""
    if not documents:
        return []
    folders = {f.id: f for f in db.execute(select(DocumentFolder)).scalars()}

    def path_of(folder_id: int | None) -> str | None:
        names, seen = [], set()
        while folder_id is not None and folder_id in folders and folder_id not in seen:
            seen.add(folder_id)
            names.append(folders[folder_id].name)
            folder_id = folders[folder_id].parent_id
        return " / ".join(reversed(names)) or None

    listing_ids = {d.property_listing_id for d in documents if d.property_listing_id}
    titles = dict(db.execute(
        select(PropertyListing.listing_id, PropertyListing.title)
        .where(PropertyListing.listing_id.in_(listing_ids))
    ).all()) if listing_ids else {}
    user_ids = {d.uploaded_by for d in documents if d.uploaded_by}
    names = dict(db.execute(
        select(User.id, User.full_name).where(User.id.in_(user_ids))
    ).all()) if user_ids else {}
    processing = dict(processing or {})
    missing = [d.id for d in documents if d.id not in processing]
    if missing:
        latest = (
            select(DocumentAuditEvent.document_row_id, DocumentAuditEvent.details)
            .where(DocumentAuditEvent.document_row_id.in_(missing),
                   DocumentAuditEvent.event_type == "DOCUMENT_PROCESSING")
            .order_by(DocumentAuditEvent.document_row_id, DocumentAuditEvent.id.desc())
            .distinct(DocumentAuditEvent.document_row_id)
        )
        for row_id, details in db.execute(latest).all():
            processing[row_id] = dict(details or {})

    results = []
    for document in documents:
        result = DocumentResponse.model_validate(document).model_dump(mode="json")
        folder = folders.get(document.folder_id) if document.folder_id else None
        title = titles.get(document.property_listing_id) if document.property_listing_id else None
        details = dict(processing.get(document.id) or {})
        details.pop("entity_events", None)
        result.update(
            folder_name=folder.name if folder else None,
            folder_path=path_of(document.folder_id),
            property_name=title or document.property_listing_title,
            property_listing_title=title or document.property_listing_title,
            extracted_fields=details.get("extracted_fields") or {},
            processing=details,
            uploaded_by_name=names.get(document.uploaded_by),
        )
        results.append(result)
    return results


def _record_event(db: Session, event_type: str, actor: User, document: Document | None = None,
                  folder: DocumentFolder | None = None, details: dict | None = None) -> None:
    db.add(DocumentAuditEvent(
        document_row_id=document.id if document else None,
        folder_id=folder.id if folder else None,
        actor_id=actor.id,
        event_type=event_type,
        details=details or {},
    ))


def _descendant_folder_ids(db: Session, folder_id: int) -> set[int]:
    """A folder and everything under it (auto-filed name folders included)."""
    children: dict[int | None, list[int]] = {}
    for fid, parent in db.execute(select(DocumentFolder.id, DocumentFolder.parent_id)).all():
        children.setdefault(parent, []).append(fid)
    found, stack = {folder_id}, [folder_id]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in found:
                found.add(child)
                stack.append(child)
    return found


def _validate_folder(db: Session, folder_id: int | None) -> DocumentFolder | None:
    if folder_id is None:
        return None
    folder = db.get(DocumentFolder, folder_id)
    if folder is None or folder.is_archived:
        raise HTTPException(status_code=404, detail="Active folder not found")
    return folder


def _read_upload(upload: UploadFile) -> tuple[str, bytes, str, FileKind]:
    # Only the base name is kept, for display; it never becomes a storage path.
    name = (upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    name = "".join(ch for ch in name if ch.isprintable())[:255]
    if not name:
        raise HTTPException(status_code=400, detail="Choose a file to upload")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = upload.file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The selected file is empty")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Files must be {settings.MAX_UPLOAD_MB} MB or smaller")
    try:
        kind = detect_file_kind(name, content)
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return name, content, hashlib.sha256(content).hexdigest(), kind


def _find_duplicate(db: Session, file_hash: str, document_id: str | None) -> Document | None:
    statement = select(Document).where(Document.file_hash == file_hash)
    if document_id:
        statement = statement.where(Document.document_id != document_id)
    return db.execute(statement.order_by(Document.created_at.desc())).scalars().first()


def _declared_type(value: str | None) -> str:
    code = canonical_type(value) if value else AUTO
    if code is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported document type '{value}'. See GET /api/v1/documents/types.",
        )
    return code


def _run_processing(db: Session, actor: User, document: Document, filename: str,
                    content: bytes, source_format: str, declared: str) -> dict:
    processing = process_document_content(
        db, document, filename, content, source_format=source_format, declared_type=declared
    )
    events = processing.pop("entity_events", [])
    _record_event(db, "DOCUMENT_PROCESSING", actor, document, details=processing)
    filed = file_document(db, document, processing, actor.id)
    if filed:
        processing["filed_to"] = filed["path"]
        for name in filed["created"]:
            _record_event(db, "FOLDER_CREATED", actor, document, details={"name": name, "automatic": True})
        _record_event(db, "DOCUMENT_FILED", actor, document, details={"folder": filed["path"], "automatic": True})
        record_audit(db, "DOCUMENT_FILED", actor=actor, entity_type="documents", entity_id=document.document_id,
                     details={"folder": filed["path"], "created_folders": filed["created"]})
    record_audit(
        db,
        "DOCUMENT_PROCESSED" if processing["status"] == "SUCCESS" else "DOCUMENT_PROCESSING_FAILED",
        actor=actor,
        entity_type="documents",
        entity_id=document.document_id,
        result=processing["status"],
        details={
            "version": document.version,
            "document_type": processing.get("document_type"),
            "stage": processing.get("stage"),
            "reason": processing.get("error_reason"),
            "created_records": processing.get("created_records"),
            "updated_records": processing.get("updated_records"),
        },
    )
    for event in events:
        record_audit(
            db, event["action"], actor=actor, entity_type=event["entity_type"],
            entity_id=event["entity_id"],
            details={**event["details"], "source_document_id": document.document_id},
        )
    return processing


def _after_commit_sync(db: Session, document: Document) -> None:
    """Cloud metadata + derived-record push; failures stay PENDING, never 5xx."""
    if not cloud_metadata_enabled():
        document.sync_status = "LOCAL_ONLY"
        db.commit()
        return
    error = try_sync_document_metadata(document)
    if error:
        logger.warning("Document metadata sync pending for %s: %s", document.document_id, error)
    db.commit()
    try_push_pending(db)


def _upload_record(db: Session, actor: User, upload: UploadFile, document_name: str | None,
                   document_type: str | None, folder_id: int | None, description: str | None,
                   document_id: str | None = None, version: int = 1,
                   allow_duplicate: bool = False) -> tuple[Document, dict]:
    declared = _declared_type(document_type)
    folder = _validate_folder(db, folder_id)
    filename, content, file_hash, kind = _read_upload(upload)
    duplicate = _find_duplicate(db, file_hash, document_id)
    if duplicate and not allow_duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This exact file was already uploaded.",
                "existing_document": _serialize_document(db, duplicate),
            },
        )

    document_id = document_id or str(uuid.uuid4())
    storage_path = generated_storage_path(document_id, version, kind.extension)
    try:
        bucket = upload_document_file(storage_path, content, kind.mime_type)
    except StorageError as exc:
        logger.error("Document storage failed (document_id=%s): %s", document_id, exc)
        record_audit(db, "DOCUMENT_UPLOAD_FAILED", actor=actor, entity_type="documents",
                     entity_id=document_id, result="FAILED",
                     details={"stage": "STORAGE", "backend": settings.storage_backend,
                              "reason": str(exc), "filename": filename})
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "message": "The file could not be stored, so nothing was recorded.",
                "stage": "STORAGE",
                "storage_backend": settings.storage_backend,
                "reason": str(exc),
            },
        ) from exc

    now = datetime.utcnow()
    document = Document(
        document_id=document_id,
        document_name=(document_name or filename).strip()[:255],
        document_type=declared if declared != AUTO else "UNCLASSIFIED",
        folder_id=folder.id if folder else None,
        description=description,
        storage_path=storage_path,
        storage_bucket=bucket,
        mime_type=kind.mime_type,
        file_size=len(content),
        file_hash=file_hash,
        version=version,
        status="PROCESSING",
        sync_status="PENDING",
        uploaded_by=actor.id,
        duplicate_of_id=duplicate.id if duplicate else None,
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(document)
        db.flush()
        _record_event(db, "VERSION_REPLACED" if version > 1 else "DOCUMENT_UPLOADED", actor, document,
                      details={"version": version, "filename": filename,
                               "possible_duplicate_of": duplicate.document_id if duplicate else None})
        record_audit(db, "DOCUMENT_UPLOADED", actor=actor, entity_type="documents",
                     entity_id=document_id,
                     details={"version": version, "filename": filename, "size": len(content),
                              "format": kind.source_format, "storage": bucket.split(":")[0]})
        processing = _run_processing(db, actor, document, filename, content,
                                     kind.source_format, declared)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Local document record failed (document_id=%s)", document_id)
        try:
            remove_document_file(document)
        except StorageError:
            logger.warning("Orphaned stored file %s/%s", bucket, storage_path)
        raise HTTPException(
            status_code=500,
            detail={"message": "The document record could not be saved locally.",
                    "stage": "LOCAL_RECORD", "reason": f"{type(exc).__name__}: {exc}"},
        ) from exc
    db.refresh(document)
    _after_commit_sync(db, document)
    return document, processing


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@router.get("/types")
def get_document_types(_actor: User = Depends(get_current_user)):
    """Document types the processing engine supports (drives the UI list)."""
    return [{"code": AUTO, "label": "Auto-detect", "processing": "Classified from content"},
            *type_catalog()]


@router.get("/folders", response_model=list[DocumentFolderResponse])
def get_folders(include_archived: bool = False, db: Session = Depends(get_db),
                actor: User = Depends(get_current_user)):
    parents: dict[str, DocumentFolder] = {}
    created = False
    # One query for the top-level folders and one for Financial's, rather than
    # one per default folder (each query is a round trip to the database).
    top = {}
    for folder in db.execute(select(DocumentFolder).where(DocumentFolder.parent_id.is_(None))
                             .order_by(DocumentFolder.id)).scalars():
        top.setdefault(folder.name, folder)
    for name in DEFAULT_FOLDERS:
        folder = top.get(name)
        if folder is None:
            folder = DocumentFolder(name=name, created_by=actor.id)
            db.add(folder)
            db.flush()
            _record_event(db, "FOLDER_CREATED", actor, folder=folder, details={"name": name})
            created = True
        parents[name] = folder
    parent = parents["Financial"]
    children = {}
    for folder in db.execute(select(DocumentFolder).where(DocumentFolder.parent_id == parent.id)
                             .order_by(DocumentFolder.id)).scalars():
        children.setdefault(folder.name, folder)
    for name in FINANCIAL_SUBFOLDERS:
        folder = children.get(name)
        if folder is None:
            folder = DocumentFolder(name=name, parent_id=parent.id, created_by=actor.id)
            db.add(folder)
            db.flush()
            _record_event(db, "FOLDER_CREATED", actor, folder=folder, details={"name": name})
            created = True
    if created:
        db.commit()
    statement = select(DocumentFolder).order_by(DocumentFolder.name)
    if not include_archived:
        statement = statement.where(DocumentFolder.is_archived.is_(False))
    return db.execute(statement).scalars().all()


@router.post("/folders", response_model=DocumentFolderResponse, status_code=201)
def create_folder(payload: DocumentFolderCreate, db: Session = Depends(get_db),
                  actor: User = Depends(get_current_user)):
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
def update_folder(folder_id: int, payload: DocumentFolderUpdate, db: Session = Depends(get_db),
                  actor: User = Depends(get_current_user)):
    folder = db.get(DocumentFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    changes = payload.model_dump(exclude_unset=True)
    if "is_archived" in changes:
        require_filing(actor)
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
    _record_event(db, "FOLDER_ARCHIVED" if folder.is_archived else "FOLDER_UPDATED", actor,
                  folder=folder, details=changes)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db),
                  actor: User = Depends(get_current_user)):
    """Delete a folder and its sub-folders. Documents are never deleted with
    it: they move to the folder's parent (or to no folder at the top level).
    The standard category folders can't be deleted — filing relies on them."""
    require_filing(actor)
    folder = db.get(DocumentFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if is_category_folder(db, folder.id):
        raise HTTPException(status_code=409, detail=f"“{folder.name}” is a standard folder and can't be deleted")
    path = folder_path(db, folder.id)
    subtree = _descendant_folder_ids(db, folder.id)
    destination = folder.parent_id
    moved = db.execute(
        select(func.count(func.distinct(Document.document_id))).where(Document.folder_id.in_(subtree))
    ).scalar_one()
    db.execute(update(Document).where(Document.folder_id.in_(subtree)).values(folder_id=destination))
    # History entries keep their details; they just no longer point at the folder.
    db.execute(update(DocumentAuditEvent).where(DocumentAuditEvent.folder_id.in_(subtree)).values(folder_id=None))
    db.execute(update(DocumentFolder).where(DocumentFolder.id.in_(subtree)).values(parent_id=None))
    db.execute(delete(DocumentFolder).where(DocumentFolder.id.in_(subtree)))
    moved_to = folder_path(db, destination)
    details = {"folder": path, "subfolders": len(subtree) - 1, "moved_documents": int(moved),
               "moved_to": moved_to}
    _record_event(db, "FOLDER_DELETED", actor, details=details)
    record_audit(db, "FOLDER_DELETED", actor=actor, entity_type="document_folders",
                 entity_id=str(folder_id), details=details)
    db.commit()
    return {"deleted": path, **details}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DocumentResponse])
def get_documents(
    search: str | None = None,
    document_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    folder_id: int | None = None,
    include_subfolders: bool = True,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
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
    )).outerjoin(DocumentFolder, DocumentFolder.id == Document.folder_id)
    if document_type:
        statement = statement.where(Document.document_type == (canonical_type(document_type) or document_type))
    if status_filter:
        statement = statement.where(Document.status == status_filter.upper())
    if folder_id is not None:
        ids = _descendant_folder_ids(db, folder_id) if include_subfolders else {folder_id}
        statement = statement.where(Document.folder_id.in_(ids))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(
            Document.document_name.ilike(pattern),
            Document.document_type.ilike(pattern),
            Document.document_id.ilike(pattern),
            Document.related_party_name.ilike(pattern),
            Document.transaction_reference.ilike(pattern),
            Document.property_listing_external_id.ilike(pattern),
            Document.property_listing_title.ilike(pattern),
            Document.related_party_external_id.ilike(pattern),
            Document.processing_error.ilike(pattern),
            cast(Document.property_listing_id, String).ilike(pattern),
            DocumentFolder.name.ilike(pattern),
        ))
    rows = db.execute(
        statement.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return _serialize_documents(db, list(rows))


@router.get("/summary")
def get_document_summary(db: Session = Depends(get_db), _actor: User = Depends(get_current_user)):
    latest = select(Document.document_id, func.max(Document.version).label("version")).group_by(
        Document.document_id).subquery()
    rows = db.execute(
        select(Document.status, func.count()).join(latest, and_(
            Document.document_id == latest.c.document_id, Document.version == latest.c.version,
        )).group_by(Document.status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}
    return {"total": sum(counts.values()), "by_status": counts,
            **{status.lower(): counts.get(status, 0) for status in DOCUMENT_STATUSES}}


@router.post("/upload", response_model=DocumentResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    document_name: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    folder_id: int | None = Form(default=None),
    description: str | None = Form(default=None),
    allow_duplicate: bool = Form(default=False),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Store the file, then process it automatically.

    HTTP 201 means the file is stored; ``status`` (SUCCESS/FAILED) and
    ``processing`` report the separate business-data processing outcome.
    """
    row, processing = _upload_record(db, actor, file, document_name, document_type, folder_id,
                                     description, allow_duplicate=allow_duplicate)
    return _serialize_document(db, row, processing)


@router.get("/{document_id}/versions", response_model=list[DocumentResponse])
def get_document_versions(document_id: str, db: Session = Depends(get_db),
                          _actor: User = Depends(get_current_user)):
    versions = db.execute(
        select(Document).where(Document.document_id == document_id).order_by(Document.version.desc())
    ).scalars().all()
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_documents(db, list(versions))


@router.get("/{document_id}/audit")
def get_document_audit(document_id: str, db: Session = Depends(get_db),
                       _actor: User = Depends(get_current_user)):
    versions = db.execute(select(Document.id, Document.version).where(
        Document.document_id == document_id)).all()
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")
    version_of = {row_id: version for row_id, version in versions}
    events = db.execute(
        select(DocumentAuditEvent).where(DocumentAuditEvent.document_row_id.in_(version_of))
        .order_by(DocumentAuditEvent.id)
    ).scalars().all()
    actors = {user.id: user.username for user in db.execute(select(User)).scalars()}
    return [
        {
            "id": event.id,
            "version": version_of.get(event.document_row_id),
            "event_type": event.event_type,
            "actor": actors.get(event.actor_id, "SYSTEM"),
            "created_at": event.created_at,
            "details": {key: value for key, value in (event.details or {}).items()
                        if key != "entity_events"},
        }
        for event in events
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db),
                 _actor: User = Depends(get_current_user)):
    return _serialize_document(db, _document_or_404(db, document_id))


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: str, payload: DocumentUpdate, db: Session = Depends(get_db),
                    actor: User = Depends(require_filing)):
    document = _document_or_404(db, document_id)
    changes = payload.model_dump(exclude_unset=True)
    if "folder_id" in changes:
        folder = _validate_folder(db, changes["folder_id"])
        changes["folder_id"] = folder.id if folder else None
    old_folder_id = document.folder_id
    for key, value in changes.items():
        setattr(document, key, (value.strip() or None) if isinstance(value, str) else value)
    document.updated_at = datetime.utcnow()
    document.sync_status = "PENDING"
    _record_event(db, "DOCUMENT_MOVED" if old_folder_id != document.folder_id else "DOCUMENT_UPDATED",
                  actor, document, details=changes)
    db.commit()
    _after_commit_sync(db, document)
    return _serialize_document(db, document)


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(document_id: str, payload: DocumentReprocess | None = None,
                       db: Session = Depends(get_db), actor: User = Depends(require_filing)):
    """Run processing again on the stored file (e.g. after a missing property
    document was uploaded). Idempotent for documents that already succeeded."""
    document = _document_or_404(db, document_id)
    if document.status in {"ARCHIVED", "SUPERSEDED"}:
        raise HTTPException(status_code=409, detail=f"{document.status} documents cannot be reprocessed")
    declared = _declared_type(payload.document_type if payload and payload.document_type else None)
    try:
        content = download_document_file(document)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail={
            "message": "The stored file could not be read", "stage": "STORAGE", "reason": str(exc)
        }) from exc
    kind = detect_file_kind(f"file{_extension_of(document)}", content)
    document.status = "PROCESSING"
    processing = _run_processing(db, actor, document, document.document_name, content,
                                 kind.source_format, declared)
    document.updated_at = datetime.utcnow()
    document.sync_status = "PENDING"
    db.commit()
    _after_commit_sync(db, document)
    return _serialize_document(db, document, processing)


def _extension_of(document: Document) -> str:
    return "." + document.storage_path.rsplit(".", 1)[-1] if "." in document.storage_path else ""


def _set_archive_state(db: Session, document_id: str, actor: User, archive: bool) -> dict:
    document = _document_or_404(db, document_id)
    now = datetime.utcnow()
    if archive:
        if document.status == "ARCHIVED":
            raise HTTPException(status_code=409, detail="Document is already archived")
        previous = document.status
        document.status, document.archived_by, document.archived_at = "ARCHIVED", actor.id, now
        event, details = "DOCUMENT_ARCHIVED", {"previous_status": previous}
    else:
        if document.status != "ARCHIVED":
            raise HTTPException(status_code=409, detail="Only archived documents can be restored")
        restored = _latest_processing(db, document).get("status") or "FAILED"
        document.status, document.archived_by, document.archived_at = restored, None, None
        event, details = "DOCUMENT_RESTORED", {"restored_status": restored}
    document.updated_at = now
    document.sync_status = "PENDING"
    _record_event(db, event, actor, document, details=details)
    record_audit(db, event, actor=actor, entity_type="documents", entity_id=document_id, details=details)
    db.commit()
    _after_commit_sync(db, document)
    return _serialize_document(db, document)


@router.post("/{document_id}/archive", response_model=DocumentResponse)
def archive_document(document_id: str, db: Session = Depends(get_db),
                     actor: User = Depends(require_filing)):
    return _set_archive_state(db, document_id, actor, archive=True)


@router.post("/{document_id}/restore", response_model=DocumentResponse)
def restore_document(document_id: str, db: Session = Depends(get_db),
                     actor: User = Depends(require_filing)):
    return _set_archive_state(db, document_id, actor, archive=False)


@router.post("/{document_id}/new-version", response_model=DocumentResponse, status_code=201)
def create_document_version(
    document_id: str,
    file: UploadFile = File(...),
    document_name: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    folder_id: int | None = Form(default=None),
    description: str | None = Form(default=None),
    allow_duplicate: bool = Form(default=False),
    db: Session = Depends(get_db),
    actor: User = Depends(require_filing),
):
    previous = _document_or_404(db, document_id)
    if previous.status == "ARCHIVED":
        raise HTTPException(status_code=409, detail="Archived documents cannot be replaced")
    row, processing = _upload_record(
        db, actor, file, document_name or previous.document_name,
        document_type or previous.document_type,
        folder_id if folder_id is not None else previous.folder_id,
        description if description is not None else previous.description,
        document_id=previous.document_id, version=previous.version + 1,
        allow_duplicate=allow_duplicate,
    )
    previous.status = "SUPERSEDED"
    previous.updated_at = datetime.utcnow()
    previous.sync_status = "PENDING"
    _record_event(db, "VERSION_REPLACED", actor, previous, details={"new_version": row.version})
    db.commit()
    _after_commit_sync(db, previous)
    return _serialize_document(db, row, processing)


@router.get("/{document_id}/download")
def download_document(document_id: str, version: int | None = Query(default=None, ge=1),
                      db: Session = Depends(get_db), _actor: User = Depends(get_current_user)):
    statement = select(Document).where(Document.document_id == document_id)
    if version is not None:
        statement = statement.where(Document.version == version)
    document = db.execute(statement.order_by(Document.version.desc())).scalars().first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document version not found")
    try:
        content = download_document_file(document)
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="The document file is currently unavailable") from exc
    filename = quote(document.document_name, safe="")
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db),
                    actor: User = Depends(require_filing)):
    """Delete all versions and files. Audit history is kept (row links become NULL)."""
    versions = db.execute(
        select(Document).where(Document.document_id == document_id).order_by(Document.version.desc())
    ).scalars().all()
    if not versions:
        raise HTTPException(status_code=404, detail="Document not found")
    for version in versions:
        try:
            remove_document_file(version)
        except StorageError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not delete version {version.version} from storage: {exc}",
            ) from exc
        if cloud_metadata_enabled():
            try:
                delete_document_metadata(version)
            except Exception:
                logger.warning("Cloud metadata for %s v%s not deleted", document_id, version.version)
    details = {"document_id": document_id, "versions": [v.version for v in versions],
               "document_name": versions[0].document_name, "status": versions[0].status}
    row_ids = [version.id for version in versions]
    db.execute(
        update(Document).where(Document.duplicate_of_id.in_(row_ids)).values(duplicate_of_id=None)
    )
    for version in versions:
        db.delete(version)
    db.flush()
    _record_event(db, "DOCUMENT_DELETED", actor, details=details)
    record_audit(db, "DOCUMENT_DELETED", actor=actor, entity_type="documents",
                 entity_id=document_id, details=details)
    db.commit()
    return Response(status_code=204)
