"""File storage and cloud metadata synchronization for repository files.

Storage providers:
  * ``supabase`` – Supabase Storage bucket (service-role key, backend only)
  * ``local``    – files under ``DOCUMENT_STORAGE_DIR`` on the API server

The provider used for a stored object is recorded in ``storage_bucket``
(``local:<area>`` for local files, the bucket name for Supabase), so a file is
always read back from where it was written even if configuration changes.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.supabase import supabase
from app.models.document import Document

LOCAL_PREFIX = "local:"


class StorageError(RuntimeError):
    """The file could not be written to / read from the storage provider."""


class UnsupportedFileError(ValueError):
    """The upload is not a supported, well-formed document or image."""


@dataclass(frozen=True)
class FileKind:
    source_format: str  # PDF / DOCX / IMAGE
    mime_type: str
    extension: str


_IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png", {".png"}),
    (b"\xff\xd8\xff", "image/jpeg", {".jpg", ".jpeg"}),
    (b"II*\x00", "image/tiff", {".tif", ".tiff"}),
    (b"MM\x00*", "image/tiff", {".tif", ".tiff"}),
    (b"BM", "image/bmp", {".bmp"}),
)


def detect_file_kind(filename: str, content: bytes) -> FileKind:
    """Identify a file from its bytes; the uploaded name/MIME are not trusted."""
    extension = Path(filename).suffix.casefold()
    if content.startswith(b"%PDF-"):
        if extension != ".pdf":
            raise UnsupportedFileError("File content is a PDF but the extension is not .pdf")
        return FileKind("PDF", "application/pdf", ".pdf")
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileError("The file is a damaged ZIP/DOCX archive") from exc
        if "word/document.xml" in names and extension == ".docx":
            return FileKind(
                "DOCX",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
            )
        raise UnsupportedFileError("Only .docx Word documents are supported among ZIP formats")
    for signature, mime_type, extensions in _IMAGE_SIGNATURES:
        if content.startswith(signature):
            if extension not in extensions:
                raise UnsupportedFileError(
                    f"File content is {mime_type} but the extension is {extension or 'missing'}"
                )
            return FileKind("IMAGE", mime_type, extension)
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        if extension != ".webp":
            raise UnsupportedFileError("File content is WEBP but the extension is not .webp")
        return FileKind("IMAGE", "image/webp", ".webp")
    raise UnsupportedFileError(
        "Unsupported file type. Upload a PDF, DOCX, or image (PNG, JPEG, TIFF, BMP, WEBP)."
    )


def generated_storage_path(document_id: str, version: int, extension: str) -> str:
    """Server-generated object key; the uploaded filename is never used."""
    return f"{document_id}/v{version}/{uuid.uuid4().hex}{extension}"


def _local_root(area: str) -> Path:
    root = (Path(settings.DOCUMENT_STORAGE_DIR) / area).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _local_path(area: str, storage_path: str) -> Path:
    root = _local_root(area)
    target = (root / storage_path).resolve()
    if root not in target.parents:
        raise StorageError("Refusing a storage path outside the storage directory")
    return target


def _bucket_for(area: str) -> str:
    if settings.storage_backend == "local":
        return f"{LOCAL_PREFIX}{area}"
    if settings.storage_backend != "supabase":
        raise StorageError(
            f"Unknown DOCUMENT_STORAGE_BACKEND '{settings.DOCUMENT_STORAGE_BACKEND}'"
        )
    if not settings.cloud_configured:
        raise StorageError(
            "DOCUMENT_STORAGE_BACKEND=supabase but SUPABASE_URL / "
            "SUPABASE_SERVICE_ROLE_KEY are not set"
        )
    return settings.SUPABASE_MEDIA_BUCKET if area == "media" else settings.SUPABASE_DOCUMENTS_BUCKET


def store_file(area: str, storage_path: str, content: bytes, mime_type: str) -> str:
    """Write a file; returns the ``storage_bucket`` value to persist."""
    bucket = _bucket_for(area)
    try:
        if bucket.startswith(LOCAL_PREFIX):
            target = _local_path(area, storage_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise StorageError("A stored object already exists at this path")
            target.write_bytes(content)
        else:
            supabase.storage.from_(bucket).upload(
                storage_path,
                content,
                file_options={"content-type": mime_type, "upsert": "false"},
            )
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(f"{type(exc).__name__}: {exc}") from exc
    return bucket


def read_file(bucket: str, storage_path: str) -> bytes:
    try:
        if bucket.startswith(LOCAL_PREFIX):
            return _local_path(bucket[len(LOCAL_PREFIX):], storage_path).read_bytes()
        return supabase.storage.from_(bucket).download(storage_path)
    except Exception as exc:
        raise StorageError(f"{type(exc).__name__}: {exc}") from exc


def delete_file(bucket: str, storage_path: str) -> None:
    try:
        if bucket.startswith(LOCAL_PREFIX):
            _local_path(bucket[len(LOCAL_PREFIX):], storage_path).unlink(missing_ok=True)
        else:
            supabase.storage.from_(bucket).remove([storage_path])
    except Exception as exc:
        raise StorageError(f"{type(exc).__name__}: {exc}") from exc


# ---- backwards-compatible document helpers ---------------------------------

def upload_document_file(storage_path: str, content: bytes, mime_type: str) -> str:
    return store_file("documents", storage_path, content, mime_type)


def download_document_file(document: Document) -> bytes:
    return read_file(document.storage_bucket, document.storage_path)


def remove_document_file(document: Document) -> None:
    delete_file(document.storage_bucket, document.storage_path)


# ---- cloud metadata ----------------------------------------------------------

def _metadata_row(document: Document) -> dict:
    iso = lambda value: value.isoformat() if value else None  # noqa: E731
    return {
        "document_id": document.document_id,
        "version": document.version,
        "title": document.document_name,
        "file_name": document.document_name,
        "is_archived": document.status == "ARCHIVED",
        "document_name": document.document_name,
        "document_type": document.document_type,
        "folder_id": document.folder_id,
        "property_id": document.property_id,
        "property_listing_id": document.property_listing_id,
        "property_listing_external_id": document.property_listing_external_id,
        "property_listing_title": document.property_listing_title,
        "transaction_id": (
            str(document.transaction_id) if document.transaction_id is not None else None
        ),
        "transaction_reference": document.transaction_reference,
        "related_party_id": document.related_party_id,
        "related_party_name": document.related_party_name,
        "related_party_external_id": document.related_party_external_id,
        "description": document.description,
        "storage_path": document.storage_path,
        "storage_bucket": document.storage_bucket,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "file_hash": document.file_hash,
        "status": document.status,
        "uploaded_by": document.uploaded_by,
        "created_at": iso(document.created_at),
        "updated_at": iso(document.updated_at),
        "confirmed_by": document.confirmed_by,
        "confirmed_at": iso(document.confirmed_at),
        "archived_by": document.archived_by,
        "archived_at": iso(document.archived_at),
        "rejected_by": document.rejected_by,
        "rejected_at": iso(document.rejected_at),
        "duplicate_of_id": document.duplicate_of_id,
    }


def cloud_metadata_enabled() -> bool:
    return settings.CLOUD_SYNC_ENABLED and settings.cloud_configured


def sync_document_metadata(document: Document) -> None:
    """Upsert repository metadata into Supabase ``public.documents``."""
    supabase.table("documents").upsert(
        _metadata_row(document), on_conflict="document_id,version"
    ).execute()


def delete_document_metadata(document: Document) -> None:
    supabase.table("documents").delete().eq(
        "document_id", document.document_id
    ).eq("version", document.version).execute()


def try_sync_document_metadata(document: Document) -> str | None:
    """Best-effort cloud metadata sync. Updates ``document.sync_status``.

    Returns the error text when synchronization failed; the local record is
    authoritative and stays PENDING until a later sync succeeds.
    """
    if not cloud_metadata_enabled():
        document.sync_status = "LOCAL_ONLY"
        return None
    try:
        sync_document_metadata(document)
    except Exception as exc:
        document.sync_status = "PENDING"
        return f"{type(exc).__name__}: {exc}"
    document.sync_status = "SYNCED"
    return None
