from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PropertyMedia(Base):
    """An uploaded property image with its OpenCV quality analysis."""

    __tablename__ = "property_media"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("property_listings.listing_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    contrast: Mapped[float | None] = mapped_column(Float, nullable=True)
    # GOOD / ACCEPTABLE / POOR / INVALID
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quality_issues: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
