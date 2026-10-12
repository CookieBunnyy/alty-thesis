"""Add (or remove) demo listings and client reviews, to see the website full.

    python scripts/demo_showcase_data.py            # add the demo data
    python scripts/demo_showcase_data.py --remove   # delete exactly what was added

What it adds:
  * 14 AVAILABLE homes scattered around Cavite, Batangas, Laguna, Rizal,
    Bulacan and Metro Manila, with map positions, prices, terms, features and
    photos (served by the website from /demo-homes/);
  * 6 recently SOLD homes, each with a buyer, a completed sale handled by one
    of your active agents, and that buyer's review of the agent, so the home
    page's "What our clients say" section and agent ratings have content.

Unlike forecasting test data, these rows are meant to SHOW on the public
website, so they are not marked TEST_DATA. They are marked ``DEMO`` instead
(listing code DEMO-…, source and sync status DEMO): never pushed to the
central listings (only PENDING rows are) and removed exactly by ``--remove``.
The demo reviews count toward the agents' ratings while they exist, so remove
them before real client use the site.

The live database: pass its connection string (Render → Environment →
DATABASE_URL) for this one command, plus ``--allow-remote``; you are asked to
type YES before anything changes:

    $env:DATABASE_URL = "<live connection string>"      # PowerShell
    python scripts/demo_showcase_data.py --allow-remote
    python scripts/demo_showcase_data.py --allow-remote --remove
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Windows consoles may not print "₱"; never fail on printing a summary.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.property_listing import PropertyListing  # noqa: E402
from app.models.review import AgentReview  # noqa: E402
from app.models.transaction import PropertyTransaction  # noqa: E402
from forecast_test_data import repair_id_counters  # noqa: E402

MARK = "DEMO"
CODE = "DEMO-"
PHOTOS = [f"/demo-homes/home-{index:02d}.webp" for index in range(1, 14)]

# (title, category, place, lat, lng, price, bedrooms, bathrooms, features)
AVAILABLE = [
    ("Modern Pool Villa in Molino", "House and Lot", "Molino IV, Bacoor, Cavite", 14.4095, 120.9786, 9_850_000, 4, 4, "pool garage balcony"),
    ("Corner Townhouse near SM Bacoor", "Townhouse", "Talaba, Bacoor, Cavite", 14.4549, 120.9563, 3_650_000, 3, 2, "garage"),
    ("Family Home in Anabu", "House and Lot", "Anabu II, Imus, Cavite", 14.3985, 120.9412, 5_400_000, 3, 3, "garage backyard"),
    ("Garden Bungalow in Salitran", "House and Lot", "Salitran, Dasmariñas, Cavite", 14.3376, 120.9563, 4_250_000, 3, 2, "backyard"),
    ("Two-Storey Home in Manggahan", "House and Lot", "Manggahan, General Trias, Cavite", 14.3618, 120.8977, 4_980_000, 4, 3, "garage balcony"),
    ("Ridge-View Cottage in Tagaytay", "House and Lot", "Kaybagal South, Tagaytay City", 14.1101, 120.9763, 7_200_000, 3, 3, "balcony backyard"),
    ("Hillside House in Silang", "House and Lot", "Lalaan, Silang, Cavite", 14.2223, 120.9792, 6_150_000, 4, 3, "garage backyard"),
    ("Bayview Home in Batangas City", "House and Lot", "Alangilan, Batangas City", 13.7837, 121.0742, 5_750_000, 3, 3, "garage balcony"),
    ("Townhouse in Lipa City", "Townhouse", "Sabang, Lipa City, Batangas", 13.9454, 121.1620, 3_250_000, 2, 2, "kitchen"),
    ("Starter Home in Santo Tomas", "Townhouse", "San Rafael, Santo Tomas, Batangas", 14.0992, 121.1381, 2_890_000, 2, 1, "kitchen"),
    ("Lakeside House in Santa Rosa", "House and Lot", "Don Jose, Santa Rosa, Laguna", 14.2887, 121.0866, 6_480_000, 4, 3, "garage backyard"),
    ("Condo Unit near Calamba Crossing", "Condominium", "Real, Calamba, Laguna", 14.2088, 121.1594, 2_650_000, 1, 1, "balcony kitchen"),
    ("City-View Home in Antipolo", "House and Lot", "San Roque, Antipolo, Rizal", 14.5859, 121.1752, 7_850_000, 4, 4, "garage balcony backyard"),
    ("Townhouse near Malolos Cathedral", "Townhouse", "Santo Rosario, Malolos, Bulacan", 14.8441, 120.8107, 3_100_000, 3, 2, "garage"),
]
SOLD = [
    ("Pool House in BF Resort Village", "House and Lot", "Talon Dos, Las Piñas City", 14.4384, 120.9866, 8_900_000, 4, 4, "pool garage"),
    ("Townhouse in Cainta", "Townhouse", "San Isidro, Cainta, Rizal", 14.5759, 121.1179, 3_450_000, 3, 2, "garage"),
    ("Family Home in Alabang Hills", "House and Lot", "Cupang, Muntinlupa City", 14.4246, 121.0346, 10_500_000, 4, 4, "garage backyard"),
    ("Condo near Ortigas Center", "Condominium", "San Antonio, Pasig City", 14.5866, 121.0614, 4_800_000, 2, 1, "balcony"),
    ("Two-Storey Home in Fairview", "House and Lot", "Fairview, Quezon City", 14.7130, 121.0687, 6_900_000, 4, 3, "garage"),
    ("Townhouse in San Pedro", "Townhouse", "Landayan, San Pedro, Laguna", 14.3540, 121.0539, 3_050_000, 3, 2, "garage"),
]
REVIEWS = [
    ("Carla Mendoza", 5, "Our agent explained every step of the reservation and was always quick to reply. We moved in without any surprises."),
    ("Paolo Villanueva", 5, "Very patient with all our questions about the payment terms. Highly recommended for first-time buyers."),
    ("Bea Dela Cruz", 4, "Smooth process from viewing to signing. Paperwork took a little longer than expected, but our agent kept us updated."),
    ("Marco Santiago", 5, "Sobrang helpful! Our agent even checked the commute from my office before we decided. Salamat po!"),
    ("Liza Fernandez", 5, "Professional and honest about the pros and cons of each property. We found the right home in two weeks."),
    ("Rafael Torres", 4, "Good experience overall. The documents were complete and the turnover was on schedule."),
]


def _listing(index: int, row: tuple, status: str, rng: random.Random) -> PropertyListing:
    title, category, place, lat, lng, price, bedrooms, bathrooms, features = row
    photos = [PHOTOS[index % len(PHOTOS)], PHOTOS[(index + 4) % len(PHOTOS)], PHOTOS[(index + 9) % len(PHOTOS)]]
    down = round(price * 0.1, -3)
    return PropertyListing(
        external_listing_id=f"{CODE}{index + 1:03d}", title=title, category=category, village_name=place,
        lat=lat, lng=lng, price_total=Decimal(price), initial_dp=Decimal(down),
        monthly_rate=Decimal(round((price - down) / 180, -2)), num_bedrooms=bedrooms, num_bathrooms=bathrooms,
        has_garage="garage" in features, garage_spaces=1 if "garage" in features else 0,
        has_balcony="balcony" in features, has_backyard="backyard" in features or "pool" in features,
        has_kitchen=True, photos=photos, status=status, sync_status=MARK,
        # Condominium units have no lot of their own.
        lot_area_sqm=None if category == "Condominium" else Decimal(
            rng.randrange(60, 110, 5) if category == "Townhouse" else rng.randrange(120, 420, 10)),
        details=(f"{bedrooms}-bedroom {category.lower()} in {place}. "
                 f"{'With a private pool. ' if 'pool' in features else ''}Demo listing for previewing the website."),
    )


def add(db) -> None:
    repair_id_counters(db)
    if db.scalar(select(func.count()).select_from(PropertyListing).where(PropertyListing.external_listing_id.like(f"{CODE}%"))):
        sys.exit("Demo data is already there. Run with --remove first to add it again.")
    agents = db.execute(select(Agent.agent_id).where(func.upper(Agent.status) == "ACTIVE")
                        .order_by(Agent.agent_id)).scalars().all()
    rng = random.Random(2026)  # the same data every time
    for index, row in enumerate(AVAILABLE):
        db.add(_listing(index, row, "AVAILABLE", rng))
    db.flush()
    print(f"Added {len(AVAILABLE)} available demo homes.")
    if not agents:
        db.commit()
        print("No active agents found, so no sold homes or reviews were added.")
        return

    now = datetime.now(timezone.utc)
    for number, (row, (buyer, rating, text)) in enumerate(zip(SOLD, REVIEWS)):
        listing = _listing(len(AVAILABLE) + number, row, "SOLD", rng)
        db.add(listing)
        db.flush()
        agent_id = agents[number % len(agents)]
        sold_on = now - timedelta(days=12 + number * 9, hours=rng.randint(0, 6))
        client = Client(full_name=buyer, email=f"{buyer.split()[0].lower()}.demo@example.com", location=row[2],
                        agent_id=agent_id, property_id=listing.listing_id, transaction_type="SOLD",
                        transaction_date=sold_on, status="SOLD", source=MARK, sync_status=MARK)
        db.add(client)
        db.flush()
        sale = PropertyTransaction(client_id=client.client_id, property_id=listing.listing_id, agent_id=agent_id,
                                   transaction_type="SOLD", status="COMPLETED", transaction_date=sold_on,
                                   amount=listing.price_total, source=MARK, sync_status=MARK,
                                   notes="Demo sale for previewing the website")
        db.add(sale)
        db.flush()
        reviewed = (sold_on + timedelta(days=3)).replace(tzinfo=None)
        db.add(AgentReview(agent_id=agent_id, client_id=client.client_id, transaction_id=sale.transaction_id,
                           rating=rating, review=text, created_at=reviewed, updated_at=reviewed))
    db.commit()
    print(f"Added {len(SOLD)} sold demo homes with a buyer, a completed sale and a review each.")


def remove(db) -> None:
    demo_sales = select(PropertyTransaction.transaction_id).where(PropertyTransaction.source == MARK)
    reviews = db.execute(delete(AgentReview).where(AgentReview.transaction_id.in_(demo_sales))).rowcount
    sales = db.execute(delete(PropertyTransaction).where(PropertyTransaction.source == MARK)).rowcount
    clients = db.execute(delete(Client).where(Client.source == MARK)).rowcount
    listings = db.execute(delete(PropertyListing).where(PropertyListing.external_listing_id.like(f"{CODE}%"),
                                                        PropertyListing.sync_status == MARK)).rowcount
    db.commit()
    print(f"Removed {listings} demo homes, {clients} buyers, {sales} sales and {reviews} reviews.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="delete the demo data this script added")
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
        action = "REMOVE the demo data from" if args.remove else "ADD demo data to"
        if input(f"This will {action} {url.host}/{url.database}. Type YES to continue: ").strip() != "YES":
            sys.exit("Nothing changed.")
    with SessionLocal() as db:
        remove(db) if args.remove else add(db)


if __name__ == "__main__":
    main()
