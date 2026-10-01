"""Deterministic text + field extraction for repository documents.

Pipeline: bytes -> text (native PDF/DOCX text, OCR fallback per page)
-> labeled fields (alias table) -> normalized values.

Nothing here invents values: a field that is absent or cannot be parsed is
simply not returned (unparseable values are reported in ``invalid``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from docx import Document as WordDocument
from pypdf import PdfReader

from app.core.config import settings
from app.services import ocr_service

logger = logging.getLogger(__name__)


class ExtractionError(ValueError):
    """Text could not be obtained from the document."""


@dataclass
class ExtractionResult:
    text: str
    method: str  # TEXT / OCR / MIXED
    source_format: str  # TEXT_PDF / SCANNED_PDF / DOCX / IMAGE
    pages: int = 1
    ocr_pages: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "method": self.method,
            "source_format": self.source_format,
            "pages": self.pages,
            "ocr_pages": self.ocr_pages,
            "text_length": len(self.text),
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _meaningful_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _pdf_text(content: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
    except Exception as exc:
        raise ExtractionError(f"The PDF could not be read: {exc}") from exc
    if page_count == 0:
        raise ExtractionError("The PDF has no pages")

    texts: list[str] = []
    ocr_pages: list[int] = []
    warnings: list[str] = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # damaged content stream on one page
            warnings.append(f"page {index + 1}: text layer unreadable ({exc})")
            text = ""
        if _meaningful_chars(text) < settings.OCR_MIN_TEXT_CHARS:
            try:
                ocr_text = ocr_service.pdf_page_to_text(content, index)
            except ocr_service.OcrUnavailableError as exc:
                raise ExtractionError(
                    f"Page {index + 1} has no extractable text and OCR is unavailable: {exc}"
                ) from exc
            except Exception as exc:
                raise ExtractionError(f"OCR failed on page {index + 1}: {exc}") from exc
            if _meaningful_chars(ocr_text) > _meaningful_chars(text):
                text = ocr_text
                ocr_pages.append(index + 1)
        texts.append(text)

    if not ocr_pages:
        method, source_format = "TEXT", "TEXT_PDF"
    elif len(ocr_pages) == page_count:
        method, source_format = "OCR", "SCANNED_PDF"
    else:
        method, source_format = "MIXED", "SCANNED_PDF"
    return ExtractionResult(
        "\n".join(texts), method, source_format, page_count, ocr_pages, warnings
    )


def _docx_text(content: bytes) -> ExtractionResult:
    try:
        document = WordDocument(BytesIO(content))
    except Exception as exc:
        raise ExtractionError(f"The DOCX could not be read: {exc}") from exc
    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = []
            for cell in row.cells:
                value = cell.text.strip()
                if not cells or cells[-1] != value:  # merged cells repeat
                    cells.append(value)
            # Two-column tables are "label | value" forms.
            lines.append(f"{cells[0]}: {cells[1]}" if len(cells) == 2 else "\t".join(cells))
    return ExtractionResult("\n".join(lines), "TEXT", "DOCX")


def _image_text(content: bytes) -> ExtractionResult:
    try:
        text = ocr_service.image_bytes_to_text(content)
    except ocr_service.OcrUnavailableError as exc:
        raise ExtractionError(f"OCR is unavailable for this image: {exc}") from exc
    except Exception as exc:
        raise ExtractionError(f"OCR failed: {exc}") from exc
    return ExtractionResult(text, "OCR", "IMAGE", 1, [1])


def extract_text(source_format: str, content: bytes) -> ExtractionResult:
    """``source_format`` comes from byte-level detection (PDF / DOCX / IMAGE)."""
    if source_format == "PDF":
        result = _pdf_text(content)
    elif source_format == "DOCX":
        result = _docx_text(content)
    elif source_format == "IMAGE":
        result = _image_text(content)
    else:
        raise ExtractionError(f"Unsupported document format: {source_format}")
    if _meaningful_chars(result.text) == 0:
        raise ExtractionError("No text could be extracted from the document")
    return result


# ---------------------------------------------------------------------------
# Labeled field extraction
# ---------------------------------------------------------------------------

# field -> {alias: priority}. Specific labels (priority 2) override generic
# ones (priority 1) such as "Date" or "Amount" regardless of order.
_G, _S = 1, 2
FIELD_ALIASES: dict[str, dict[str, int]] = {
    # property
    "listing_id": {
        "listing id": _S, "listing code": _S, "listing no": _S, "listing number": _S,
        "property id": _S, "property code": _S, "property listing id": _S,
        "property no": _S, "property number": _S, "property reference": _S,
    },
    "property_title": {
        "property title": _S, "property name": _S, "listing title": _S,
        "title": _G, "property": _G,
    },
    "category": {"category": _G, "property category": _S, "property type": _S},
    "price_total": {
        "price total": _S, "total price": _S, "selling price": _S, "contract price": _S,
        "total contract price": _S, "list price": _S, "listing price": _S, "price": _G,
    },
    "initial_dp": {
        "initial dp": _S, "down payment": _S, "downpayment": _S,
        "initial down payment": _S, "required down payment": _S, "dp": _G,
    },
    "monthly_rate": {
        "monthly rate": _S, "monthly payment": _S, "monthly installment": _S,
        "monthly amortization": _S, "monthly": _G,
    },
    "num_bedrooms": {
        "num bedrooms": _S, "bedrooms": _S, "bedroom count": _S,
        "number of bedrooms": _S, "no of bedrooms": _S, "bedroom": _G,
    },
    "num_bathrooms": {
        "num bathrooms": _S, "bathrooms": _S, "bathroom count": _S,
        "number of bathrooms": _S, "no of bathrooms": _S, "bathroom": _G,
    },
    "layout_type": {"layout type": _S, "layout": _G, "floor plan": _G},
    "village_name": {"village name": _S, "village": _S, "subdivision": _S, "project": _G},
    "latitude": {"latitude": _S, "lat": _G},
    "longitude": {"longitude": _S, "lng": _G, "lon": _G, "long": _G},
    "status": {"property status": _S, "listing status": _S, "status": _G},
    "amenities": {"amenities": _S, "amenity list": _S, "amenity": _G},
    "nearby_places": {"nearby places": _S, "nearby landmarks": _S, "landmarks": _G},
    "nearby_establishments": {"nearby establishments": _S, "establishments": _G},
    "has_balcony": {"has balcony": _S, "balcony": _G},
    "has_kitchen": {"has kitchen": _S, "kitchen": _G},
    "has_backyard": {"has backyard": _S, "backyard": _G},
    "has_garage": {"has garage": _S, "garage": _G},
    "garage_spaces": {
        "garage spaces": _S, "number of garage spaces": _S, "parking slots": _S,
        "parking spaces": _S,
    },
    "details": {"details": _G, "property details": _S, "description": _G},
    "photos": {"photos": _S, "photo urls": _S, "images": _G, "media": _G},
    # client / buyer
    "client_id": {
        "client id": _S, "buyer id": _S, "customer id": _S, "client no": _S,
        "client number": _S, "client code": _S, "buyer no": _S,
    },
    "full_name": {
        "full name": _G, "client name": _S, "client full name": _S, "buyer name": _S,
        "buyer full name": _S, "customer name": _S, "name of buyer": _S, "name": _G,
    },
    "address": {
        "address": _G, "client address": _S, "buyer address": _S, "client location": _S,
        "home address": _S, "residential address": _S,
    },
    "contact_number": {
        "contact number": _G, "contact no": _G, "phone number": _G, "phone": _G,
        "mobile": _G, "mobile number": _G, "cellphone number": _G, "telephone": _G,
        "client contact number": _S, "buyer contact number": _S,
    },
    "email": {"email": _G, "email address": _G, "client email": _S, "buyer email": _S},
    "occupation": {"occupation": _S, "profession": _S, "job title": _S},
    "civil_status": {"civil status": _S, "marital status": _S},
    "preferred_contact": {
        "preferred contact": _S, "preferred contact method": _S,
        "preferred mode of contact": _S,
    },
    "purpose_of_purchase": {"purpose of purchase": _S, "purpose": _G, "intended use": _S},
    "client_status": {"client status": _S, "buyer status": _S},
    # agent
    "agent_id": {"agent id": _S, "agent code": _S, "agent no": _S, "broker id": _S},
    "agent_name": {
        "agent name": _S, "agent full name": _S, "assigned agent": _S,
        "sales agent": _S, "handling agent": _S, "agent": _G,
    },
    "phone_number": {
        "agent phone number": _S, "agent phone": _S, "agent contact number": _S,
        "agent mobile": _S,
    },
    "agent_location": {
        "agent location": _S, "office location": _S, "branch": _G, "location": _G,
    },
    "star_rating": {"star rating": _S, "rating": _G},
    "assignments_count": {"assignments count": _S, "assignment count": _S, "assignments": _G},
    "transactions_count": {"transactions count": _S, "transaction count": _S},
    "completed_sales": {"completed sales": _S},
    "total_sales": {"total sales": _S},
    "total_commission": {"total commission": _S, "commission": _G},
    "performance_score": {"performance score": _S},
    "agent_status": {"agent status": _S},
    # transaction
    "transaction_id": {
        "transaction id": _S, "transaction no": _S, "transaction number": _S,
        "transaction reference": _S, "transaction ref": _S,
    },
    "reservation_id": {
        "reservation id": _S, "reservation no": _S, "reservation number": _S,
        "reservation reference": _S,
    },
    "reference_number": {
        "reference number": _S, "reference no": _S, "receipt no": _S, "receipt number": _S,
        "official receipt no": _S, "or no": _S, "voucher no": _S, "voucher number": _S,
        "invoice no": _S, "invoice number": _S,
    },
    "transaction_date": {
        "transaction date": _S, "reservation date": _S, "sale date": _S,
        "date of sale": _S, "date of reservation": _S, "payment date": _S,
        "contract date": _S, "date": _G,
    },
    "transaction_type": {"transaction type": _S, "type of transaction": _S},
    "amount": {
        "transaction amount": _S, "reservation amount": _S, "reservation fee": _S,
        "sale amount": _S, "sales amount": _S, "amount paid": _S, "payment amount": _S,
        "purchase price": _S, "total amount": _G, "amount": _G,
    },
    "transaction_status": {
        "transaction status": _S, "reservation status": _S, "sale status": _S,
        "payment status": _S,
    },
    "payer": {"payer": _S, "received from": _S, "paid by": _S},
    "payment_method": {"payment method": _S, "mode of payment": _S},
    # seller
    "seller_name": {
        "seller name": _S, "seller full name": _S, "owner name": _S,
        "property owner": _S, "vendor name": _S, "seller": _G,
    },
    "seller_contact": {"seller contact number": _S, "seller contact": _S, "seller phone": _S},
    "seller_address": {"seller address": _S, "owner address": _S},
}


def _label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.casefold())


_LABEL_INDEX: dict[str, tuple[str, int]] = {}
for _field, _aliases in FIELD_ALIASES.items():
    for _alias, _priority in _aliases.items():
        _LABEL_INDEX[_label_key(_alias)] = (_field, _priority)

_LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ./'()#&-]{0,62}?)\s*[:\t]\s*(.*)$")


@dataclass
class LabeledFields:
    values: dict[str, str]
    conflicts: dict[str, list[str]]
    unknown_labels: list[str]


def extract_labeled_fields(text: str) -> LabeledFields:
    values: dict[str, str] = {}
    priorities: dict[str, int] = {}
    conflicts: dict[str, list[str]] = {}
    unknown: list[str] = []
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines()]

    def label_of(line: str) -> tuple[str, str] | None:
        match = _LABEL_LINE.match(line)
        return (match.group(1), match.group(2)) if match else None

    for index, line in enumerate(lines):
        parsed = label_of(line)
        if parsed is None:
            continue
        label, value = parsed
        key = _label_key(label)
        # Test/expectation annotations ("Expected result: ...") are not data.
        if key.startswith("expected"):
            continue
        mapped = _LABEL_INDEX.get(key)
        if mapped is None:
            unknown.append(label.strip())
            continue
        name, priority = mapped
        value = value.strip()
        if not value and index + 1 < len(lines):
            following = lines[index + 1]
            if following and label_of(following) is None:
                value = following
        if not value:
            continue
        current_priority = priorities.get(name, 0)
        if priority > current_priority:
            values[name] = value
            priorities[name] = priority
        elif priority == current_priority and values.get(name) != value:
            conflicts.setdefault(name, [values[name]]).append(value)
    return LabeledFields(values, conflicts, unknown)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

DECIMAL_FIELDS = {
    "price_total", "initial_dp", "monthly_rate", "latitude", "longitude",
    "star_rating", "total_sales", "total_commission", "performance_score", "amount",
}
INTEGER_FIELDS = {
    "num_bedrooms", "num_bathrooms", "garage_spaces", "assignments_count",
    "transactions_count", "completed_sales",
}
BOOLEAN_FIELDS = {"has_balcony", "has_kitchen", "has_backyard", "has_garage"}
LIST_FIELDS = {"amenities", "nearby_places", "nearby_establishments", "photos"}
DATE_FIELDS = {"transaction_date"}
STATUS_FIELDS = {"status", "client_status", "transaction_status", "agent_status"}

_TRUE = {"yes", "y", "true", "1", "included", "with", "available", "present"}
_FALSE = {"no", "n", "false", "0", "not included", "none", "without", "n/a", "na"}

TRANSACTION_TYPE_WORDS = {
    "RESERVED": {"RESERVED", "RESERVATION", "RESERVE"},
    "SOLD": {"SOLD", "SALE", "SALES", "PURCHASE", "FULL_PAYMENT", "PURCHASED"},
}

_MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}


def parse_amount(raw: str) -> Decimal:
    value = raw.strip().upper()
    value = re.sub(r"(PHP|PESOS?|₱|^P(?=\s*\d))", "", value).strip()
    multiplier = Decimal(1)
    suffix = re.search(r"(\d)\s*(M|MILLION|K|THOUSAND)\b", value)
    if suffix:
        multiplier = Decimal(1_000_000) if suffix.group(2).startswith("M") else Decimal(1000)
        value = value[: suffix.start(2)]
    value = value.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        raise InvalidOperation(raw)
    return Decimal(match.group()) * multiplier


def parse_date(raw: str) -> datetime:
    """Parse common document date formats; returns a UTC-aware datetime."""
    candidate = raw.strip().rstrip(".")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    numeric = re.fullmatch(r"(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})", candidate)
    if numeric:
        a, b, c = (int(part) for part in numeric.groups())
        if a > 31:  # YYYY/MM/DD
            year, month, day = a, b, c
        elif a > 12:  # DD/MM/YYYY
            day, month, year = a, b, c
        else:  # MM/DD/YYYY (Philippine convention)
            month, day, year = a, b, c
        return datetime(year, month, day, tzinfo=timezone.utc)
    words = re.findall(r"[A-Za-z]+|\d+", candidate)
    month = next((_MONTHS[w.casefold()] for w in words if w.casefold() in _MONTHS), None)
    numbers = [int(w) for w in words if w.isdigit()]
    if month and len(numbers) >= 2:
        year = next((n for n in numbers if n > 31), None)
        day = next((n for n in numbers if n <= 31), None)
        if year and day:
            return datetime(year, month, day, tzinfo=timezone.utc)
    raise ValueError(f"Unrecognized date: {raw}")


def normalize_transaction_type(raw: str) -> str | None:
    token = re.sub(r"[\s-]+", "_", raw.strip().upper())
    for canonical, words in TRANSACTION_TYPE_WORDS.items():
        if token in words:
            return canonical
    return None


def normalize_phone_digits(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("63") and len(digits) == 12:  # +63 9XX -> 09XX
        digits = "0" + digits[2:]
    return digits


def normalize_name(value: str | None) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (value or "").casefold()).split())


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class NormalizedFields:
    values: dict[str, Any]
    invalid: dict[str, str]  # field -> raw value that could not be parsed


def normalize_fields(raw_fields: dict[str, str]) -> NormalizedFields:
    values: dict[str, Any] = {}
    invalid: dict[str, str] = {}
    for name, raw in raw_fields.items():
        text = raw.strip()
        if not text:
            continue
        try:
            if name in DECIMAL_FIELDS:
                value: Any = parse_amount(text)
            elif name in INTEGER_FIELDS:
                match = re.search(r"-?\d+", text.replace(",", ""))
                if not match:
                    raise ValueError(text)
                value = int(match.group())
            elif name in BOOLEAN_FIELDS:
                lowered = text.casefold()
                if lowered in _TRUE:
                    value = True
                elif lowered in _FALSE:
                    value = False
                else:
                    raise ValueError(text)
            elif name in LIST_FIELDS:
                value = [item.strip() for item in re.split(r"[;,\n|]", text) if item.strip()]
            elif name in DATE_FIELDS:
                value = parse_date(text)
            elif name == "transaction_type":
                value = normalize_transaction_type(text)
                if value is None:
                    raise ValueError(text)
            elif name in STATUS_FIELDS:
                value = re.sub(r"[\s-]+", "_", text.upper())
            elif name == "email":
                value = text.casefold()
                if not _EMAIL.match(value):
                    raise ValueError(text)
            else:
                value = " ".join(text.split())
        except (InvalidOperation, ValueError, OverflowError):
            invalid[name] = raw
            continue
        values[name] = value
    return NormalizedFields(values, invalid)


def jsonable_fields(values: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, value in values.items():
        if isinstance(value, Decimal):
            output[name] = str(value)
        elif isinstance(value, datetime):
            output[name] = value.date().isoformat()
        else:
            output[name] = value
    return output
