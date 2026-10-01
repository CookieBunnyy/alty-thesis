"""Document type registry and rule-based classification.

The registry is the single source of truth for which document types exist
and how the backend processes each one; the desktop UI loads it from
``GET /api/v1/documents/types`` so it can never offer an unprocessable type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AUTO = "AUTO"

# type -> (label, what processing does)
DOCUMENT_TYPES: dict[str, tuple[str, str]] = {
    "PROPERTY_INFORMATION": ("Property Information", "Creates or updates a property listing"),
    "BUYER_DOCUMENT": ("Buyer Document", "Creates or updates a client; records a reservation/sale when the document contains one"),
    "RESERVATION_AGREEMENT": ("Reservation Agreement", "Records a reservation and marks the property RESERVED"),
    "SALE_AGREEMENT": ("Sale Agreement", "Records a sale and marks the property SOLD"),
    "DEED": ("Deed of Sale", "Records a sale and marks the property SOLD"),
    "AGENT_INFORMATION": ("Agent Information", "Creates or updates an agent"),
    "TRANSACTION_DOCUMENT": ("Transaction Document", "Records the reservation or sale stated in the document"),
    "CONTRACT": ("Contract", "Records the stated reservation/sale, otherwise links the parties and property"),
    "SELLER_DOCUMENT": ("Seller Document", "Links the seller details to an existing property"),
    "RECEIPT": ("Receipt", "Validates the payment and links it to its transaction"),
    "VOUCHER": ("Voucher", "Validates the payment and links it to its transaction"),
    "PROOF_OF_PAYMENT": ("Proof of Payment", "Validates the payment and links it to its transaction"),
    "INVOICE": ("Invoice", "Validates the billed amount and links it to its transaction"),
    "OTHER": ("Other", "Stored in the repository without business-record processing"),
}

TRANSACTION_TYPES = {"RESERVATION_AGREEMENT", "SALE_AGREEMENT", "DEED", "TRANSACTION_DOCUMENT"}
FINANCIAL_TYPES = {"RECEIPT", "VOUCHER", "PROOF_OF_PAYMENT", "INVOICE"}

# Legacy labels stored by earlier builds / older desktop versions.
LEGACY_TYPE_ALIASES = {
    "PROPERTY DOCUMENT": "PROPERTY_INFORMATION",
    "BUYER DOCUMENT": "BUYER_DOCUMENT",
    "SELLER DOCUMENT": "SELLER_DOCUMENT",
    "TRANSACTION DOCUMENT": "TRANSACTION_DOCUMENT",
    "PROOF OF PAYMENT": "PROOF_OF_PAYMENT",
    "RECEIPT": "RECEIPT",
    "VOUCHER": "VOUCHER",
    "CONTRACT": "CONTRACT",
    "DEED": "DEED",
    "INVOICE": "INVOICE",
    "OTHER": "OTHER",
}


def canonical_type(value: str | None) -> str | None:
    """Map a UI/legacy label or code to a registry key (None if unknown)."""
    if not value:
        return None
    text = value.strip()
    code = re.sub(r"[\s-]+", "_", text.upper())
    if code in DOCUMENT_TYPES or code == AUTO:
        return code
    return LEGACY_TYPE_ALIASES.get(text.upper())


def type_catalog() -> list[dict]:
    return [
        {"code": code, "label": label, "processing": processing}
        for code, (label, processing) in DOCUMENT_TYPES.items()
    ]


# Title phrases, checked against the document's opening lines. Order matters:
# more specific phrases first ("deed of sale" before "sale", etc.).
_TITLE_RULES: list[tuple[str, str]] = [
    (r"\bdeed of (absolute )?sale\b", "DEED"),
    (r"\breservation (agreement|form|contract|slip)\b", "RESERVATION_AGREEMENT"),
    (r"\b(sale|sales|purchase) agreement\b|\bcontract to sell\b|\bagreement of sale\b", "SALE_AGREEMENT"),
    (r"\bbuyer'?s? (information|details|document|profile|record)\b|\bclient information (sheet|record|form)\b", "BUYER_DOCUMENT"),
    (r"\bseller'?s? (information|details|document)\b|\bowner'?s? information\b", "SELLER_DOCUMENT"),
    (r"\bagent (information|profile|details|record)\b", "AGENT_INFORMATION"),
    (r"\bproperty (information|details|profile|listing)\b|\blisting information\b", "PROPERTY_INFORMATION"),
    (r"\bproof of payment\b|\bpayment confirmation\b|\bdeposit slip\b", "PROOF_OF_PAYMENT"),
    (r"\b(official|acknowledg(e)?ment|cash|payment) receipt\b|^receipt\b", "RECEIPT"),
    (r"\b(cash|check|cheque|disbursement|payment)? ?voucher\b", "VOUCHER"),
    (r"\binvoice\b|\bbilling statement\b|\bstatement of account\b", "INVOICE"),
    (r"\btransaction (record|document|summary|form)\b", "TRANSACTION_DOCUMENT"),
    (r"\bcontract\b|\bagreement\b", "CONTRACT"),
]
TITLE_LINES = 6

_PROPERTY_ONLY = {
    "category", "price_total", "initial_dp", "monthly_rate", "num_bedrooms",
    "num_bathrooms", "layout_type", "village_name", "latitude", "longitude",
    "amenities", "garage_spaces",
}
_AGENT_METRICS = {
    "star_rating", "performance_score", "total_sales", "total_commission",
    "completed_sales", "assignments_count", "transactions_count", "agent_location",
}
_CLIENT_IDENTITY = {"client_id", "full_name"}
_CLIENT_CONTACT = {"email", "contact_number", "address"}


@dataclass
class Classification:
    document_type: str | None
    confidence: str  # HIGH (title) / MEDIUM (field evidence) / NONE
    reason: str


def classify(text: str, fields: dict) -> Classification:
    opening = [line.strip() for line in text.splitlines() if line.strip()][:TITLE_LINES]
    for line in opening:
        lowered = line.casefold()
        for pattern, document_type in _TITLE_RULES:
            if re.search(pattern, lowered):
                return Classification(document_type, "HIGH", f"title line: '{line[:80]}'")

    names = set(fields)
    has_client = bool(names & _CLIENT_IDENTITY) and bool(names & (_CLIENT_CONTACT | {"client_id"}))
    has_agent = bool(names & {"agent_id", "agent_name"})
    transaction_type = fields.get("transaction_type")
    if has_client and has_agent and transaction_type in {"RESERVED", "SOLD"} and "amount" in names:
        document_type = "RESERVATION_AGREEMENT" if transaction_type == "RESERVED" else "SALE_AGREEMENT"
        return Classification(document_type, "MEDIUM", "client, agent, amount and transaction type fields")
    if has_client:
        return Classification("BUYER_DOCUMENT", "MEDIUM", "client identity and contact fields")
    if "agent_id" in names and names & _AGENT_METRICS:
        return Classification("AGENT_INFORMATION", "MEDIUM", "agent id with agent profile fields")
    if len(names & _PROPERTY_ONLY) >= 3 and names & {"listing_id", "property_title"}:
        return Classification("PROPERTY_INFORMATION", "MEDIUM", "property listing fields")
    if "reference_number" in names and "amount" in names:
        return Classification("RECEIPT", "MEDIUM", "payment reference and amount fields")
    return Classification(None, "NONE", "no recognizable title or field combination")
