from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: int
    document_id: str
    document_name: str
    document_type: str
    folder_id: int | None = None
    folder_name: str | None = None
    property_id: int | None = None
    property_name: str | None = None
    property_listing_id: int | None = None
    property_listing_external_id: str | None = None
    property_listing_title: str | None = None
    transaction_id: int | None = None
    transaction_reference: str | None = None
    related_party_id: int | None = None
    related_party_name: str | None = None
    related_party_external_id: str | None = None
    description: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    # Business-data processing outcome (distinct from file storage).
    processing_stage: str | None = None
    processing_error: str | None = None
    extraction_method: str | None = None
    source_format: str | None = None
    processed_at: datetime | None = None
    processing: dict[str, Any] = Field(default_factory=dict)
    # File storage + cloud metadata state.
    stored: bool = True
    sync_status: str | None = None
    mime_type: str
    file_size: int
    version: int
    status: str
    uploaded_by: int
    uploaded_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    archived_by: int | None = None
    archived_at: datetime | None = None
    rejected_by: int | None = None
    rejected_at: datetime | None = None
    duplicate_of_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    parent_id: int | None = None


class DocumentFolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: int | None = None
    is_archived: bool | None = None


class DocumentFolderResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    """Filing metadata only. Entity links are derived by processing."""

    model_config = ConfigDict(extra="forbid")

    document_name: str | None = Field(default=None, min_length=1, max_length=255)
    folder_id: int | None = None
    description: str | None = None


class DocumentReprocess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str | None = Field(default=None, max_length=80)