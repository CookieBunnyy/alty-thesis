"""Lot area, reservation payment schedules, reservation -> sale, Business Outlook."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models.client import Client
from app.models.payment import TransactionPayment
from app.models.property_listing import PropertyListing
from app.models.transaction import PropertyTransaction
from app.services.payment_plan import add_months, build_plan
from tests.test_cancellations import _reserve


def _terms(db, listing_id: int, price=3_000_000, down=300_000, monthly=15_000) -> None:
    listing = db.get(PropertyListing, listing_id)
    listing.price_total, listing.initial_dp, listing.monthly_rate = Decimal(price), Decimal(down), Decimal(monthly)
    db.commit()


# ---- lot area -----------------------------------------------------------------

def test_lot_area_is_saved_validated_and_public(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    path = f"/api/v1/property-listings/{reservation.property_id}"
    assert api.put(path, headers=admin, json={"lot_area_sqm": 0}).status_code == 422
    saved = api.put(path, headers=admin, json={"lot_area_sqm": 640000})
    assert saved.status_code == 200 and saved.json()["lot_area_sqm"] == 640000
    db.expire_all()
    db.get(PropertyListing, reservation.property_id).status = "AVAILABLE"
    db.commit()
    public = api.get("/api/v1/public/properties").json()
    assert any(p.get("lot_area_sqm") == 640000 for p in public)


# ---- payment schedule -----------------------------------------------------------

def test_schedule_from_listing_terms(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    _terms(db, reservation.property_id)
    db.expire_all()
    reservation = db.get(PropertyTransaction, reservation.transaction_id)
    fee = Decimal(reservation.amount)
    reserved_on = reservation.transaction_date.astimezone(timezone(timedelta(hours=8))).date()

    plan = build_plan(reservation, [], today=reserved_on)
    assert plan["available"] and plan["down_payment_status"] == "NOT_PAID"
    dp = plan["items"][1]
    assert dp["kind"] == "DOWN_PAYMENT" and dp["amount"] == Decimal(300_000) - fee
    assert dp["due"] == add_months(reserved_on, 1)
    monthly = [item for item in plan["items"] if item["kind"] == "MONTHLY"]
    assert len(monthly) == 180 and monthly[0]["amount"] == Decimal(15_000)      # 2,700,000 / 15,000
    assert sum(item["amount"] for item in monthly) == Decimal(2_700_000)
    assert plan["fully_paid_by"] == add_months(reserved_on, 1 + 180)
    assert plan["remaining"] == Decimal(3_000_000) - fee

    # Paying the down payment and one and a half months.
    paid = [TransactionPayment(amount=Decimal(300_000) - fee, paid_at=reserved_on),
            TransactionPayment(amount=Decimal(22_500), paid_at=reserved_on)]
    # On its due day the half-paid month is "partial"; a day later it is overdue.
    plan = build_plan(reservation, paid, today=add_months(reserved_on, 3))
    assert plan["items"][3]["status"] == "PARTIAL"
    plan = build_plan(reservation, paid, today=add_months(reserved_on, 3) + timedelta(days=1))
    assert plan["down_payment_status"] == "PAID"
    assert [m["status"] for m in plan["items"][2:5]] == ["PAID", "OVERDUE", "UPCOMING"]
    assert plan["items"][3]["paid"] == Decimal(7_500)
    assert plan["next_due"]["amount"] == Decimal(7_500)


def test_record_and_remove_payments(api, admin, employee, agents, db):
    reservation = _reserve(api, admin, db)
    _terms(db, reservation.property_id)
    base = f"/api/v1/transactions/{reservation.transaction_id}"
    payment = {"amount": "50000", "paid_at": date.today().isoformat(), "note": "Partial down payment"}
    assert api.post(f"{base}/payments", headers=employee, json=payment).status_code == 403
    future = {**payment, "paid_at": (date.today() + timedelta(days=5)).isoformat()}
    assert api.post(f"{base}/payments", headers=admin, json=future).status_code == 422
    added = api.post(f"{base}/payments", headers=admin, json=payment)
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["plan"]["down_payment_status"] == "PARTIAL" and len(body["payments"]) == 1
    assert api.get(f"{base}/payment-plan", headers=employee).status_code == 200
    removed = api.delete(f"{base}/payments/{body['payments'][0]['id']}", headers=admin)
    assert removed.status_code == 200 and removed.json()["payments"] == []
    actions = [e["action"] for e in api.get("/api/v1/audit", headers=admin).json()["items"]]
    assert "PAYMENT_RECORDED" in actions and "PAYMENT_DELETED" in actions


# ---- reservation -> sale -----------------------------------------------------------

def test_reservation_proceeds_to_sale(api, admin, employee, agents, db):
    reservation = _reserve(api, admin, db)
    _terms(db, reservation.property_id, price=4_500_000)
    path = f"/api/v1/transactions/{reservation.transaction_id}/complete-sale"
    assert api.post(path, headers=employee, json={}).status_code == 403
    done = api.post(path, headers=admin, json={"note": "Bank loan approved"})
    assert done.status_code == 200, done.text
    sale = done.json()
    assert sale["transaction_type"] == "SOLD" and sale["status"] == "COMPLETED"
    assert float(sale["amount"]) == 4_500_000 and sale["source"] == "MANAGEMENT"

    db.expire_all()
    assert db.get(PropertyTransaction, reservation.transaction_id).status == "COMPLETED"
    assert db.get(PropertyListing, reservation.property_id).status == "SOLD"
    assert db.get(Client, reservation.client_id).status == "SOLD"
    assert api.post(path, headers=admin, json={}).status_code == 409  # no longer an open reservation
    actions = [e["action"] for e in api.get("/api/v1/audit", headers=admin).json()["items"]]
    assert "RESERVATION_COMPLETED_AS_SALE" in actions


def test_cancelled_reservation_cannot_be_sold(api, admin, agents, db):
    reservation = _reserve(api, admin, db)
    base = f"/api/v1/transactions/{reservation.transaction_id}"
    api.post(f"{base}/cancel", headers=admin, json={"reason": "Buyer withdrew"})
    assert api.post(f"{base}/complete-sale", headers=admin, json={"amount": "1000000"}).status_code == 409
    assert api.post(f"{base}/payments", headers=admin,
                    json={"amount": "1000", "paid_at": date.today().isoformat()}).status_code == 409


# ---- Business Outlook -----------------------------------------------------------------

def _monthly_sales(db, agents, values: list[int]) -> list[str]:
    """One completed sale per month with the given amounts, ending last month."""
    today = datetime.now(timezone.utc)
    months = []
    year, month = today.year, today.month
    for _ in values:
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        months.append((year, month))
    months.reverse()
    keys = []
    for index, ((year, month), amount) in enumerate(zip(months, values)):
        listing = PropertyListing(title=f"Outlook {index}", price_total=Decimal(amount), status="SOLD", sync_status="SYNCED")
        db.add(listing)
        db.flush()
        client = Client(full_name=f"Buyer {index}", status="SOLD", source="SYNC", sync_status="SYNCED")
        db.add(client)
        db.flush()
        db.add(PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agents[0],
                                   transaction_type="SOLD", status="COMPLETED", amount=Decimal(amount),
                                   transaction_date=datetime(year, month, 15, 4, tzinfo=timezone.utc),
                                   source="SYNC", sync_status="SYNCED"))
        keys.append(f"{year:04d}-{month:02d}")
    db.commit()
    return keys


def test_outlook_looks_back_and_explains_a_month(api, admin, agents, db):
    values = [1_000_000, 1_200_000, 900_000, 1_400_000, 1_300_000, 1_600_000, 1_500_000, 9_000_000, 1_700_000]
    keys = _monthly_sales(db, agents, values)
    body = api.get("/api/v1/intelligence/forecast?metric=revenue&horizon=3", headers=admin).json()["forecast"]
    assert body["status"] == "estimated" and len(body["forecast"]) == 3
    back = {point["month"]: point for point in body["backtest"]}
    # The first 6 months train the first look-back; months 7-9 are checked.
    assert set(back) == set(keys[6:])
    assert back[keys[7]]["verdict"] == "ABOVE"            # the 9M spike is outside its range
    assert back[keys[6]]["actual"] == 1_500_000
    model = back[keys[6]]["model"]
    assert model["months_used"] == 6 and model["x"] == 6
    assert abs(back[keys[6]]["value"] - max(0, model["intercept"] + model["slope"] * 6)) < 1
    assert body["accuracy"]["months"] == 3 and body["accuracy"]["above"] >= 1
    assert body["forecast"][0]["model"]["x"] == len(values)

    month = api.get(f"/api/v1/intelligence/outlook/month?month={keys[7]}&metric=revenue", headers=admin)
    assert month.status_code == 200
    detail = month.json()
    assert detail["count"] == 1 and detail["total"] == 9_000_000 and detail["items"][0]["client"] == "Buyer 7"
    assert api.get("/api/v1/intelligence/outlook/month?month=2026-13", headers=admin).status_code == 422


def test_seasonal_months_are_considered():
    """Two years where every December sells about double: the next December
    is forecast above the plain trend line, and the working shows why."""
    from app.services.analytics import _predict, _trend

    months, values = [], []
    year, month = 2024, 1
    for _ in range(24):
        months.append(f"{year:04d}-{month:02d}")
        values.append(2_000_000.0 * (2 if month == 12 else 1) + 10_000 * len(values))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    december = _predict(months, values, 35, "2026-12", seasonal=True)["model"]
    assert december["seasonal"] and december["seasonal_seen"] == 2
    assert december["seasonal_factor"] > 1.3                       # Decembers sell more
    assert december["seasonal_weight"] == round(2 / 3, 4)          # seen twice: two-thirds weight
    assert abs(december["trend_value"] - (december["intercept"] + december["slope"] * 35)) < 1
    june = _predict(months, values, 29, "2026-06", seasonal=True)["model"]
    assert june["seasonal_factor"] < 1                             # other months a little below the line
    # Under a year of history: trend only, and the page is told why.
    short = _predict(months[:8], values[:8], 8, "2024-09", seasonal=True)["model"]
    assert short["seasonal"] is False and short["seasonal_months_needed"] == 12
    # The trend line is the least-squares line (same as numpy's fit).
    import numpy as np
    slope, intercept = np.polyfit(np.arange(24), values, 1)
    line = _trend(values)
    assert abs(line["slope"] - slope) < 1e-6 and abs(line["intercept"] - intercept) < 1e-4
