"""Payment schedule for a reservation, from the listing's terms.

Terms (stated on the page as well, so staff can check them):
  * the reservation fee is the reservation's own amount, paid on the day,
    and it is credited toward the down payment;
  * the rest of the down payment (listing ``initial_dp``) is due one month
    after the reservation;
  * the balance (price minus the down payment) is paid in monthly payments of
    the listing's ``monthly_rate``, starting one month after the down
    payment; the last payment is the remainder. Without a monthly rate, the
    balance is one payment due a month after the down payment.

Recorded payments (``transaction_payments``) are applied in order: down
payment first, then each monthly payment.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta, timezone
from decimal import ROUND_CEILING, Decimal

from app.models.payment import TransactionPayment
from app.models.transaction import PropertyTransaction

PH = timezone(timedelta(hours=8))
CENT = Decimal("0.01")


def add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _ph_date(moment) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(PH).date()


def _status(amount: Decimal, paid: Decimal, due: date, today: date) -> str:
    if paid >= amount:
        return "PAID"
    if due < today:
        return "OVERDUE"
    if paid > 0:
        return "PARTIAL"
    if (due.year, due.month) == (today.year, today.month):
        return "DUE"
    return "UPCOMING"


def build_plan(reservation: PropertyTransaction, payments: list[TransactionPayment],
               today: date | None = None) -> dict:
    today = today or date.today()
    listing = reservation.property_listing
    if reservation.transaction_type != "RESERVED":
        return {"available": False, "reason": "Payment schedules belong to reservations."}
    if reservation.status == "CANCELLED":
        return {"available": False, "reason": "This reservation was cancelled, so no payments are due."}
    price = Decimal(listing.price_total or 0)
    if price <= 0:
        return {"available": False, "reason": "The property has no price on record, so no schedule can be worked out."}

    fee = Decimal(reservation.amount or 0)
    down_payment = Decimal(listing.initial_dp or 0)
    monthly = Decimal(listing.monthly_rate or 0)
    reserved_on = _ph_date(reservation.transaction_date)
    dp_due_amount = max(down_payment - fee, Decimal(0))       # the fee counts toward the down payment
    balance = max(price - max(down_payment, fee), Decimal(0))  # what monthly payments cover
    dp_due = add_months(reserved_on, 1)

    items: list[dict] = [{"kind": "RESERVATION_FEE", "label": "Reservation fee", "due": reserved_on,
                          "amount": fee, "paid": fee, "status": "PAID"}]
    if dp_due_amount > 0:
        items.append({"kind": "DOWN_PAYMENT", "label": "Down payment (after the reservation fee)",
                      "due": dp_due, "amount": dp_due_amount})
    if balance > 0:
        if monthly > 0:
            count = int((balance / monthly).to_integral_value(rounding=ROUND_CEILING))
            for number in range(1, count + 1):
                amount = monthly if number < count else balance - monthly * (count - 1)
                items.append({"kind": "MONTHLY", "label": f"Monthly payment {number} of {count}",
                              "due": add_months(dp_due, number), "amount": amount.quantize(CENT)})
        else:
            items.append({"kind": "BALANCE", "label": "Balance (the listing has no monthly terms)",
                          "due": add_months(dp_due, 1), "amount": balance})

    received = sum((Decimal(payment.amount) for payment in payments), Decimal(0))
    left = received
    for item in items[1:]:
        applied = min(left, item["amount"])
        item["paid"] = applied
        left -= applied
    for item in items:
        item["status"] = _status(item["amount"], item["paid"], item["due"], today)

    total_paid = fee + received
    unpaid = [item for item in items if item["status"] != "PAID"]
    dp_item = next((item for item in items if item["kind"] == "DOWN_PAYMENT"), None)
    if down_payment <= 0:
        dp_status = "NONE"
    elif dp_item is None or dp_item["status"] == "PAID":
        dp_status = "PAID"
    elif dp_item["paid"] > 0:
        dp_status = "PARTIAL"
    else:
        dp_status = "NOT_PAID"
    monthly_count = sum(1 for item in items if item["kind"] in {"MONTHLY", "BALANCE"})
    return {
        "available": True,
        "price": price,
        "reservation_fee": fee,
        "down_payment": down_payment,
        "down_payment_status": dp_status,
        "down_payment_paid": min(down_payment, fee + (dp_item["paid"] if dp_item else Decimal(0))) if down_payment else Decimal(0),
        "monthly_rate": monthly,
        "monthly_payments": monthly_count,
        "balance_after_down_payment": balance,
        "total_paid": total_paid,
        "remaining": max(price - total_paid, Decimal(0)),
        "overpaid": max(total_paid - price, Decimal(0)),
        "fully_paid_by": items[-1]["due"],
        "is_fully_paid": not unpaid,
        "next_due": ({"label": unpaid[0]["label"], "due": unpaid[0]["due"],
                      "amount": unpaid[0]["amount"] - unpaid[0]["paid"], "status": unpaid[0]["status"]}
                     if unpaid else None),
        "terms": [
            "The reservation fee is credited toward the down payment.",
            "The rest of the down payment is due one month after the reservation.",
            ("Monthly payments of the listing's monthly rate start one month after the down payment; "
             "the last one is the remainder." if monthly > 0 else
             "The listing has no monthly rate, so the balance is one payment a month after the down payment."),
            "Recorded payments are applied in order: down payment first, then each monthly payment.",
        ],
        "items": items,
    }
