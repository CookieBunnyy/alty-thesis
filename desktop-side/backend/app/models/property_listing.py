from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    # The lot's size in square metres (shown as m² or hectares).
    lot_area_sqm: Mapped[float | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    # The lot's outline as a GeoJSON Polygon drawn by staff (see
    # services/lot_geometry.py); measurements are calculated from it.
    boundary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    boundary_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    boundary_updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    @property
    def boundary_measurements(self) -> dict | None:
        """Area, perimeter and side lengths estimated from the boundary."""
        from app.services.lot_geometry import measure

        return measure(self.boundary)

    # Photos uploaded in Digital Preview (property_media), oldest first.
    uploaded_media: Mapped[list["PropertyMedia"]] = relationship(  # noqa: F821
        "PropertyMedia", order_by="PropertyMedia.created_at", lazy="selectin", viewonly=True,
    )

    @property
    def media_ids(self) -> list[int]:
        """Uploaded photos that passed the quality check (shown on the listing)."""
        return [m.id for m in self.uploaded_media if m.quality_status in ("GOOD", "ACCEPTABLE")]

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
    # Developer / partner of this listing (kept in ALTY; not a Supabase column).
    partner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True,
    )