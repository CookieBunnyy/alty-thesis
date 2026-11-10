"""Add Abellar Realty's developers and partners (the office board's list) with
their logos. Safe to run again: a developer that already exists (same name,
any case) is left as it is, and only gets a logo if it has none.

    python scripts/seed_developers.py                       # the DATABASE_URL in .env
    python scripts/seed_developers.py --database-url "postgresql://..."

Logos are stored with the same file storage the API uses (Supabase Storage
when SUPABASE_URL / the service key are set in .env), so the live site shows
them too. Every developer on the board is accredited with Abellar Realty
(that is why it is on the official board), so each is recorded as VERIFIED
unless its accreditation was already set to something else on the
Partners / Developers page. Reference numbers and expiry dates aren't known
here: add them on that page.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
LOGOS = Path(__file__).with_name("developer_logos")

# (name, logo file, note) — the board's "Developers and Partners".
DEVELOPERS = [
    ("SMDC", "smdc.png", None),
    ("Northacre Builders Corporation", "northacre.png", None),
    ("Reignwood Development Corporation", "reignwood.png", None),
    ("Phinma Properties", "phinma.png", None),
    ("Jeika Properties Corporation", None, None),
    ("Hestia Properties and Development Corporation", "hestia.png", None),
    ("Paradisimo", "paradisimo.png", None),
    ("NextAsia", "nextasia.png", None),
    ("Amaia", "amaia.png", None),
    ("Axeia", "axeia.png", None),
    ("Golden Horizon", "golden-horizon.png", "Brgy. Hugo Perez, Trece Martires, Cavite"),
    ("Red Oak Properties", "red-oak.png", None),
    ("MyCitiHomes", "mycitihomes.png", None),
    ("Vanderbuilt Properties Internationale, Inc.", "vanderbuilt.png", None),
    ("Masaito Homes", "masaito.png", None),
    ("Lumina Homes", "lumina.png", None),
    ("Suntrust Properties", "suntrust.png", None),
    ("Ovialand", "ovialand.png", None),
    ("Ecoverde Homes", "ecoverde.png", None),
    ("Duraville Realty & Dev't. Corp.", "duraville.png", None),
    ("Wee Community Developers Inc.", "wee-community.png", None),
    ("Landnet Dynamic Realty Estate Management", "landnet.png", None),
    ("Lynville Land Development Corp.", "lynville.png", None),
    ("Idesia Heights", "idesia.png", None),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", help="defaults to DATABASE_URL from .env")
    args = parser.parse_args()
    if args.database_url:
        if not args.database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
            print("Use the Postgres connection string (postgresql://...), not the https:// project URL.")
            return 1
        os.environ["DATABASE_URL"] = args.database_url.replace("postgres://", "postgresql://", 1)

    from sqlalchemy import func, select

    import app.models  # noqa: F401
    from app.core.database import SessionLocal, engine
    from app.models.partner import Partner
    from app.services.audit import record_audit
    from app.services.document_storage import store_file
    from app.services.partner_logos import _logo_png

    print(f"Target database: {engine.url.database} on {engine.url.host}")
    added = logos = kept = verified = 0
    with SessionLocal() as db:
        for name, logo, note in DEVELOPERS:
            partner = db.execute(select(Partner).where(func.lower(Partner.name) == name.lower())).scalar_one_or_none()
            if partner is None:
                partner = Partner(name=name, partner_type="DEVELOPER", status="ACTIVE", address=note)
                db.add(partner)
                db.flush()
                record_audit(db, "PARTNER_CREATED", actor="seed_developers", entity_type="partners",
                             entity_id=partner.id, details={"name": name, "partner_type": "DEVELOPER"})
                added += 1
            else:
                kept += 1
            if (partner.accreditation_status or "NONE") == "NONE":
                partner.accreditation_status = "VERIFIED"
                partner.accreditation_notes = "Accredited developer on Abellar Realty's official Developers and Partners board."
                partner.accreditation_verified_by = "Abellar Realty (office board)"
                partner.accreditation_verified_at = datetime.utcnow()
                verified += 1
            if logo and not partner.logo_path:
                png = _logo_png((LOGOS / logo).read_bytes())
                path = f"partner-logos/{partner.id}-{secrets.token_hex(6)}.png"
                partner.logo_bucket = store_file("media", path, png, "image/png")
                partner.logo_path = path
                partner.logo_updated_at = datetime.utcnow()
                logos += 1
            db.commit()
    print(f"Developers added: {added}, already there: {kept}, logos uploaded: {logos}, "
          f"accreditation recorded: {verified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
