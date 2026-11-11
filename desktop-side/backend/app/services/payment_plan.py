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

Second interview: the equity (down payment less the reservation fee) is
usually paid monthly over the chosen terms (e.g. 12 to 24 months), and the
balance is then paid by the buyer's bank / Pag-IBIG / SSS loan in one lump sum
(loan takeout), by the developer's in-house financing (monthly), or in cash.
When the deal (or the listing) gives the equity terms and the financing, the
schedule follows them; otherwise the terms above apply.
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


FINANCING_LABEL = {"BANK": "Bank", "PAGIBIG": "Pag-IBIG", "SSS": "SSS", "IN_HOUSE": "In-house", "CASH": "Cash"}
LOANS = ("BANK", "PAGIBIG", "SSS")


def build_plan(reservation: PropertyTransaction, payments: list[TransactionPayment],
               today: date | None = None, financing_type: str | None = None,
               equity_terms_months: int | None = None) -> dict:
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
    equity_months = equity_terms_months or getattr(listing, "equity_terms_months", None) or 0
    monthly = Decimal(listing.monthly_rate or 0)
    reserved_on = _ph_date(reservation.transaction_date)
    dp_due_amount = max(down_payment - fee, Decimal(0))       # the fee counts toward the down payment
    balance = max(price - max(down_payment, fee), Decimal(0))  # what monthly payments cover
    dp_due = add_months(reserved_on, 1)

    items: list[dict] = [{"kind": "RESERVATION_FEE", "label": "Reservation fee", "due": reserved_on,
                          "amount": fee, "paid": fee, "status": "PAID"}]
    if dp_due_amount > 0 and equity_months > 1:
        # Monthly equity over the terms; the last one is the remainder.
        share = (dp_due_amount / equity_months).quantize(CENT)
        for number in range(1, equity_months + 1):
            amount = share if number < equity_months else dp_due_amount - share * (equity_months - 1)
            items.append({"kind": "EQUITY", "label": f"Equity {number} of {equity_months}",
                          "due": add_months(reserved_on, number), "amount": amount})
        dp_due = add_months(reserved_on, equity_months)
    elif dp_due_amount > 0:
        items.append({"kind": "DOWN_PAYMENT", "label": "Down payment (after the reservation fee)",
                      "due": dp_due, "amount": dp_due_amount})
    if balance > 0:
        if financing_type in LOANS:
            items.append({"kind": "LOAN_TAKEOUT",
                          "label": f"Loan takeout ({FINANCING_LABEL[financing_type]}): paid by the lender in one lump sum",
                          "due": add_months(dp_due, 1), "amount": balance})
        elif financing_type == "CASH":
            items.append({"kind": "BALANCE", "label": "Balance (cash)", "due": add_months(dp_due, 1), "amount": balance})
        elif monthly > 0:
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
    equity = [item for item in items if item["kind"] in {"DOWN_PAYMENT", "EQUITY"}]
    equity_paid = sum((item["paid"] for item in equity), Decimal(0))
    if down_payment <= 0:
        dp_status = "NONE"
    elif not equity or all(item["status"] == "PAID" for item in equity):
        dp_status = "PAID"
    elif equity_paid > 0:
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
        "down_payment_paid": min(down_payment, fee + equity_paid) if down_payment else Decimal(0),
        "financing_type": financing_type,
        "equity_terms_months": equity_months if equity_months > 1 else None,
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
            (f"The rest of the down payment (the equity) is paid monthly over {equity_months} months, "
             "starting a month after the reservation." if equity_months > 1 else
             "The rest of the down payment is due one month after the reservation."),
            (f"The balance is paid by the buyer's {FINANCING_LABEL[financing_type]} loan in one lump sum "
             "(loan takeout) after the equity." if financing_type in LOANS else
             "The balance is paid in cash a month after the equity." if financing_type == "CASH" else
             "Monthly payments of the listing's monthly rate start one month after the down payment; "
             "the last one is the remainder." if monthly > 0 else
             "The listing has no monthly rate, so the balance is one payment a month after the down payment."),
            "Recorded payments are applied in order: down payment first, then each later payment.",
        ],
        "items": items,
    }


def sample_computation(listing) -> dict | None:
    """The listing's sample computation sheet (second interview): TCP,
    reservation fee, net equity (down payment less the reservation fee) and its
    monthly terms, the amount to finance and the estimated monthly
    amortization. Only figures recorded on the listing are used."""
    if not listing.price_total:
        return None
    money = lambda value: float(Decimal(value).quantize(CENT)) if value is not None else None  # noqa: E731
    tcp = Decimal(listing.price_total)
    fee = Decimal(listing.reservation_fee) if listing.reservation_fee is not None else None
    down = Decimal(listing.initial_dp) if listing.initial_dp is not None else None
    net_equity = max(down - (fee or 0), Decimal(0)) if down is not None else None
    terms = listing.equity_terms_months or None
    return {
        "tcp": money(tcp),
        "reservation_fee": money(fee),
        "down_payment": money(down),
        "net_equity": money(net_equity),
        "equity_terms_months": terms,
        "monthly_equity": money(net_equity / terms) if net_equity and terms else None,
        "amount_to_finance": money(max(tcp - down, Decimal(0))) if down is not None else None,
        "monthly_amortization": money(listing.monthly_rate) if listing.monthly_rate else None,
        "note": "Sample only: the developer's computation sheet and the lender's approval give the final figures.",
    }
