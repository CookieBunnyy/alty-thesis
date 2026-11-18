from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.document_classification import canonical_type, classify
from app.services.document_extraction import (
    extract_labeled_fields,
    normalize_fields,
    parse_amount,
    parse_date,
)


def fields(text: str) -> dict:
    return normalize_fields(extract_labeled_fields(text).values).values


def test_aliases_normalize_to_database_fields():
    values = fields("Buyer Name: Ana Reyes\nProperty Code: PROP-9\nNumber of Bedrooms: 3\n"
                    "Mobile Number: 0917 123 4567\nMarital Status: Single")
    assert values == {"full_name": "Ana Reyes", "listing_id": "PROP-9", "num_bedrooms": 3,
                      "contact_number": "0917 123 4567", "civil_status": "Single"}


def test_specific_label_beats_generic_regardless_of_order():
    values = fields("Date: 2026-01-01\nAmount: 5\nReservation Date: 2026-09-30\nReservation Amount: 50,000")
    assert values["transaction_date"].date().isoformat() == "2026-09-30"
    assert values["amount"] == Decimal("50000")


def test_conflicting_values_are_reported_not_overwritten():
    labeled = extract_labeled_fields("Listing ID: PROP-1\nListing ID: PROP-2")
    assert labeled.values["listing_id"] == "PROP-1"
    assert labeled.conflicts == {"listing_id": ["PROP-1", "PROP-2"]}


def test_expected_annotations_and_unknown_labels_are_ignored():
    labeled = extract_labeled_fields("Expected result: create client\nFavourite Colour: blue")
    assert labeled.values == {} and labeled.unknown_labels == ["Favourite Colour"]


def test_a_list_of_field_names_is_not_a_label_and_value():
    """A form's note to developers ("buyer_name, company_name, email, ...")
    must not read as a second buyer name and fail the document."""
    labeled = extract_labeled_fields(
        "Buyer Full Name\tMaria Angela Santos\nEmail Address\tmaria.santos@example.com\n"
        "10. Suggested NLP Extraction Targets\n"
        "buyer_name, company_name, buyer_type, email, mobile_phone, grand_total, payment_method")
    assert labeled.conflicts == {}
    assert labeled.values["full_name"] == "Maria Angela Santos"
    # A real row whose border was lost still splits.
    assert fields("Buyer Name Maria Clara Reyes")["full_name"] == "Maria Clara Reyes"


def test_value_on_following_line():
    assert fields("Full Name:\nMaria Clara")["full_name"] == "Maria Clara"


@pytest.mark.parametrize("raw,expected", [
    ("PHP 8,500,000.00", Decimal("8500000.00")), ("₱ 50,000", Decimal("50000")),
    ("P1.5M", Decimal("1500000")), ("75k", Decimal("75000")), ("125000", Decimal("125000")),
])
def test_amounts(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["2026-09-30", "09/30/2026", "30/09/2026", "September 30, 2026",
                                 "30 Sept. 2026", "2026/09/30"])
def test_dates(raw):
    assert parse_date(raw) == datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_invalid_values_are_reported():
    normalized = normalize_fields({"amount": "lots", "email": "not-an-email", "has_garage": "maybe"})
    assert normalized.values == {} and set(normalized.invalid) == {"amount", "email", "has_garage"}


def test_transaction_type_words():
    assert fields("Transaction Type: Reservation")["transaction_type"] == "RESERVED"
    assert fields("Transaction Type: Full Payment")["transaction_type"] == "SOLD"


@pytest.mark.parametrize("title,expected", [
    ("BUYER INFORMATION DOCUMENT", "BUYER_DOCUMENT"),
    ("Deed of Absolute Sale", "DEED"),
    ("RESERVATION AGREEMENT", "RESERVATION_AGREEMENT"),
    ("Contract to Sell", "SALE_AGREEMENT"),
    ("Official Receipt", "RECEIPT"),
    ("Agent Profile", "AGENT_INFORMATION"),
])
def test_title_classification(title, expected):
    assert classify(title + "\nSomething: else", {}).document_type == expected


def test_buyer_document_with_property_fields_is_not_misclassified_as_property():
    text = "Client ID: C1\nFull Name: A B\nListing ID: P1\nProperty Name: Home"
    assert classify(text, fields(text)).document_type == "BUYER_DOCUMENT"


def test_legacy_ui_labels_map_to_registry():
    assert canonical_type("Buyer Document") == "BUYER_DOCUMENT"
    assert canonical_type("Property Document") == "PROPERTY_INFORMATION"
    assert canonical_type("Proof of Payment") == "PROOF_OF_PAYMENT"
    assert canonical_type("Nonsense") is None
