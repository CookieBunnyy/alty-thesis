from app.core.config import settings
from app.core.supabase import supabase
from app.models.document import Document


def ensure_document_storage_configured() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase document storage is not configured on the server.")


def upload_document_file(storage_path: str, content: bytes, mime_type: str) -> None:
    ensure_document_storage_configured()
    supabase.storage.from_(settings.SUPABASE_DOCUMENTS_BUCKET).upload(
        storage_path,
        content,
        file_options={"content-type": mime_type, "upsert": "false"},
    )


def remove_document_file(storage_path: str) -> None:
    ensure_document_storage_configured()
    supabase.storage.from_(settings.SUPABASE_DOCUMENTS_BUCKET).remove([storage_path])


def download_document_file(storage_path: str) -> bytes:
    ensure_document_storage_configured()
    return supabase.storage.from_(settings.SUPABASE_DOCUMENTS_BUCKET).download(storage_path)


def sync_document_metadata(document: Document) -> None:
    ensure_document_storage_configured()
    supabase.table("documents").upsert(
        {
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
                str(document.transaction_id)
                if document.transaction_id is not None
                else None
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
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "confirmed_by": document.confirmed_by,
            "confirmed_at": document.confirmed_at.isoformat() if document.confirmed_at else None,
            "archived_by": document.archived_by,
            "archived_at": document.archived_at.isoformat() if document.archived_at else None,
            "rejected_by": document.rejected_by,
            "rejected_at": document.rejected_at.isoformat() if document.rejected_at else None,
            "duplicate_of_id": document.duplicate_of_id,
        },
        on_conflict="document_id,version",
    ).execute()


def delete_document_metadata(document: Document) -> None:
    ensure_document_storage_configured()
    supabase.table("documents").delete().eq(
        "document_id", document.document_id
    ).eq("version", document.version).execute()