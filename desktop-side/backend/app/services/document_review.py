"""Configurable extraction for documents that a person verifies (commission
vouchers): every printed "label: value" pair is kept, schema fields are
filled from them, and nothing is written to business records until a person
verifies the values and the links."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.extraction import DocumentExtraction, DocumentSchema

REVIEWED_TYPES = {"COMMISSION_VOUCHER"}
# The voucher details Abellar Realty listed (second interview); set up by
# migration 0026, and editable in Document Repository > voucher fields.
DEFAULT_VOUCHER_FIELDS = [
    {"key": "agent_name", "label": "Agent name", "aliases": ["Agent", "Name of agent", "Seller", "Payee", "Pay to"],
     "type": "text", "required": True},
    {"key": "voucher_date", "label": "Date", "aliases": ["Voucher date", "Date prepared", "Date issued"],
     "type": "date", "required": True},
    {"key": "tcp", "label": "TCP", "aliases": ["Total contract price", "Contract price", "Selling price"],
     "type": "money", "required": True},
    {"key": "particulars", "label": "Particulars", "aliases": ["Description", "Details", "Remarks"],
     "type": "text", "required": True},
    {"key": "amount", "label": "Amount", "aliases": ["Amount paid", "Total amount", "Gross amount"],
     "type": "money", "required": True},
    {"key": "payment_method", "label": "Mode of payment",
     "aliases": ["Paid through", "Payment method", "Paid via", "Payment mode", "Mode"], "type": "text",
     "required": True},
    {"key": "commission_amount", "label": "Commission amount",
     "aliases": ["Commission", "Net commission", "Commission due"], "type": "money", "required": True},
    {"key": "bank_name", "label": "Bank name", "aliases": ["Bank", "Bank / branch"], "type": "text",
     "required": True},
]
_PAIR = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ./'()#&%-]{0,62}?)\s*[:\t]\s*(.*?)\s*$")
_SPACED = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ./'()#&%-]{1,40}?)\s{3,}(\S.*?)\s*$")


def _key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()


def label_value_pairs(text: str) -> list[dict]:
    """Every "Label: value" (or "Label    value") line, with a value on the
    next line when the label stands alone. Nothing is renamed or dropped."""
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines()]
    pairs, used = [], set()
    for index, line in enumerate(lines):
        if index in used or not line:
            continue
        match = _PAIR.match(line) or _SPACED.match(line)
        if not match:
            continue
        label, value = match.group(1).strip(), match.group(2).strip()
        if not value and index + 1 < len(lines) and lines[index + 1] and not _PAIR.match(lines[index + 1]):
            value = lines[index + 1]
            used.add(index + 1)
        pairs.append({"label": label, "value": value, "line": index + 1})
    return pairs


def schema_for(db: Session, document_type: str) -> list[dict]:
    row = db.execute(select(DocumentSchema).where(DocumentSchema.document_type == document_type)).scalar_one_or_none()
    return list(row.fields or []) if row else []


def map_fields(pairs: list[dict], schema: list[dict]) -> dict[str, Any]:
    """Schema key -> the first value whose printed label matches the field's
    label or one of its aliases (case and punctuation ignored)."""
    found: dict[str, Any] = {}
    by_label: dict[str, str] = {}
    for pair in pairs:
        by_label.setdefault(_key(pair["label"]), pair["value"])
    for field in schema:
        for label in [field.get("label", ""), *field.get("aliases", [])]:
            value = by_label.get(_key(label))
            if value not in (None, ""):
                found[field["key"]] = value
                break
    return found


def extract(db: Session, document_row_id: int, document_type: str, text: str) -> DocumentExtraction:
    pairs = label_value_pairs(text)
    mapped = map_fields(pairs, schema_for(db, document_type))
    row = db.execute(select(DocumentExtraction).where(DocumentExtraction.document_row_id == document_row_id)
                     ).scalar_one_or_none()
    if row is None:
        row = DocumentExtraction(document_row_id=document_row_id, document_type=document_type)
        db.add(row)
    row.document_type, row.detected_pairs, row.mapped_fields = document_type, pairs, mapped
    row.verification_status, row.verified_by, row.verified_at = "NEEDS_REVIEW", None, None
    db.flush()
    return row


def missing_required(schema: list[dict], values: dict) -> list[str]:
    return [f.get("label") or f["key"] for f in schema if f.get("required") and values.get(f["key"]) in (None, "")]
