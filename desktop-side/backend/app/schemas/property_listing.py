from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PropertyStatus = Literal[
    "AVAILABLE",
    "RESERVED",
    "SOLD",
    "ON_HOLD",
    "UNAVAILABLE",
]


class PropertyListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=100)
    price_total: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    initial_dp: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    monthly_rate: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    num_bedrooms: int | None = Field(default=None, ge=0)
    num_bathrooms: int | None = Field(default=None, ge=0)
    layout_type: str | None = Field(default=None, max_length=255)
    village_name: str | None = Field(default=None, max_length=255)
    lat: Decimal | None = Field(
        default=None, ge=-90, le=90, max_digits=10, decimal_places=6
    )
    lng: Decimal | None = Field(
        default=None, ge=-180, le=180, max_digits=10, decimal_places=6
    )
    photos: list[str] = Field(default_factory=list)
    amenity_list: dict | list | None = None
    nearby_places: dict | list | None = None
    details: str | None = None
    nearby_establishments: dict | list | None = None
    has_balcony: bool = False
    has_kitchen: bool = False
    has_backyard: bool = False
    has_garage: bool = False
    garage_spaces: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "category")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class PropertyListingResponse(BaseModel):
    listing_id: int
    external_listing_id: str | None = None

    title: str | None = None
    category: str | None = None

    price_total: float | None = None
    initial_dp: float | None = None
    monthly_rate: float | None = None

    num_bedrooms: int | None = None
    num_bathrooms: int | None = None

    layout_type: str | None = None
    village_name: str | None = None

    lat: float | None = None
    lng: float | None = None

    photos: list[str] | None = None

    amenity_list: dict | list | None = None
    nearby_places: dict | list | None = None

    details: str | None = None
    nearby_establishments: dict | list | None = None

    has_balcony: bool | None = None
    has_kitchen: bool | None = None
    has_backyard: bool | None = None
    has_garage: bool | None = None

    garage_spaces: int | None = None
    status: PropertyStatus = "AVAILABLE"

    sync_status: str
    last_synced_at: datetime | None = None
    created_at: datetime | None = None
    status_changed_at: datetime | None = None
    partner_id: int | None = None  # developer / partner (ALTY only)

    model_config = ConfigDict(from_attributes=True)


class PropertyListingUpdate(BaseModel):
    """Partial management edit. RESERVED/SOLD are rejected by the endpoint:
    those statuses come from reservation and sale documents."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    price_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    initial_dp: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    monthly_rate: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    num_bedrooms: int | None = Field(default=None, ge=0)
    num_bathrooms: int | None = Field(default=None, ge=0)
    layout_type: str | None = Field(default=None, max_length=255)
    village_name: str | None = Field(default=None, max_length=255)
    lat: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=10, decimal_places=6)
    lng: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=10, decimal_places=6)
    photos: list[str] | None = None
    amenity_list: dict | list | None = None
    nearby_places: dict | list | None = None
    details: str | None = None
    nearby_establishments: dict | list | None = None
    has_balcony: bool | None = None
    has_kitchen: bool | None = None
    has_backyard: bool | None = None
    has_garage: bool | None = None
    garage_spaces: int | None = Field(default=None, ge=0)
    status: str | None = None
    partner_id: int | None = None

    model_config = ConfigDict(extra="forbid")


class PropertyListingStatusSummary(BaseModel):
    available: int
    reserved: int
    sold: int
    on_hold: int
    unavailable: int
    total: int