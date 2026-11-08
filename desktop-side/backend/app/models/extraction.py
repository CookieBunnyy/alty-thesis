"""Configurable document schemas and reviewed extraction results.

Interview: the commission voucher is the main document Abellar keeps, but no
sample (and so no field labels) was provided. A voucher's extraction is
therefore driven by a schema that management configures once a real voucher
is available; until then every "label: value" pair found is kept and shown
for human verification and correction. The original file is never changed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

FIELD_TYPES = ("text", "money", "date", "number")
VERIFICATION_STATUSES = ("NEEDS_REVIEW", "VERIFIED")


class DocumentSchema(Base):
    """The fields to look for in one document type.

    ``fields`` = [{"key", "label", "aliases": [printed labels], "type", "required"}]."""

    __tablename__ = "document_schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)


class DocumentExtraction(Base):
    """What was read from one document, and its human verification."""

    __tablename__ = "document_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_row_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    # Every "label: value" pair found in the text, in reading order.
    detected_pairs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Schema fields filled from the detected pairs (key -> value), at extraction time.
    mapped_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # The values a person confirmed or corrected (key -> value).
    verified_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Records the document is linked to: commission_id, agent_id, listing_id, transaction_id.
    links: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NEEDS_REVIEW")
    verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow,
                                                 onupdate=datetime.utcnow)
