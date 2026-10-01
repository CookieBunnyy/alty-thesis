from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PropertyListing(Base):
    __tablename__ = "property_listings"

    # Original ID from Supabase listings table
    listing_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    external_listing_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True, unique=True, index=True
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    price_total: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    initial_dp: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    monthly_rate: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    num_bedrooms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    num_bathrooms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    layout_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    village_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    lat: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    lng: Mapped[float | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    photos: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    amenity_list: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    nearby_places: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    nearby_establishments: Mapped[dict | list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    has_balcony: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    has_kitchen: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    has_backyard: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    has_garage: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    garage_spaces: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="AVAILABLE",
        server_default="AVAILABLE",
        nullable=False,
        index=True,
    )

    # Local synchronization metadata
    sync_status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        nullable=False,
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Lifecycle timestamps (NULL for rows that predate tracking).
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=True,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=True,
    )

    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )