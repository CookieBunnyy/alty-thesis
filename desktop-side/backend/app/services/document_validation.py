"""Per-type required fields and value checks for extracted document data."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.services.document_classification import FINANCIAL_TYPES, TRANSACTION_TYPES

PROPERTY_STATUSES = {"AVAILABLE", "RESERVED", "SOLD", "ON_HOLD", "UNAVAILABLE"}

# Each requirement is a tuple of alternatives: at least one must be present.
_PARTY = ("client_id", "full_name")
_PROPERTY_REF = ("listing_id", "property_title")
_AGENT_REF = ("agent_id", "agent_name")
_TRANSACTION = [_PARTY, _PROPERTY_REF, _AGENT_REF, ("transaction_date",), ("amount",)]

REQUIREMENTS: dict[str, list[tuple[str, ...]]] = {
    "PROPERTY_INFORMATION": [("listing_id",), ("property_title",), ("category",)],
    "BUYER_DOCUMENT": [("full_name",), ("client_id", "email", "contact_number")],
    "RESERVATION_AGREEMENT": _TRANSACTION,
    "SALE_AGREEMENT": _TRANSACTION,
    "DEED": _TRANSACTION,
    "TRANSACTION_DOCUMENT": [("transaction_type",), *_TRANSACTION],
    "AGENT_INFORMATION": [("agent_id",), ("full_name", "agent_name")],
    "SELLER_DOCUMENT": [("seller_name", "full_name"), _PROPERTY_REF],
    "CONTRACT": [],
    "OTHER": [],
    **{name: [("amount",)] for name in FINANCIAL_TYPES},
}

_NON_NEGATIVE = (
    "price_total", "initial_dp", "monthly_rate", "amount", "total_sales",
    "total_commission", "performance_score", "num_bedrooms", "num_bathrooms",
    "garage_spaces", "assignments_count", "transactions_count", "completed_sales",
)


@dataclass
class ValidationResult:
    errors: list[dict] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def fields(self) -> list[str]:
        return [error["field"] for error in self.errors]

    def add(self, name: str, message: str) -> None:
        self.errors.append({"field": name, "message": message})

    def as_dict(self) -> dict:
        return {"valid": self.valid, "errors": self.errors, "missing_or_invalid_fields": self.fields}

    def summary(self) -> str:
        return "; ".join(f"{error['field']}: {error['message']}" for error in self.errors)


def validate(document_type: str, values: dict, invalid: dict[str, str]) -> ValidationResult:
    result = ValidationResult()
    for name, raw in invalid.items():
        result.add(name, f"value '{raw}' could not be parsed")

    requirements = list(REQUIREMENTS.get(document_type, []))
    if document_type == "BUYER_DOCUMENT" and values.get("transaction_type"):
        # A buyer document that states a transaction must describe it fully.
        requirements += [_PROPERTY_REF, _AGENT_REF, ("transaction_date",), ("amount",)]
    if document_type == "CONTRACT" and values.get("transaction_type"):
        requirements += _TRANSACTION
    for alternatives in requirements:
        if not any(values.get(name) not in (None, "", []) for name in alternatives):
            label = " or ".join(alternatives)
            if not any(name in invalid for name in alternatives):
                result.add(label, "required field is missing")

    for name in _NON_NEGATIVE:
        value = values.get(name)
        if value is not None and value < 0:
            result.add(name, "must not be negative")
    latitude, longitude = values.get("latitude"), values.get("longitude")
    if latitude is not None and not Decimal(-90) <= latitude <= Decimal(90):
        result.add("latitude", "must be between -90 and 90")
    if longitude is not None and not Decimal(-180) <= longitude <= Decimal(180):
        result.add("longitude", "must be between -180 and 180")
    rating = values.get("star_rating")
    if rating is not None and not Decimal(0) <= rating <= Decimal(5):
        result.add("star_rating", "must be between 0 and 5")
    if document_type == "PROPERTY_INFORMATION":
        status = values.get("status")
        if status and status not in PROPERTY_STATUSES:
            result.add("status", f"'{status}' is not a property status")
    if document_type in TRANSACTION_TYPES | {"BUYER_DOCUMENT", "CONTRACT"}:
        stated = values.get("transaction_type")
        implied = {"RESERVATION_AGREEMENT": "RESERVED", "SALE_AGREEMENT": "SOLD", "DEED": "SOLD"}
        expected = implied.get(document_type)
        if stated and expected and stated != expected:
            result.add(
                "transaction_type",
                f"document states {stated} but a {document_type} records {expected}",
            )
    return result
