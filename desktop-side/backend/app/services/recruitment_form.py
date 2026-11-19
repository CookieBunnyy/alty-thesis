"""Read an applicant's details from a photo or scan of the recruitment form.

The form's rows ("Full name  Patricia Anne Lim") are found by their labels;
OCR often drops the spaces ("Dateofbirth", "AndreaVillanueva"), so labels are
matched letter by letter and names are compared without spaces. The
recruiter and team are matched to the sellers and teams recorded in ALTY.

Nothing is invented: a detail that isn't on the form is left out, and the
broker declaration (a ticked box that OCR can't see reliably) is left for a
person to confirm.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.branch import Branch
from app.services.document_extraction import parse_date

# field -> printed labels (longest first is decided below).
LABELS: dict[str, tuple[str, ...]] = {
    "full_name": ("full name", "name of applicant", "applicant name", "applicant's name", "complete name"),
    "birthday": ("date of birth", "birth date", "birthday", "birthdate"),
    "address": ("home address", "present address", "complete address", "address"),
    "phone_number": ("mobile number", "mobile no", "cellphone number", "contact number", "contact no", "phone number"),
    "email": ("email address", "e-mail address", "email", "e-mail"),
    "recruiter": ("recruited by", "referred by", "recruiter", "sponsor"),
    "team": ("team / cluster", "team/cluster", "team", "cluster"),
    "experience": ("real estate experience", "years of experience", "experience"),
    "license": ("prc license no", "prc license number", "license number", "license no", "prc no"),
    "source": ("how you heard about us", "how did you hear about us", "source"),
}
SOURCES = (("referr", "REFERRAL"), ("walk", "WALK_IN"), ("job fair", "JOB_FAIR"), ("jobfair", "JOB_FAIR"),
           ("facebook", "SOCIAL_MEDIA"), ("social", "SOCIAL_MEDIA"), ("online", "ONLINE"), ("website", "ONLINE"))


def _pattern(label: str) -> re.Pattern:
    """Letters of the label with anything (or nothing) between them, at the start of a line."""
    letters = [re.escape(ch) for ch in label.casefold() if ch.isalnum()]
    return re.compile(r"^\s*" + r"[^a-z0-9]*".join(letters) + r"[\s:.\-]*(?P<value>.*)$", re.IGNORECASE)


_PATTERNS = sorted(((field, label, _pattern(label)) for field, labels in LABELS.items() for label in labels),
                   key=lambda item: -len(item[1]))


def _letters(text: str | None) -> str:
    return re.sub(r"[^a-z]", "", (text or "").casefold())


def _spaced(text: str) -> str:
    """'March14,1996' -> 'March 14, 1996'; '1year' -> '1 year'."""
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
    return re.sub(r",(?=\S)", ", ", text).strip()


def raw_rows(text: str) -> dict[str, str]:
    """The first value found for each field."""
    found: dict[str, str] = {}
    lines = [line.strip() for line in text.splitlines()]

    def label_of(line: str):
        for field, _label, pattern in _PATTERNS:
            match = pattern.match(line)
            if match:
                return field, match.group("value").strip()
        return None

    for index, line in enumerate(lines):
        parsed = label_of(line)
        if parsed is None:
            continue
        field, value = parsed
        # A PDF puts the written value on its own line, right after the label.
        # ("Team Pinyas" starts like a label but has a value, so it is the value.)
        if not value and index + 1 < len(lines) and lines[index + 1]:
            following = label_of(lines[index + 1])
            if following is None or following[1]:
                value = lines[index + 1]
        if value:
            found.setdefault(field, value)
    return found


def read_form(db: Session, text: str) -> dict:
    """{"fields": values in the applicant form's format, "found": the
    fields read, "notes": what a person should still check}."""
    rows = raw_rows(text)
    fields: dict = {}
    notes: list[str] = []
    if rows.get("full_name"):
        fields["full_name"] = " ".join(rows["full_name"].split())
    if rows.get("birthday"):
        try:
            fields["birthday"] = parse_date(_spaced(rows["birthday"])).date().isoformat()
        except (ValueError, OverflowError):
            notes.append("The date of birth couldn't be read; enter it from the form.")
    if rows.get("address"):
        fields["address"] = " ".join(rows["address"].split())
    if rows.get("phone_number"):
        digits = re.sub(r"[^\d+]", "", rows["phone_number"])
        if len(re.sub(r"\D", "", digits)) >= 7:
            fields["phone_number"] = digits
    if rows.get("email"):
        email = re.sub(r"\s+", "", rows["email"]).strip(".,;")
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            fields["email"] = email.lower()
    if rows.get("recruiter"):
        wanted = _letters(rows["recruiter"])
        agent = next((a for a in db.execute(select(Agent)).scalars() if _letters(a.full_name) == wanted), None)
        if agent is not None:
            fields["recruiter_agent_id"] = agent.agent_id
        else:
            fields["recruiter_name"] = _spaced(rows["recruiter"])
            notes.append("The recruiter isn't a seller in ALTY under that name; check the spelling.")
    if rows.get("team"):
        wanted = _letters(rows["team"])
        team = next((b for b in db.execute(select(Branch)).scalars()
                     if _letters(b.name) == wanted or _letters(b.name).endswith(wanted) or wanted.endswith(_letters(b.name))), None)
        if team is not None:
            fields["branch_id"] = team.id
        else:
            notes.append(f"No team named “{rows['team']}” is set up; choose the team yourself.")
    if rows.get("experience"):
        number = re.search(r"\d+(?:\.\d+)?", rows["experience"])
        if number:
            fields["experience_years"] = float(number.group())
        elif re.search(r"\bnone\b|^none|^no\b", rows["experience"].casefold()):
            fields["experience_years"] = 0.0
    if rows.get("license"):
        value = rows["license"]
        if re.match(r"\s*(none|n/?a|no\b|wala)", value, re.IGNORECASE) or _letters(value).startswith("none"):
            fields["has_license"] = False
        elif re.search(r"\d", value):
            fields["has_license"] = True
            fields["license_number"] = value.strip()
    if rows.get("source"):
        lowered = rows["source"].casefold()
        source = next((code for word, code in SOURCES if word in lowered), None)
        fields["source"] = source or "OTHER"
    if fields:
        notes.append("Tick the declaration that the applicant isn't bound to another broker after checking the form.")
    return {"fields": fields, "found": sorted(fields), "notes": notes}

