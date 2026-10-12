"""Fill in sample lot sizes, so the lot area display can be tried.

    python scripts/sample_lot_areas.py            # fill blank lot areas
    python scripts/sample_lot_areas.py --remove   # clear exactly the values it filled

Only listings with no lot area get one, and condominium units and
apartments are skipped (they have no lot of their own). Sizes are realistic
for the category: townhouses 60–110 sqm, houses 120–400 sqm, other
properties 150–600 sqm. Each listing always gets the same sample value, so
``--remove`` clears a lot area only while it still equals that sample (a size
someone entered by hand is kept).

The live database: pass its connection string (Render → Environment →
DATABASE_URL) for this one command, plus ``--allow-remote``; you are asked to
type YES first:

    $env:DATABASE_URL = "<live connection string>"      # PowerShell
    python scripts/sample_lot_areas.py --allow-remote
"""

from __future__ import annotations

import argparse
import random
import sys
from decimal import Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.property_listing import PropertyListing  # noqa: E402

NO_LOT = ("condo", "condominium", "apartment", "studio", "loft", "unit")


def has_lot(category: str | None) -> bool:
    name = (category or "").strip().casefold()
    return not any(word in name for word in NO_LOT)


def sample_size(listing: PropertyListing) -> Decimal:
    """The same realistic size for a listing every time."""
    rng = random.Random(f"lot-{listing.listing_id}")
    name = (listing.category or "").casefold()
    if "town" in name or "row" in name:
        low, high, step = 60, 110, 5
    elif "house" in name or "bungalow" in name or "villa" in name:
        low, high, step = 120, 400, 10
    else:
        low, high, step = 150, 600, 10
    return Decimal(rng.randrange(low, high + 1, step))


def fill(db) -> None:
    listings = db.execute(select(PropertyListing).where(PropertyListing.lot_area_sqm.is_(None))).scalars().all()
    filled = skipped = 0
    for listing in listings:
        if not has_lot(listing.category):
            skipped += 1
            continue
        listing.lot_area_sqm = sample_size(listing)
        filled += 1
    db.commit()
    print(f"Filled a sample lot area on {filled} listing(s); skipped {skipped} condominium/apartment unit(s).")


def remove(db) -> None:
    cleared = 0
    for listing in db.execute(select(PropertyListing).where(PropertyListing.lot_area_sqm.is_not(None))).scalars():
        if has_lot(listing.category) and Decimal(listing.lot_area_sqm) == sample_size(listing):
            listing.lot_area_sqm = None
            cleared += 1
    db.commit()
    print(f"Cleared {cleared} sample lot area(s); sizes entered by hand were kept.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="clear the sample lot areas this script filled")
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
        action = "CLEAR the sample lot areas in" if args.remove else "FILL sample lot areas in"
        if input(f"This will {action} {url.host}/{url.database}. Type YES to continue: ").strip() != "YES":
            sys.exit("Nothing changed.")
    with SessionLocal() as db:
        remove(db) if args.remove else fill(db)


if __name__ == "__main__":
    main()
