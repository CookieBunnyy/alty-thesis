from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentFolder(Base):
    __tablename__ = "document_folders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_folders.id"), nullable=True, index=True
    )
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_folders.id"), nullable=True, index=True
    )
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("properties.id"), nullable=True, index=True
    )
    property_listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    property_listing_external_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    property_listing_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_party_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_party_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    related_party_external_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(160), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="PROCESSING", nullable=False, index=True
    )
    # Processing outcome (business-data processing, distinct from storage).
    processing_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_format: Mapped[str | None] = mapped_column(String(24), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Cloud metadata synchronization state (storage upload is separate).
    sync_status: Mapped[str] = mapped_column(
        String(24), default="PENDING", server_default="SYNCED", nullable=False
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))


class DocumentAuditEvent(Base):
    __tablename__ = "document_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_row_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    folder_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_folders.id"), nullable=True, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )