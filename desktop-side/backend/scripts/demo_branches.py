"""Sample branches, agent assignments and applicants, so Branches,
Workforce planning and Recruitment can be tried.

    python scripts/demo_branches.py            # add the samples
    python scripts/demo_branches.py --remove   # take back exactly what it added

What it adds:
- three branches (codes DEMO-MM, DEMO-CAV, DEMO-LB): Metro Manila, Cavite,
  and Laguna & Batangas;
- every agent and listing WITHOUT a branch is put in the branch matching its
  location (Cavite towns -> Cavite, Laguna/Batangas towns -> Laguna &
  Batangas, everything else -> Metro Manila); agents without a designation
  get a sample one and their location as work area;
- six sample applicants at different recruitment stages (notes "[DEMO]").

``--remove`` deletes the DEMO branches (their agents and listings go back to
no branch), clears the sample designations/work areas it set (values typed
by hand are kept) and deletes the [DEMO] applicants.

The live database: pass its connection string (Render -> Environment ->
DATABASE_URL) for this one command, plus ``--allow-remote``; you are asked to
type YES first:

    $env:DATABASE_URL = "<live connection string>"      # PowerShell
    python scripts/demo_branches.py --allow-remote
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.branch import Branch  # noqa: E402
from app.models.property_listing import PropertyListing  # noqa: E402
from app.models.workforce import AgentApplicant  # noqa: E402

BRANCHES = [
    ("DEMO-MM", "Metro Manila Branch", "Ayala Avenue, Makati City", "(02) 8123 4567"),
    ("DEMO-CAV", "Cavite Branch", "Aguinaldo Highway, Imus, Cavite", "(046) 471 2345"),
    ("DEMO-LB", "Laguna & Batangas Branch", "National Highway, Santa Rosa, Laguna", "(049) 534 6789"),
]
CAVITE = ("cavite", "imus", "bacoor", "dasmari", "silang", "tagaytay", "general trias", "kawit", "molino", "salitran",
          "anabu", "carmona", "rosario", "trece")
SOUTH = ("laguna", "santa rosa", "sta. rosa", "calamba", "binan", "biñan", "san pedro", "batangas", "lipa", "tanauan",
         "san pablo", "cabuyao", "alangilan")
DESIGNATIONS = ("Sales Agent", "Sales Agent", "Senior Sales Agent", "Team Leader")
APPLICANTS = [
    ("Carlo Mendoza", "0917 555 0101", "Imus, Cavite", "DEMO-CAV", "Sales Agent", "REFERRAL", 2, True, 78, "APPLIED"),
    ("Bea Santos", "0918 555 0102", "Makati City", "DEMO-MM", "Senior Sales Agent", "ONLINE", 5, True, 85, "SCREENING"),
    ("Paolo Reyes", "0919 555 0103", "Santa Rosa, Laguna", "DEMO-LB", "Sales Agent", "JOB_FAIR", 1, False, 70, "INTERVIEW"),
    ("Liza Navarro", "0920 555 0104", "Bacoor, Cavite", "DEMO-CAV", "Trainee Agent", "SOCIAL_MEDIA", 0, False, 66, "INTERVIEW"),
    ("Miguel Torres", "0921 555 0105", "Pasig City", "DEMO-MM", "Sales Agent", "WALK_IN", 3, True, 88, "APPROVED"),
    ("Andrea Lim", "0922 555 0106", "Lipa, Batangas", "DEMO-LB", "Sales Agent", "ONLINE", 1, False, 52, "REJECTED"),
]
STAGES = ("APPLIED", "SCREENING", "INTERVIEW", "APPROVED")


def region(text: str | None) -> str:
    value = (text or "").casefold()
    if any(word in value for word in CAVITE):
        return "DEMO-CAV"
    if any(word in value for word in SOUTH):
        return "DEMO-LB"
    return "DEMO-MM"


def sample_designation(agent_id: str) -> str:
    return DESIGNATIONS[int(hashlib.sha256(agent_id.encode()).hexdigest(), 16) % len(DESIGNATIONS)]


def add(db) -> None:
    branches = {}
    for code, name, address, phone in BRANCHES:
        branch = db.execute(select(Branch).where(Branch.code == code)).scalar_one_or_none()
        if branch is None:
            branch = Branch(code=code, name=name, address=address, contact_number=phone, is_active=True,
                            notes="[DEMO] Sample branch from scripts/demo_branches.py")
            db.add(branch)
            db.flush()
        branches[code] = branch.id
    agents = listings = 0
    for agent in db.execute(select(Agent).where(Agent.branch_id.is_(None))).scalars():
        agent.branch_id = branches[region(agent.agent_location)]
        if agent.designation is None:
            agent.designation = sample_designation(agent.agent_id)
        if agent.work_area is None and agent.agent_location:
            agent.work_area = agent.agent_location
        agents += 1
    for listing in db.execute(select(PropertyListing).where(PropertyListing.branch_id.is_(None))).scalars():
        listing.branch_id = branches[region(f"{listing.village_name} {listing.title}")]
        listings += 1
    added = 0
    for name, phone, address, code, position, source, years, licensed, score, status in APPLICANTS:
        if db.execute(select(AgentApplicant).where(AgentApplicant.full_name == name,
                                                   AgentApplicant.notes.like("[DEMO]%"))).first():
            continue
        days = 30 - 5 * added
        history, at = [], datetime.utcnow() - timedelta(days=days)
        for stage in STAGES[:STAGES.index(status) + 1] if status in STAGES else ("APPLIED", "SCREENING"):
            history.append({"status": stage, "at": at.isoformat(timespec="seconds"), "by": "Demo data", "note": None})
            at += timedelta(days=3)
        if status == "REJECTED":
            history.append({"status": "REJECTED", "at": at.isoformat(timespec="seconds"), "by": "Demo data",
                            "note": "No real estate license and below the screening cut-off."})
        db.add(AgentApplicant(full_name=name, phone_number=phone, address=address, branch_id=branches[code],
                              desired_designation=position, source=source, experience_years=years,
                              has_license=licensed, license_number=f"PRC-{10000 + added}" if licensed else None,
                              screening_score=score, status=status, history=history, created_by="Demo data",
                              interview_on=date.today() + timedelta(days=3) if status == "INTERVIEW" else None,
                              notes="[DEMO] Sample applicant from scripts/demo_branches.py"))
        added += 1
    db.commit()
    print(f"Branches ready: {', '.join(name for _, name, _, _ in BRANCHES)}.")
    print(f"Put {agents} agent(s) and {listings} listing(s) without a branch into a branch; added {added} applicant(s).")


def remove(db) -> None:
    demo = {b.id: b for b in db.execute(select(Branch).where(Branch.code.like("DEMO-%"))).scalars()}
    agents = 0
    for agent in db.execute(select(Agent).where(Agent.branch_id.in_(demo or [-1]))).scalars():
        agent.branch_id = None
        if agent.designation == sample_designation(agent.agent_id):
            agent.designation = None
        if agent.work_area and agent.work_area == agent.agent_location:
            agent.work_area = None
        agents += 1
    listings = 0
    for listing in db.execute(select(PropertyListing).where(PropertyListing.branch_id.in_(demo or [-1]))).scalars():
        listing.branch_id = None
        listings += 1
    applicants = 0
    for applicant in db.execute(select(AgentApplicant).where(AgentApplicant.notes.like("[DEMO]%"))).scalars():
        db.delete(applicant)
        applicants += 1
    db.flush()
    for branch in demo.values():
        db.delete(branch)
    db.commit()
    print(f"Removed {len(demo)} demo branch(es) and {applicants} demo applicant(s); "
          f"{agents} agent(s) and {listings} listing(s) are back to no branch.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="take back what this script added")
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
        action = "REMOVE the demo branches from" if args.remove else "ADD demo branches to"
        if input(f"This will {action} {url.host}/{url.database}. Type YES to continue: ").strip() != "YES":
            sys.exit("Nothing changed.")
    with SessionLocal() as db:
        remove(db) if args.remove else add(db)


if __name__ == "__main__":
    main()
