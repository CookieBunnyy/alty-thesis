from __future__ import annotations

from io import BytesIO
import re
from pathlib import Path
from typing import Any
from decimal import Decimal, InvalidOperation

from docx import Document as WordDocument
from pypdf import PdfReader


DOCUMENT_TYPES = {
    "PROPERTY_INFORMATION",
    "RESERVATION_AGREEMENT",
    "SALE_AGREEMENT",
    "AGENT_INFORMATION",
}

FIELD_ALIASES = {
    "listing_id": {"listingid", "propertyid", "propertylistingid"},
    "property_title": {"propertytitle", "title", "propertyname"},
    "category": {"category", "propertycategory", "propertytype"},
    "price_total": {"pricetotal", "totalprice", "price"},
    "initial_dp": {"initialdp", "downpayment", "initialdownpayment"},
    "monthly_rate": {"monthlyrate", "monthlypayment", "monthlyinstallment"},
    "num_bedrooms": {"numbedrooms", "bedrooms", "bedroomcount"},
    "num_bathrooms": {"numbathrooms", "bathrooms", "bathroomcount"},
    "layout_type": {"layouttype", "layout"},
    "village_name": {"villagename", "village", "subdivision"},
    "latitude": {"latitude", "lat"},
    "longitude": {"longitude", "lng", "lon"},
    "status": {"status", "propertystatus", "agentstatus"},
    "amenities": {"amenities", "amenity", "amenitylist"},
    "nearby_places": {"nearbyplaces"},
    "nearby_establishments": {"nearbyestablishments"},
    "has_balcony": {"hasbalcony", "balcony"},
    "has_kitchen": {"haskitchen", "kitchen"},
    "has_backyard": {"hasbackyard", "backyard"},
    "has_garage": {"hasgarage", "garage"},
    "garage_spaces": {"garagespaces", "numberofgaragespaces"},
    "details": {"details", "description", "propertydetails"},
    "client_id": {"clientid", "buyerid", "customerid"},
    "full_name": {"fullname", "clientfullname", "clientname", "customername"},
    "address": {"address", "clientaddress", "clientlocation"},
    "contact_number": {"contactnumber", "phonenumber", "phone", "mobile"},
    "email": {"email", "emailaddress"},
    "agent_id": {"agentid"},
    "agent_name": {"agentname", "agentfullname"},
    "transaction_id": {"transactionid", "reservationid", "reservationnumber"},
    "transaction_date": {"transactiondate", "reservationdate", "saledate"},
    "transaction_type": {"transactiontype"},
    "amount": {"amount", "reservationamount", "saleamount", "transactionamount"},
    "transaction_status": {"transactionstatus", "reservationstatus", "salestatus"},
    "phone_number": {"agentphonenumber", "agentphone"},
    "agent_location": {"agentlocation", "location"},
    "star_rating": {"starrating", "rating"},
    "assignments_count": {"assignmentscount", "assignmentcount"},
    "transactions_count": {"transactionscount", "transactioncount"},
    "completed_sales": {"completedsales"},
    "total_sales": {"totalsales"},
    "total_commission": {"totalcommission"},
    "performance_score": {"performancescore"},
}

_LABEL_TO_FIELD = {
    re.sub(r"[^a-z0-9]", "", alias.casefold()): field
    for field, aliases in FIELD_ALIASES.items()
    for alias in aliases
}
def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    if extension == ".docx":
        document = WordDocument(BytesIO(content))
        lines = [paragraph.text for paragraph in document.paragraphs]
        lines.extend("\t".join(cell.text for cell in row.cells) for table in document.tables for row in table.rows)
        return "\n".join(lines)
    raise ValueError(f"Unsupported document format: {extension or 'no extension'}")


def _normalized_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.casefold())


def extract_labeled_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines()]
    for index, line in enumerate(lines):
        match = re.match(r"^([^:\t]{2,64})\s*[:\t]\s*(.*)$", line)
        label, value = (match.group(1), match.group(2)) if match else (line, "")
        field = _LABEL_TO_FIELD.get(_normalized_label(label))
        if field is None:
            continue
        if not value and index + 1 < len(lines):
            value = lines[index + 1]
        value = value.strip()
        if value:
            fields[field] = value
    return fields


def classify_document(text: str, filename: str = "") -> str | None:
    fields = set(extract_labeled_fields(text))
    labeled_fields = extract_labeled_fields(text)
    content = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    declared_type = str(labeled_fields.get("transaction_type") or "").upper()
    has_party = bool(fields & {"full_name", "client_id"}) and "agent_id" in fields

    if has_party and (
        declared_type in {"SOLD", "SALE"}
        or re.search(r"\bsale agreement\b|\bdeed of sale\b|\bsale amount\b", content)
    ):
        return "SALE_AGREEMENT"
    if has_party and (
        declared_type in {"RESERVED", "RESERVATION"}
        or
        "reservation amount" in content
        or re.search(r"\breservation agreement\b|\breservation id\b", content)
    ):
        return "RESERVATION_AGREEMENT"
    property_fields = fields & {
        "listing_id", "property_title", "category", "price_total", "num_bedrooms", "num_bathrooms"
    }
    if len(property_fields) >= 2:
        return "PROPERTY_INFORMATION"
    if "agent_id" in fields and (
        "contact_number" in fields
        or "phone_number" in fields
        or "star_rating" in fields
        or "performance_score" in fields
    ):
        return "AGENT_INFORMATION"

    # Filenames are a supplementary hint only after content contains domain fields.
    filename_hint = Path(filename).stem.casefold().replace("_", " ").replace("-", " ")
    if fields and "sale" in filename_hint and has_party:
        return "SALE_AGREEMENT"
    if fields and "reservation" in filename_hint and has_party:
        return "RESERVATION_AGREEMENT"
    if fields & {"agent_id", "full_name"} == {"agent_id", "full_name"} and "agent" in filename_hint:
        return "AGENT_INFORMATION"
    return None


def normalize_fields(fields: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    numeric_fields = {
        "price_total", "initial_dp", "monthly_rate", "latitude", "longitude",
        "star_rating", "total_sales", "total_commission", "performance_score", "amount",
    }
    integer_fields = {
        "num_bedrooms", "num_bathrooms", "garage_spaces", "assignments_count",
        "transactions_count", "completed_sales",
    }
    boolean_fields = {"has_balcony", "has_kitchen", "has_backyard", "has_garage"}
    for name, raw_value in fields.items():
        value: Any = raw_value.strip()
        if name in numeric_fields:
            value = re.sub(r"[^0-9.+-]", "", value.replace(",", ""))
            try:
                value = Decimal(value)
            except InvalidOperation:
                continue
        elif name in integer_fields:
            match = re.search(r"-?\d+", value.replace(",", ""))
            if not match:
                continue
            value = int(match.group())
        elif name in boolean_fields:
            lowered = value.casefold()
            if lowered in {"yes", "true", "1", "included"}:
                value = True
            elif lowered in {"no", "false", "0", "not included"}:
                value = False
            else:
                continue
        elif name in {"amenities", "nearby_places", "nearby_establishments"}:
            value = [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
        if value != "":
            normalized[name] = value
    return normalized


def classify_and_extract(filename: str, content: bytes) -> tuple[str, dict[str, Any]]:
    text = extract_text(filename, content)
    document_type = classify_document(text, filename)
    return document_type or "", normalize_fields(extract_labeled_fields(text))