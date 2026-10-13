"""Price and closing-cost breakdown on the transaction page."""

from decimal import Decimal

from app.models.partner import Partner
from app.models.property_listing import PropertyListing
from app.services.closing_costs import breakdown, location_of
from tests.test_cancellations import _reserve


def _listing(village, category="House and Lot"):
    return PropertyListing(title="Home", village_name=village, category=category)


def test_metro_manila_is_recognised():
    assert location_of(_listing("Loft BGC Residences, Taguig"))["metro_manila"]
    assert location_of(_listing("Ortigas Center"))["metro_manila"]
    assert not location_of(_listing("Molino IV, Bacoor, Cavite"))["metro_manila"]
    assert not location_of(_listing("San Juan, Batangas"))["metro_manila"]       # the province wins
    assert not location_of(_listing("Somewhere"))["metro_manila"]


def test_fees_follow_location_and_seller():
    price = Decimal(5_000_000)
    ncr = breakdown(_listing("Makati City"), price)
    fees = {f["key"]: f["amount"] for f in ncr["buyer_fees"]}
    assert fees == {"transfer_tax": Decimal("37500.00"), "documentary_stamp_tax": Decimal("75000.00"),
                    "registration_fee": Decimal("12500.00"), "notarial_fee": Decimal("50000.00")}
    assert ncr["total_cost"] == price + sum(fees.values())
    assert not ncr["vat"]["applies"] and ncr["seller_fees"][0]["amount"] == Decimal("300000.00")  # 6% CGT

    province = breakdown(_listing("Imus, Cavite"), price)
    assert {f["key"]: f["amount"] for f in province["buyer_fees"]}["transfer_tax"] == Decimal("25000.00")

    developer = Partner(name="Dev", partner_type="DEVELOPER")
    sold = breakdown(_listing("Imus, Cavite"), Decimal(5_600_000), developer)
    assert sold["vat"]["applies"] and sold["vat"]["amount"] == Decimal("600000.00")   # VAT inside the price
    assert sold["seller_fees"] == []
    cheap = breakdown(_listing("Imus, Cavite"), Decimal(2_500_000), developer)
    assert not cheap["vat"]["applies"]                                              # under the exemption
    lot = breakdown(_listing("Imus, Cavite", "Lot Only"), Decimal(2_500_000), developer)
    assert lot["vat"]["applies"]                                                    # lots have no exemption


def test_endpoint(api, admin, employee, agents, db):
    reservation = _reserve(api, admin, db)
    listing = db.get(PropertyListing, reservation.property_id)
    listing.price_total, listing.village_name = Decimal(4_000_000), "Eastwood City, Quezon City"
    db.commit()
    body = api.get(f"/api/v1/transactions/{reservation.transaction_id}/cost-breakdown", headers=employee).json()
    assert float(body["price"]) == 4_000_000 and body["location"]["metro_manila"]
    assert float(body["total_cost"]) == 4_140_000                   # + 0.75% + 1.5% + 0.25% + 1%
    assert api.get("/api/v1/transactions/nope/cost-breakdown", headers=admin).status_code == 404
