"""Add (or remove) clearly labelled test history so Forecasting can be tried.

    python scripts/forecast_test_data.py            # add 12 months of history
    python scripts/forecast_test_data.py --remove   # delete exactly what was added

What it adds, for the 12 complete months before the current one:
  * reservations that became completed sales, plus a few cancelled
    reservations, with a gentle upward trend and some seasonal variation;
  * one "[Test data] …" listing and buyer per deal, handled by your existing
    active agents.

Every row is titled "[Test data] …" and marked ``TEST_DATA`` (source and sync
status). TEST_DATA rows are never pushed to the central listings (only PENDING
rows are), the public website never shows them, and ``--remove`` deletes
exactly these rows.

The live database: pass its connection string (Render → Environment →
DATABASE_URL) for this one command, plus ``--allow-remote``; you are asked to
type YES before anything changes:

    $env:DATABASE_URL = "<live connection string>"      # PowerShell
    python scripts/forecast_test_data.py --allow-remote
    python scripts/forecast_test_data.py --allow-remote --remove
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.property_listing import PropertyListing  # noqa: E402
from app.models.transaction import PropertyTransaction  # noqa: E402

MARK = "TEST_DATA"
PREFIX = "[Test data]"
PH = timezone(timedelta(hours=8))
CATEGORIES = [("House and Lot", 4_200_000, 7_800_000), ("Condominium", 2_400_000, 5_200_000),
              ("Townhouse", 2_800_000, 4_600_000)]
# Completed sales per month, oldest first: an upward trend with a mid-year dip
# and a December bump, so the forecast has a real pattern to fit.
SALES_PER_MONTH = [3, 3, 5, 3, 4, 4, 3, 5, 5, 6, 5, 6]
CANCELLED_PER_MONTH = [1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1]


def _months_back(count: int) -> list[tuple[int, int]]:
    """The last ``count`` complete months, oldest first."""
    today = datetime.now(PH)
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        months.append((year, month))
    return list(reversed(months))


def _at(year: int, month: int, day: int, rng: random.Random) -> datetime:
    """A business-hours moment (Philippine time) on that day, as UTC."""
    local = datetime(year, month, min(day, 28), rng.randint(9, 17), rng.choice((0, 15, 30, 45)), tzinfo=PH)
    return local.astimezone(timezone.utc)


def add(db) -> None:
    if db.scalar(select(func.count()).select_from(PropertyTransaction).where(PropertyTransaction.source == MARK)):
        sys.exit("Test data is already there. Run with --remove first to add it again.")
    agents = db.execute(select(Agent.agent_id).where(func.upper(Agent.status) == "ACTIVE")
                        .order_by(Agent.agent_id)).scalars().all()
    if not agents:
        sys.exit("No active agents found; sync or add agents first.")
    rng = random.Random(2026)  # same data every time
    deal = 0
    totals = {"listings": 0, "sales": 0, "reservations": 0, "cancelled": 0, "revenue": Decimal(0)}
    for (year, month), sales, cancelled in zip(_months_back(12), SALES_PER_MONTH, CANCELLED_PER_MONTH):
        for index in range(sales + cancelled):
            deal += 1
            sold = index < sales
            category, low, high = rng.choice(CATEGORIES)
            price = Decimal(rng.randrange(low, high, 10_000))
            agent_id = agents[deal % len(agents)]
            listing = PropertyListing(
                title=f"{PREFIX} {category} #{deal}", category=category, price_total=price,
                initial_dp=(price * Decimal("0.2")).quantize(Decimal("1")), village_name=f"{PREFIX} Village",
                status="SOLD" if sold else "UNAVAILABLE", external_listing_id=f"TESTDATA-{deal:03d}",
                sync_status=MARK,
            )
            db.add(listing)
            db.flush()
            reserved_on = _at(year, month, rng.randint(1, 12), rng)
            client = Client(
                full_name=f"{PREFIX} Buyer {deal}", agent_id=agent_id, property_id=listing.listing_id,
                status="SOLD" if sold else "CANCELLED", source=MARK, sync_status=MARK,
                transaction_type="SOLD" if sold else "RESERVED",
                transaction_date=reserved_on.replace(tzinfo=None),
            )
            db.add(client)
            db.flush()
            fee = Decimal(rng.choice((25_000, 50_000, 75_000)))
            db.add(PropertyTransaction(
                client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                transaction_type="RESERVED", status="COMPLETED" if sold else "CANCELLED",
                transaction_date=reserved_on, amount=fee, source=MARK, sync_status=MARK,
                notes=f"{PREFIX} for trying Forecasting",
            ))
            totals["reservations"] += 1
            totals["listings"] += 1
            if sold:
                db.add(PropertyTransaction(
                    client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                    transaction_type="SOLD", status="COMPLETED",
                    transaction_date=_at(year, month, rng.randint(14, 28), rng), amount=price,
                    source=MARK, sync_status=MARK, notes=f"{PREFIX} for trying Forecasting",
                ))
                totals["sales"] += 1
                totals["revenue"] += price
            else:
                totals["cancelled"] += 1
    db.commit()
    first, last = _months_back(12)[0], _months_back(12)[-1]
    print(f"Added {totals['listings']} listings and buyers, {totals['reservations']} reservations "
          f"({totals['cancelled']} cancelled) and {totals['sales']} completed sales "
          f"(₱{totals['revenue']:,.0f}) from {first[1]:02d}/{first[0]} to {last[1]:02d}/{last[0]}.")
    print("Open Forecasting (or Analytics) to see them. Remove with: "
          "python scripts/forecast_test_data.py --remove")


def remove(db) -> None:
    transactions = db.execute(delete(PropertyTransaction).where(PropertyTransaction.source == MARK)).rowcount
    clients = db.execute(delete(Client).where(Client.source == MARK)).rowcount
    listings = db.execute(delete(PropertyListing).where(PropertyListing.sync_status == MARK)).rowcount
    db.commit()
    print(f"Removed {transactions} transactions, {clients} buyers and {listings} listings of test data.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="delete the test data this script added")
    parser.add_argument("--allow-remote", action="store_true",
                        help="allow a database that is not on this computer (not recommended)")
    args = parser.parse_args()
    url = make_url(settings.DATABASE_URL)
    remote = url.host not in ("localhost", "127.0.0.1", "::1", None)
    if remote and not args.allow_remote:
        sys.exit(f"Refusing to change {url.host}/{url.database}: add --allow-remote for a database "
                 "that isn't on this computer.")
    print(f"Database: {url.host}/{url.database}")
    if remote:
        action = "REMOVE the test data from" if args.remove else "ADD test data to"
        if input(f"This will {action} {url.host}/{url.database}. Type YES to continue: ").strip() != "YES":
            sys.exit("Nothing changed.")
    with SessionLocal() as db:
        remove(db) if args.remove else add(db)


if __name__ == "__main__":
    main()
