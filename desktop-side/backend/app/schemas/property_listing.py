from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PropertyListingResponse(BaseModel):
    listing_id: int

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

    sync_status: str
    last_synced_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)