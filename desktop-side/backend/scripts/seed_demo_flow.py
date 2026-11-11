"""Fill ALTY with demonstration records that follow the system's real flow:
property listing -> buyer inquiry and viewing -> reservation -> steps after the
reservation (documents, equity, loan, turnover) -> sale -> commission and its
payouts. About a year of history, so the dashboard, reports and charts have
something to show, plus one property left AVAILABLE for the live walkthrough
with the sample documents in docs/demo-documents.

    python scripts/seed_demo_flow.py                        # the DATABASE_URL in .env
    python scripts/seed_demo_flow.py --database-url "postgresql://..."

Run it on a fresh system: after scripts/reset_demo_data.py and
scripts/seed_developers.py. It refuses to run twice (it checks for its own
listings, ABR-26-xxxx). Everything it creates is demonstration data.

Accounts it creates (password for all: Demo-2026!):
    filingmanager          Filing Manager
    andrea.villanueva ...  Sellers (see SELLERS below)
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

PASSWORD = "Demo-2026!"
PH = timezone(timedelta(hours=8))
CENT = Decimal("0.01")

TEAMS = [
    ("Team Pinyas", "PIN", "Dasmariñas, Cavite"),
    ("Team Batangas", "BTG", "Lipa City, Batangas"),
    ("Team San Pablo", "SPL", "San Pablo City, Laguna"),
]

# username, full name, team, designation, base, lat, lng, phone, months with Abellar
SELLERS = [
    ("andrea.villanueva", "Andrea Villanueva", "Team Pinyas", "Senior Sales Agent", "Dasmariñas, Cavite", 14.3294, 120.9367, "0917 555 0201", 40),
    ("mark.dizon", "Mark Anthony Dizon", "Team Pinyas", "Sales Agent", "Imus, Cavite", 14.4297, 120.9367, "0917 555 0202", 26),
    ("bea.fernandez", "Bea Fernandez", "Team Pinyas", "Trainee Agent", "General Trias, Cavite", 14.3869, 120.8817, "0917 555 0203", 7),
    ("kristine.bautista", "Kristine Bautista", "Team Batangas", "Team Leader", "Lipa City, Batangas", 13.9411, 121.1631, "0917 555 0204", 52),
    ("paolo.ramirez", "Paolo Ramirez", "Team Batangas", "Sales Agent", "Sto. Tomas, Batangas", 14.1078, 121.1414, "0917 555 0205", 19),
    ("miguel.torres", "Miguel Torres", "Team Batangas", "Senior Sales Agent", "Batangas City", 13.7565, 121.0583, "0917 555 0206", 33),
    ("joanna.mercado", "Joanna Mercado", "Team San Pablo", "Team Leader", "San Pablo City, Laguna", 14.0693, 121.3255, "0917 555 0207", 45),
    ("rafael.gutierrez", "Rafael Gutierrez", "Team San Pablo", "Trainee Agent", "Calamba, Laguna", 14.2117, 121.1653, "0917 555 0208", 5),
]

# developer, project, address, lat, lng, category, model, price, dp %, monthly, lot, floor, beds, baths,
# RFO / PRE_SELLING, financing, reservation fee, equity months, team, amenities
PROJECTS = [
    ("Lumina Homes", "Lumina Tanza", "Brgy. Sahud Ulan, Tanza, Cavite", 14.3700, 120.8600, "House and Lot",
     "Bettina Single Attached", 1_850_000, 10, 11_500, 88, 40, 2, 1, "PRE_SELLING", ["BANK", "PAGIBIG", "IN_HOUSE"],
     15_000, 24, "Team Pinyas", ["Gated entrance", "Basketball court", "Playground", "Chapel"]),
    ("Amaia", "Amaia Scapes General Trias", "Brgy. Pasong Kawayan II, General Trias, Cavite", 14.3170, 120.9150,
     "House and Lot", "Alessa Single Attached", 3_450_000, 10, 24_800, 99, 46, 3, 1, "RFO", ["BANK", "PAGIBIG"],
     20_000, 12, "Team Pinyas", ["Clubhouse", "Swimming pool", "Jogging path", "24/7 security"]),
    ("Golden Horizon", "Golden Horizon Trece", "Brgy. Hugo Perez, Trece Martires, Cavite", 14.2830, 120.8660,
     "Townhouse", "Inner Townhouse", 2_150_000, 10, 14_200, 50, 45, 2, 1, "RFO", ["BANK", "PAGIBIG", "IN_HOUSE"],
     15_000, 12, "Team Pinyas", ["Perimeter fence", "Multi-purpose hall", "Playground"]),
    ("Suntrust Properties", "Suntrust Verona", "Brgy. Biga, Silang, Cavite", 14.2300, 120.9750, "House and Lot",
     "Duplex Unit", 3_980_000, 15, 27_500, 110, 60, 3, 2, "RFO", ["BANK", "PAGIBIG"], 25_000, 18, "Team Pinyas",
     ["Clubhouse", "Swimming pool", "Landscaped parks"]),
    ("Idesia Heights", "Idesia Dasmariñas", "Brgy. Salitran, Dasmariñas, Cavite", 14.3290, 120.9500, "House and Lot",
     "Celine Model", 4_250_000, 15, 29_900, 120, 72, 3, 2, "PRE_SELLING", ["BANK", "PAGIBIG", "IN_HOUSE"],
     25_000, 24, "Team Pinyas", ["Clubhouse", "Lap pool", "Pocket parks", "Guard house"]),
    ("SMDC", "SMDC Charm Residences", "Ortigas Ave. Extension, Cainta, Rizal", 14.5810, 121.1150, "Condominium",
     "1-Bedroom Unit", 3_600_000, 10, 21_000, None, 26, 1, 1, "PRE_SELLING", ["BANK", "IN_HOUSE"], 25_000, 36,
     "Team Pinyas", ["Swimming pool", "Fitness gym", "Function room", "Retail podium"]),
    ("Ovialand", "Ovialand Sto. Tomas", "Brgy. San Pedro, Sto. Tomas, Batangas", 14.1050, 121.1400, "House and Lot",
     "Rowhouse Unit", 2_380_000, 10, 15_800, 60, 42, 2, 1, "RFO", ["BANK", "PAGIBIG"], 15_000, 12, "Team Batangas",
     ["Gated community", "Basketball court", "Linear park"]),
    ("MyCitiHomes", "MyCiti Lipa", "Brgy. Sabang, Lipa City, Batangas", 13.9460, 121.1620, "Townhouse",
     "End Unit Townhouse", 2_650_000, 10, 17_300, 64, 48, 2, 1, "RFO", ["PAGIBIG", "IN_HOUSE"], 15_000, 12,
     "Team Batangas", ["Covered court", "Playground", "Water system"]),
    ("Masaito Homes", "Masaito Homes Batangas", "Brgy. Balagtas, Batangas City", 13.7700, 121.0600,
     "House and Lot", "Twin Home", 2_450_000, 10, 16_400, 72, 44, 2, 1, "RFO", ["BANK", "PAGIBIG"], 15_000, 12,
     "Team Batangas", ["Entrance arch", "Clubhouse", "Playground"]),
    ("Lynville Land Development Corp.", "Lynville Residences Calamba", "Brgy. Parian, Calamba, Laguna", 14.2130,
     121.1600, "House and Lot", "Single Attached", 2_990_000, 10, 19_800, 80, 50, 3, 1, "RFO", ["BANK", "PAGIBIG"],
     20_000, 12, "Team San Pablo", ["Clubhouse", "Swimming pool", "Basketball court"]),
    ("Phinma Properties", "Phinma San Pablo Homes", "Brgy. San Francisco, San Pablo City, Laguna", 14.0720,
     121.3200, "House and Lot", "Single Detached", 3_200_000, 10, 21_900, 100, 55, 3, 2, "PRE_SELLING",
     ["BANK", "PAGIBIG", "IN_HOUSE"], 20_000, 24, "Team San Pablo", ["Clubhouse", "Pool", "Chapel", "Parks"]),
]
UNITS = [(2, 4), (3, 11), (5, 8)]  # block, lot of the three units per project

# The property kept AVAILABLE for the live walkthrough (matches docs/demo-documents).
DEMO = {
    "code": "ABR-26-0101", "project": 0, "block": 7, "lot": 5, "seller": "andrea.villanueva",
    "buyer": {"client_id": "BUY-2026-0101", "name": "Carlo M. Mendoza", "email": "carlo.mendoza@example.com",
              "phone": "0917 555 0142", "address": "Blk 12 Lot 3, Brgy. Paliparan III, Dasmariñas, Cavite",
              "occupation": "IT Support Specialist", "civil_status": "Married"},
    "reservation_id": "RSV-2026-0101", "sale_id": "SALE-2026-0101", "voucher_no": "CV-2026-0101",
}

BUYERS = [
    ("Maria Clara Reyes", "Bacoor, Cavite", "Public School Teacher"),
    ("Jose Rizal Santos", "Imus, Cavite", "OFW (Seafarer)"),
    ("Angelica Dela Cruz", "Dasmariñas, Cavite", "Nurse"),
    ("Ramon Aquino", "General Trias, Cavite", "Business Owner"),
    ("Liza Manalo", "Tanza, Cavite", "Call Center Team Lead"),
    ("Benjamin Castro", "Silang, Cavite", "Civil Engineer"),
    ("Cristina Navarro", "Lipa City, Batangas", "Bank Officer"),
    ("Daniel Mendoza", "Sto. Tomas, Batangas", "Factory Supervisor"),
    ("Erika Valdez", "Batangas City", "Pharmacist"),
    ("Francis Ocampo", "Tanauan, Batangas", "OFW (Saudi Arabia)"),
    ("Grace Pascual", "San Pablo City, Laguna", "Government Employee"),
    ("Henry Robles", "Calamba, Laguna", "Electrician"),
    ("Isabel Gonzales", "Cabuyao, Laguna", "Accountant"),
    ("Jerome Salazar", "Sta. Rosa, Laguna", "Software Developer"),
    ("Karen Lim", "Cainta, Rizal", "Marketing Officer"),
    ("Leonardo Cruz", "Trece Martires, Cavite", "Police Officer"),
    ("Monica Villareal", "Carmona, Cavite", "HR Specialist"),
    ("Nathaniel Garcia", "Lipa City, Batangas", "Farm Owner"),
    ("Olivia Ramos", "Dasmariñas, Cavite", "Freelance Designer"),
    ("Patrick Domingo", "San Pedro, Laguna", "Sales Manager"),
    ("Queenie Bernardo", "Imus, Cavite", "Dentist"),
    ("Ricardo Flores", "Batangas City", "Retired Military"),
    ("Sheila Mae Torres", "Tanza, Cavite", "OFW (Hong Kong)"),
    ("Tomas Villanueva", "Calamba, Laguna", "Mechanic"),
    ("Ursula Santiago", "General Trias, Cavite", "Small Business Owner"),
    ("Victor Manuel Reyes", "Silang, Cavite", "Architect"),
    ("Wilma Aguilar", "San Pablo City, Laguna", "Public School Principal"),
    ("Xavier Enriquez", "Lipa City, Batangas", "Engineer"),
    ("Yolanda Perez", "Bacoor, Cavite", "Barangay Health Worker"),
    ("Zaldy Marquez", "Sto. Tomas, Batangas", "Truck Operator"),
    ("Arlene Mabini", "Tanauan, Batangas", "Store Manager"),
    ("Bryan Lacsamana", "Cabuyao, Laguna", "Production Engineer"),
]
BANKS = ["BDO", "BPI", "Metrobank", "Landbank", "Security Bank", "UnionBank"]
SALES_PER_MONTH = [1, 1, 2, 1, 1, 2, 2, 1, 2, 2, 2, 1]  # 11 months ago ... this month


def money(value) -> Decimal:
    return Decimal(value).quantize(CENT, ROUND_HALF_UP)


def at(day: date, hour: int = 10) -> datetime:
    """A Philippine-time moment on ``day``, stored in UTC."""
    return datetime.combine(day, time(hour)).replace(tzinfo=PH).astimezone(timezone.utc)


def naive(day: date, hour: int = 10) -> datetime:
    return at(day, hour).replace(tzinfo=None)


def add_months(day: date, months: int) -> date:
    from app.services.payment_plan import add_months as plan_add_months
    return plan_add_months(day, months)


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
    from app.api.v1.recruitment import next_agent_id
    from app.core.database import SessionLocal, engine
    from app.core.security import get_password_hash
    from app.models.agent import Agent
    from app.models.branch import Branch
    from app.models.bulletin import BulletinPost
    from app.models.client import Client
    from app.models.commission import CommissionRecord, CommissionRelease
    from app.models.deal import MILESTONE_KEYS, Deal, DealEvent
    from app.models.listing_assignment import ListingAssignment
    from app.models.partner import Partner
    from app.models.payment import TransactionPayment
    from app.models.property_listing import PropertyListing
    from app.models.transaction import PropertyTransaction
    from app.models.trip import Trip, TripBuyer
    from app.models.user import User
    from app.models.workforce import AgentApplicant
    from app.services.audit import record_audit

    rng = random.Random(2026)
    today = date.today()
    print(f"Target database: {engine.url.database} on {engine.url.host}")
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(PropertyListing)
                     .where(PropertyListing.external_listing_id.like("ABR-26-%"))):
            print("The demonstration records are already there (listings ABR-26-xxxx). "
                  "Run scripts/reset_demo_data.py first to start over.")
            return 1
        admin = db.execute(select(User).where(func.lower(User.role) == "administrator").order_by(User.id)).scalars().first()
        admin_name = admin.full_name if admin else "Administrator"
        password = get_password_hash(PASSWORD)

        # ---- teams, filing manager, sellers ------------------------------------------------
        teams: dict[str, Branch] = {}
        for name, code, address in TEAMS:
            team = db.execute(select(Branch).where(func.lower(Branch.name) == name.lower())).scalar_one_or_none()
            if team is None:
                team = Branch(name=name, code=code, address=address, is_active=True,
                              notes="Team / cluster (demonstration record)")
                db.add(team)
                db.flush()
            teams[name] = team
        if not db.scalar(select(User.id).where(User.username == "filingmanager")):
            db.add(User(username="filingmanager", full_name="Rose Ann Lacson", role="Filing Manager",
                        password_hash=password, is_active=True, email="filing@example.com"))

        sellers: dict[str, Agent] = {}
        for username, full_name, team, designation, base, lat, lng, phone, months in SELLERS:
            user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if user is not None and user.agent_id:
                sellers[username] = db.get(Agent, user.agent_id)
                continue
            agent = Agent(agent_id=next_agent_id(db), full_name=full_name, phone_number=phone, agent_location=base,
                          latitude=Decimal(str(lat)), longitude=Decimal(str(lng)), status="ACTIVE",
                          sync_status="SYNCED", branch_id=teams[team].id, designation=designation, work_area=base,
                          hired_on=add_months(today, -months), commission_visible=True)
            db.add(agent)
            db.flush()
            if user is None:
                db.add(User(username=username, full_name=full_name, role="Seller", agent_id=agent.agent_id,
                            branch_id=teams[team].id, password_hash=password, is_active=True,
                            email=f"{username}@example.com"))
            else:
                user.agent_id = agent.agent_id
            sellers[username] = agent
        # Who recruited whom (the trainees came in through recruitment).
        sellers["bea.fernandez"].recruited_by_agent_id = sellers["andrea.villanueva"].agent_id
        sellers["rafael.gutierrez"].recruited_by_agent_id = sellers["joanna.mercado"].agent_id
        sellers["paolo.ramirez"].recruited_by_agent_id = sellers["kristine.bautista"].agent_id
        db.flush()
        by_team: dict[str, list[Agent]] = {}
        for username, _, team, *_ in SELLERS:
            by_team.setdefault(team, []).append(sellers[username])

        # ---- developers and listings ------------------------------------------------------------
        def developer(name: str) -> Partner:
            partner = db.execute(select(Partner).where(func.lower(Partner.name) == name.lower())).scalar_one_or_none()
            if partner is None:
                partner = Partner(name=name, partner_type="DEVELOPER", status="ACTIVE")
                db.add(partner)
                db.flush()
            if partner.accreditation_status != "VERIFIED":
                partner.accreditation_status = "VERIFIED"
                partner.accreditation_verified_by = admin_name
                partner.accreditation_verified_at = datetime.utcnow()
            if partner.accreditation_valid_until is None:
                partner.accreditation_valid_from = add_months(today, -4)
                partner.accreditation_valid_until = add_months(today, 8)
            return partner

        listings: list[dict] = []
        number = 0

        def make_listing(index: int, block: int, lot: int, code: str) -> PropertyListing:
            (dev, project, address, lat, lng, category, model, price, dp, monthly, lot_area, floor, beds, baths,
             status, financing, fee, equity, team, amenities) = PROJECTS[index]
            jitter = (block * 7 + lot) / 10_000
            listing = PropertyListing(
                external_listing_id=code, title=f"{project} - {model}, Blk {block} Lot {lot}", category=category,
                project_name=project, partner_id=developer(dev).id, branch_id=teams[team].id,
                price_total=money(price), initial_dp=money(price * dp / 100), monthly_rate=money(monthly),
                reservation_fee=money(fee), equity_terms_months=equity, property_status=status,
                financing_options=financing, num_bedrooms=beds, num_bathrooms=baths, layout_type=model,
                village_name=address, lat=Decimal(str(round(lat + jitter, 6))), lng=Decimal(str(round(lng + jitter, 6))),
                lot_area_sqm=money(lot_area) if lot_area else None, floor_area_sqm=money(floor),
                amenity_list=amenities, has_kitchen=True, has_garage=category != "Condominium",
                garage_spaces=0 if category == "Condominium" else 1, has_balcony=category == "Condominium",
                details=(f"{model} at {project}, {'ready for occupancy' if status == 'RFO' else 'pre-selling'}. "
                         f"{beds} bedroom(s), {baths} bathroom(s), {floor} sqm floor area"
                         + (f" on a {lot_area} sqm lot." if lot_area else ".")),
                status="AVAILABLE", sync_status="SYNCED", marketing_status="APPROVED",
                marketing_approved_by=admin_name, marketing_approved_at=datetime.utcnow() - timedelta(days=360))
            db.add(listing)
            db.flush()
            return listing

        for index in range(len(PROJECTS)):
            for block, lot in UNITS:
                number += 1
                listing = make_listing(index, block, lot, f"ABR-26-{number:04d}")
                team_sellers = by_team[PROJECTS[index][18]]
                seller = team_sellers[(number - 1) % len(team_sellers)]
                db.add(ListingAssignment(listing_id=listing.listing_id, agent_id=seller.agent_id,
                                         assigned_by=admin_name, assigned_at=datetime.utcnow() - timedelta(days=350)))
                listings.append({"listing": listing, "seller": seller, "project": PROJECTS[index], "used": False})
        demo_listing = make_listing(DEMO["project"], DEMO["block"], DEMO["lot"], DEMO["code"])
        db.add(ListingAssignment(listing_id=demo_listing.listing_id, agent_id=sellers[DEMO["seller"]].agent_id,
                                 assigned_by=admin_name, assigned_at=datetime.utcnow() - timedelta(days=20)))
        db.flush()

        # ---- buyers ----------------------------------------------------------------------------
        buyer_pool = list(BUYERS)
        rng.shuffle(buyer_pool)
        buyer_no = 0

        def new_buyer(seller: Agent, status: str = "PROSPECT") -> Client:
            nonlocal buyer_no
            name, place, job = buyer_pool[buyer_no % len(buyer_pool)]
            buyer_no += 1
            handle = name.lower().replace(" ", ".").replace("ñ", "n")
            client = Client(external_client_id=f"BUY-2026-{buyer_no:04d}", full_name=name, location=place,
                            phone_number=f"0918 555 {buyer_no:04d}", email=f"{handle}@example.com", occupation=job,
                            civil_status=rng.choice(["Single", "Married", "Married"]), preferred_contact="Mobile",
                            purpose_of_purchase=rng.choice(["Residential", "Residential", "Investment"]),
                            agent_id=seller.agent_id, status=status, source="MANAGEMENT", sync_status="SYNCED")
            db.add(client)
            db.flush()
            return client

        def events(deal: Deal, steps: list[tuple[date, str | None, str | None, str]]) -> None:
            for day, from_stage, to_stage, note in steps:
                db.add(DealEvent(deal_id=deal.id, from_stage=from_stage, to_stage=to_stage, changes={}, note=note,
                                 actor=admin_name if to_stage not in ("INQUIRY", "VIEWING") else deal.agent_id and
                                 db.get(Agent, deal.agent_id).full_name, created_at=naive(day, 9)))

        def take_listing(month_index: int) -> dict:
            free = [item for item in listings if not item["used"]]
            item = free[(month_index * 5) % len(free)]
            item["used"] = True
            return item

        def pay_plan(reservation: PropertyTransaction, listing: PropertyListing, months: int, until: date,
                     skip: int | None = None) -> None:
            """Equity paid monthly from a month after the reservation, up to ``until``."""
            equity = money(Decimal(listing.initial_dp) - Decimal(reservation.amount))
            share = money(equity / months)
            reserved_on = reservation.transaction_date.astimezone(PH).date()
            for n in range(1, months + 1):
                due = add_months(reserved_on, n)
                if due > until:
                    break
                if skip is not None and n == skip:
                    continue
                amount = share if n < months else equity - share * (months - 1)
                db.add(TransactionPayment(transaction_id=reservation.transaction_id, amount=amount,
                                          paid_at=due - timedelta(days=rng.randint(0, 3)),
                                          note=f"Equity {n} of {months} (OR-{rng.randint(10000, 99999)})",
                                          recorded_by=admin_name))

        def milestones(done: dict[str, date]) -> dict:
            return {key: {"done_on": day.isoformat(), "by": admin_name, "note": None}
                    for key, day in done.items() if day <= today}

        # ---- a year of sales ------------------------------------------------------------------------
        sales = []
        for month_offset, count in zip(range(11, -1, -1), SALES_PER_MONTH):
            month_start = add_months(date(today.year, today.month, 1), -month_offset)
            for k in range(count):
                last_day = min(add_months(month_start, 1) - timedelta(days=1), today - timedelta(days=1))
                sale_day = month_start + timedelta(days=rng.randint(2, max(2, (last_day - month_start).days)))
                item = take_listing(len(sales))
                listing, seller = item["listing"], item["seller"]
                client = new_buyer(seller, "SOLD")
                equity_months = rng.choice([1, 3, 3, 6])
                reserve_day = add_months(sale_day, -equity_months) - timedelta(days=rng.randint(5, 20))
                inquiry_day = reserve_day - timedelta(days=rng.randint(10, 30))
                financing = rng.choice([f for f in listing.financing_options if f != "IN_HOUSE"] or ["BANK"])
                fee = Decimal(listing.reservation_fee)
                reservation = PropertyTransaction(
                    external_transaction_id=f"RSV-26-{len(sales) + 1:04d}", client_id=client.client_id,
                    property_id=listing.listing_id, agent_id=seller.agent_id, transaction_type="RESERVED",
                    transaction_date=at(reserve_day), amount=fee, status="COMPLETED", source="MANAGEMENT",
                    sync_status="SYNCED", created_at=at(reserve_day))
                sale = PropertyTransaction(
                    external_transaction_id=f"SALE-26-{len(sales) + 1:04d}", client_id=client.client_id,
                    property_id=listing.listing_id, agent_id=seller.agent_id, transaction_type="SOLD",
                    transaction_date=at(sale_day, 15), amount=money(listing.price_total), status="COMPLETED",
                    source="MANAGEMENT", sync_status="SYNCED", created_at=at(sale_day, 15))
                db.add_all([reservation, sale])
                db.flush()
                pay_plan(reservation, listing, equity_months, sale_day)
                balance = money(Decimal(listing.price_total) - Decimal(listing.initial_dp))
                db.add(TransactionPayment(transaction_id=reservation.transaction_id, amount=balance,
                                          paid_at=sale_day - timedelta(days=2),
                                          note=f"Loan takeout ({financing.title()})", recorded_by=admin_name))
                listing.status, listing.status_changed_at = "SOLD", naive(sale_day, 15)
                client.transaction_type, client.transaction_date, client.property_id = "SOLD", at(sale_day, 15), listing.listing_id
                steps = {key: reserve_day + timedelta(days=d) for key, d in
                         [("DOC_RESERVATION_AGREEMENT", 0), ("DOC_BUYER_INFO_SHEET", 1), ("DOC_VALID_IDS", 1),
                          ("DOC_PROOF_OF_INCOME", 3), ("LOAN_APPLIED", 10)]}
                steps.update(EQUITY_PAID=sale_day - timedelta(days=12), LOAN_APPROVED=sale_day - timedelta(days=5),
                             TURNOVER=sale_day)
                if sale_day + timedelta(days=45) <= today:
                    steps["FULLY_PAID"] = sale_day + timedelta(days=45)
                deal = Deal(client_id=client.client_id, listing_id=listing.listing_id, agent_id=seller.agent_id,
                            stage="CLOSED", inquiry_date=inquiry_day, viewing_type=rng.choice(["PHYSICAL", "VIRTUAL"]),
                            viewing_at=naive(inquiry_day + timedelta(days=4), 9), reservation_date=reserve_day,
                            reservation_status="COMPLETED", developer_status="APPROVED", closing_date=sale_day,
                            reservation_transaction_id=reservation.transaction_id,
                            sale_transaction_id=sale.transaction_id, financing_type=financing,
                            equity_terms_months=equity_months, milestones=milestones(steps),
                            created_by=seller.full_name, created_at=naive(inquiry_day), updated_at=naive(sale_day))
                db.add(deal)
                db.flush()
                events(deal, [(inquiry_day, None, "INQUIRY", "Inquiry recorded"),
                              (inquiry_day + timedelta(days=4), "INQUIRY", "VIEWING", "Site viewing"),
                              (reserve_day, "VIEWING", "RESERVED", "Reservation recorded"),
                              (reserve_day + timedelta(days=1), "RESERVED", "DEVELOPER_PROCESSING",
                               "Reservation sent to the developer"),
                              (sale_day, "DEVELOPER_PROCESSING", "CLOSED", "Sale recorded")])
                sales.append((sale, sale_day, seller, listing))

        # ---- commissions on those sales ----------------------------------------------------------------
        for index, (sale, sale_day, seller, listing) in enumerate(sales):
            rate = Decimal(rng.choice([5, 5, 5, 4, 3]))
            amount = money(Decimal(sale.amount) * rate / 100)
            age = (today - sale_day).days
            record = CommissionRecord(
                kind="SALE", transaction_id=sale.transaction_id, agent_id=seller.agent_id,
                listing_id=listing.listing_id, basis_amount=money(sale.amount), rate_percent=rate, amount=amount,
                agreement_reference=f"CA-{listing.external_listing_id}",
                agreement_notes=f"{rate}% of the TCP, as agreed with {db.get(Partner, listing.partner_id).name}.",
                record_date=sale_day + timedelta(days=3), created_by=admin_name, status="UNRELEASED",
                approval_status="PENDING")
            db.add(record)
            db.flush()
            if age > 25 or index % 2:  # the newest ones still wait for approval
                record.approval_status, record.approved_by = "APPROVED", admin_name
                record.approved_at = naive(min(today, sale_day + timedelta(days=6)))
            payouts = []
            if record.approval_status == "APPROVED" and age > 75:
                payouts = [(amount, sale_day + timedelta(days=30))] if index % 3 else \
                    [(money(amount / 2), sale_day + timedelta(days=20)), (amount - money(amount / 2), sale_day + timedelta(days=50))]
            elif record.approval_status == "APPROVED" and age > 25:
                payouts = [(money(amount / 2), sale_day + timedelta(days=20))]
            paid = Decimal(0)
            for value, day in payouts:
                method = rng.choice(["ATM", "BANK_TRANSFER", "BANK_TRANSFER", "CHECK"])
                db.add(CommissionRelease(record_id=record.id, amount=value, released_on=day, method=method,
                                         bank_name=rng.choice(BANKS), reference=f"REF-{rng.randint(100000, 999999)}",
                                         particulars=f"Commission, {listing.title}", recorded_by=admin_name,
                                         created_at=naive(day)))
                paid += value
                record.released_on = day
            if paid:
                record.released_amount = paid
                record.status = "RELEASED" if paid >= amount else "PARTIALLY_RELEASED"

        # ---- reservations still in progress ("under evaluation") --------------------------------------------
        for n, (days_ago, months, financing, stage_steps, skip) in enumerate([
            (130, 12, "PAGIBIG", ["DOC_RESERVATION_AGREEMENT", "DOC_BUYER_INFO_SHEET", "DOC_VALID_IDS",
                                  "DOC_PROOF_OF_INCOME", "LOAN_APPLIED"], None),
            (95, 24, "BANK", ["DOC_RESERVATION_AGREEMENT", "DOC_BUYER_INFO_SHEET", "DOC_VALID_IDS"], 2),
            (60, 12, "IN_HOUSE", ["DOC_RESERVATION_AGREEMENT", "DOC_BUYER_INFO_SHEET", "DOC_VALID_IDS",
                                  "DOC_PROOF_OF_INCOME"], None),
            (8, 24, "PAGIBIG", [], None),
        ]):
            item = take_listing(len(sales) + n)
            listing, seller = item["listing"], item["seller"]
            client = new_buyer(seller, "RESERVED")
            reserve_day = today - timedelta(days=days_ago)
            inquiry_day = reserve_day - timedelta(days=rng.randint(10, 25))
            reservation = PropertyTransaction(
                external_transaction_id=f"RSV-26-{len(sales) + n + 1:04d}", client_id=client.client_id,
                property_id=listing.listing_id, agent_id=seller.agent_id, transaction_type="RESERVED",
                transaction_date=at(reserve_day), amount=money(listing.reservation_fee), status="RESERVED",
                source="MANAGEMENT", sync_status="SYNCED", created_at=at(reserve_day))
            db.add(reservation)
            db.flush()
            pay_plan(reservation, listing, months, today, skip=skip)
            listing.status, listing.status_changed_at = "RESERVED", naive(reserve_day)
            client.transaction_type, client.transaction_date, client.property_id = "RESERVED", at(reserve_day), listing.listing_id
            done = {key: reserve_day + timedelta(days=2 + i * 3) for i, key in enumerate(stage_steps)}
            deal = Deal(client_id=client.client_id, listing_id=listing.listing_id, agent_id=seller.agent_id,
                        stage="DEVELOPER_PROCESSING" if stage_steps else "RESERVED", inquiry_date=inquiry_day,
                        viewing_type="PHYSICAL", viewing_at=naive(inquiry_day + timedelta(days=3), 9),
                        reservation_date=reserve_day, reservation_status="RESERVED",
                        developer_status="IN_PROCESS" if stage_steps else "NOT_STARTED",
                        reservation_transaction_id=reservation.transaction_id, financing_type=financing,
                        equity_terms_months=months, milestones=milestones(done), created_by=seller.full_name,
                        created_at=naive(inquiry_day), updated_at=naive(today))
            db.add(deal)
            db.flush()
            steps = [(inquiry_day, None, "INQUIRY", "Inquiry recorded"),
                     (inquiry_day + timedelta(days=3), "INQUIRY", "VIEWING", "Site viewing"),
                     (reserve_day, "VIEWING", "RESERVED", "Reservation recorded")]
            if stage_steps:
                steps.append((reserve_day + timedelta(days=2), "RESERVED", "DEVELOPER_PROCESSING",
                              "Reservation sent to the developer"))
            events(deal, steps)

        # ---- cancelled reservations and lost buyers -------------------------------------------------------
        for n, (days_ago, reason) in enumerate([(200, "Buyer's bank loan was not approved"),
                                                (75, "Buyer will work abroad and withdrew the reservation")]):
            item = rng.choice([i for i in listings if not i["used"]])
            listing, seller = item["listing"], item["seller"]
            client = new_buyer(seller, "CANCELLED")
            reserve_day = today - timedelta(days=days_ago)
            reservation = PropertyTransaction(
                external_transaction_id=f"RSV-26-C{n + 1:03d}", client_id=client.client_id,
                property_id=listing.listing_id, agent_id=seller.agent_id, transaction_type="RESERVED",
                transaction_date=at(reserve_day), amount=money(listing.reservation_fee), status="CANCELLED",
                cancellation_reason=reason, cancelled_at=naive(reserve_day + timedelta(days=40)),
                cancelled_by=admin_name, source="MANAGEMENT", sync_status="SYNCED", created_at=at(reserve_day))
            db.add(reservation)
            db.flush()
            deal = Deal(client_id=client.client_id, listing_id=listing.listing_id, agent_id=seller.agent_id,
                        stage="LOST", inquiry_date=reserve_day - timedelta(days=14), reservation_date=reserve_day,
                        reservation_status="CANCELLED", lost_reason=reason,
                        reservation_transaction_id=reservation.transaction_id, created_by=seller.full_name,
                        created_at=naive(reserve_day - timedelta(days=14)), updated_at=naive(reserve_day + timedelta(days=40)))
            db.add(deal)
            db.flush()
            events(deal, [(reserve_day - timedelta(days=14), None, "INQUIRY", "Inquiry recorded"),
                          (reserve_day, "INQUIRY", "RESERVED", "Reservation recorded"),
                          (reserve_day + timedelta(days=40), "RESERVED", "LOST", f"Reservation cancelled: {reason}")])

        # ---- buyers still deciding (inquiries and viewings) ------------------------------------------------
        open_deals = []
        for n, (stage, viewing, days) in enumerate([("INQUIRY", None, -6), ("INQUIRY", None, -2),
                                                     ("VIEWING", "PHYSICAL", 2), ("VIEWING", "VIRTUAL", 4),
                                                     ("VIEWING", "PHYSICAL", 6), ("LOST", None, -30)]):
            item = [i for i in listings if not i["used"]][n * 2 % max(1, len([i for i in listings if not i["used"]]))]
            listing, seller = item["listing"], item["seller"]
            client = new_buyer(seller)
            inquiry_day = today - timedelta(days=abs(days) + 5)
            deal = Deal(client_id=client.client_id, listing_id=listing.listing_id, agent_id=seller.agent_id, stage=stage,
                        inquiry_date=inquiry_day, viewing_type=viewing,
                        viewing_at=naive(today + timedelta(days=days), 9) if viewing else None,
                        lost_reason="Chose a property from another broker" if stage == "LOST" else None,
                        created_by=seller.full_name, created_at=naive(inquiry_day), updated_at=naive(inquiry_day))
            db.add(deal)
            db.flush()
            steps = [(inquiry_day, None, "INQUIRY", "Inquiry recorded")]
            if viewing:
                steps.append((inquiry_day + timedelta(days=1), "INQUIRY", "VIEWING", f"{viewing.title()} viewing arranged"))
            if stage == "LOST":
                steps.append((inquiry_day + timedelta(days=10), "INQUIRY", "LOST", "Chose a property from another broker"))
            events(deal, steps)
            open_deals.append((deal, client, listing, seller))

        # ---- recruitment ---------------------------------------------------------------------------------------
        def applicant(name, status, days_ago, recruiter, team, agent=None, note=None, **extra):
            created = today - timedelta(days=days_ago)
            order = ["APPLIED", "SCREENING", "INTERVIEW", "APPROVED", "ONBOARDED"]
            path = order[:order.index(status) + 1] if status in order else ["APPLIED", status]
            history = [{"status": s, "at": naive(created + timedelta(days=i * 6)).isoformat(timespec="seconds"),
                        "by": admin_name, "note": note if s == status else None} for i, s in enumerate(path)]
            first, last = name.split(" ")[0], name.split(" ")[-1]
            db.add(AgentApplicant(
                full_name=name, email=f"{first.lower()}.{last.lower()}@example.com",
                phone_number=f"0919 555 {rng.randint(1000, 9999)}", address=extra.get("address", "Cavite"),
                birthday=date(rng.randint(1985, 2002), rng.randint(1, 12), rng.randint(1, 28)),
                recruiter_agent_id=recruiter.agent_id if recruiter else None, not_bound_to_other_broker=True,
                declaration_date=created, branch_id=teams[team].id, source=extra.get("source", "REFERRAL"),
                experience_years=extra.get("years", 0), has_license=extra.get("license", False),
                screening_score=extra.get("score"), interview_on=created + timedelta(days=12) if status not in
                ("APPLIED", "SCREENING") else None, status=status, history=history,
                agent_id=agent.agent_id if agent else None, created_by="Rose Ann Lacson",
                created_at=naive(created), updated_at=naive(created + timedelta(days=len(path) * 6))))

        applicant("Bea Fernandez", "ONBOARDED", 230, sellers["andrea.villanueva"], "Team Pinyas",
                  sellers["bea.fernandez"], score=84, address="General Trias, Cavite")
        applicant("Rafael Gutierrez", "ONBOARDED", 170, sellers["joanna.mercado"], "Team San Pablo",
                  sellers["rafael.gutierrez"], score=79, address="Calamba, Laguna")
        applicant("Paolo Ramirez", "ONBOARDED", 360, sellers["kristine.bautista"], "Team Batangas",
                  sellers["paolo.ramirez"], score=88, address="Sto. Tomas, Batangas", years=2)
        applicant("Janine Soriano", "APPROVED", 40, sellers["andrea.villanueva"], "Team Pinyas", score=86,
                  address="Imus, Cavite", source="SOCIAL_MEDIA")
        applicant("Kevin Abalos", "INTERVIEW", 22, sellers["miguel.torres"], "Team Batangas", score=74,
                  address="Batangas City")
        applicant("Lorraine Cabrera", "SCREENING", 12, sellers["joanna.mercado"], "Team San Pablo",
                  address="San Pablo City, Laguna", source="WALK_IN")
        applicant("Marvin Estrada", "APPLIED", 3, sellers["mark.dizon"], "Team Pinyas", address="Bacoor, Cavite",
                  source="ONLINE")
        applicant("Nicole Pineda", "REJECTED", 65, None, "Team Batangas", note="Still bound to another broker",
                  address="Lipa City, Batangas", source="JOB_FAIR")
        applicant("Oscar Lumbres", "WITHDRAWN", 90, sellers["kristine.bautista"], "Team Batangas",
                  note="Took a job abroad", address="Tanauan, Batangas")

        # ---- office board: announcements and memos ------------------------------------------------------------
        quarter_start = date(today.year, (today.month - 1) // 3 * 3 + 1, 1)
        quarter_end = add_months(quarter_start, 3) - timedelta(days=1)
        quarter = f"Q{(today.month - 1) // 3 + 1} {today.year}"
        next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        db.add_all([
            BulletinPost(board="ANNOUNCEMENT", category="MEETING", title="Monthly sales meeting",
                         body="All sellers and team leaders: monthly sales meeting at the Dasmariñas office. "
                              "Bring your updated buyer list and reservation documents.",
                         event_at=naive(next_monday, 9), pinned=True, created_by_user_id=admin.id if admin else None,
                         created_by_name=admin_name, created_at=naive(today - timedelta(days=2))),
            BulletinPost(board="ANNOUNCEMENT", category="PROJECT", title="Now open: Idesia Dasmariñas (pre-selling)",
                         body="Pre-selling units of the Celine Model are open for reservation. Reservation fee "
                              "PHP 25,000; equity payable in 24 months; bank, Pag-IBIG and in-house financing.",
                         partner_id=developer("Idesia Heights").id, created_by_name=admin_name,
                         created_by_user_id=admin.id if admin else None, created_at=naive(today - timedelta(days=9))),
            BulletinPost(board="MEMO", category="TARGET", title=f"{quarter} sales target",
                         body="Company target for the quarter. Every reservation that becomes a sale counts.",
                         valid_from=quarter_start, valid_until=quarter_end, target_amount=money(25_000_000),
                         created_by_name=admin_name, created_by_user_id=admin.id if admin else None,
                         created_at=naive(quarter_start)),
            BulletinPost(board="MEMO", category="INCENTIVE", title=f"{quarter} sales incentive",
                         body="Cash incentive for sellers who reach these sales within the quarter.",
                         valid_from=quarter_start, valid_until=quarter_end,
                         tiers=[{"label": "Bronze", "minimum_sales": 3_000_000.0, "reward": "PHP 5,000 cash incentive"},
                                {"label": "Silver", "minimum_sales": 6_000_000.0, "reward": "PHP 12,000 cash incentive"},
                                {"label": "Gold", "minimum_sales": 10_000_000.0, "reward": "PHP 20,000 and a plaque"}],
                         created_by_name=admin_name, created_by_user_id=admin.id if admin else None,
                         created_at=naive(quarter_start + timedelta(days=1))),
        ])

        # ---- tripping schedule (site visits) ---------------------------------------------------------------------
        for n, (deal, client, listing, seller) in enumerate(d for d in open_deals if d[0].stage == "VIEWING"):
            trip = Trip(trip_date=today + timedelta(days=2 + n * 2), pickup_time=["08:30", "09:00", "13:30"][n % 3],
                        pickup_point="Abellar Realty office, Dasmariñas", subdivision=listing.project_name,
                        listing_id=listing.listing_id, partner_id=listing.partner_id, agent_id=seller.agent_id,
                        status="CONFIRMED" if n == 0 else "SCHEDULED", notes="Bring a valid ID for the site gate.",
                        created_by_user_id=admin.id if admin else None, updated_by_name=seller.full_name)
            trip.buyers = [TripBuyer(client_id=client.client_id, name=client.full_name, phone=client.phone_number)]
            db.add(trip)
        for n, (sale, sale_day, seller, listing) in enumerate(sales[-2:]):
            client = db.get(Client, sale.client_id)
            trip = Trip(trip_date=sale_day - timedelta(days=70), pickup_time="08:30",
                        pickup_point="Abellar Realty office, Dasmariñas", subdivision=listing.project_name,
                        listing_id=listing.listing_id, partner_id=listing.partner_id, agent_id=seller.agent_id,
                        status="DONE", updated_by_name=seller.full_name)
            trip.buyers = [TripBuyer(client_id=client.client_id, name=client.full_name, phone=client.phone_number)]
            db.add(trip)

        record_audit(db, "DEMO_DATA_SEEDED", actor="seed_demo_flow", entity_type="system", entity_id="demo",
                     details={"listings": len(listings) + 1, "sales": len(sales), "buyers": buyer_no})
        db.commit()

    print(f"Teams: {len(TEAMS)} | sellers: {len(SELLERS)} (+ filingmanager) | listings: {len(listings) + 1} | "
          f"sales: {len(sales)} | buyers: {buyer_no}")
    print(f"Accounts: filingmanager and each seller (e.g. andrea.villanueva), password {PASSWORD}")
    print(f"Live walkthrough property: {DEMO['code']} (Lumina Tanza, Blk {DEMO['block']} Lot {DEMO['lot']}), "
          "use the files in docs/demo-documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
