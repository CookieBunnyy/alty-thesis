import re
import spacy

HOUSE_KEYWORDS = {"house", "subdivision", "home", "villa", "village", "townhouse", "town house"}
CONDO_KEYWORDS = {"condo", "apartment"}
WORKPLACE_KEYWORDS = {"office", "work", "job site", "workplace", "site", "commute"}

# Words that indicate the WORKPLACE_REGEX captured a generic phrase,
# not an actual place name (e.g. "near my work site location")
GENERIC_LOCATION_WORDS = {
    "location", "area", "place", "site", "office", "work",
    "workplace", "job", "here", "there", "commute",
}

DOWNPAYMENT_KEYWORDS = {"downpayment", "down payment", "dp"}
MONTHLY_KEYWORDS = {"per month", "monthly", "a month", "/month", "each month"}

# Maps a phrase the user might type -> the normalized substring to search
# for inside the DB's free-text `layout_type` column via ILIKE.
LAYOUT_KEYWORDS = {
    "studio": "studio",
    "loft": "loft",
    "penthouse": "penthouse",
    "duplex": "duplex",
    "single attached": "single attached",
    "single detached": "single detached",
    "townhouse": "townhouse",
    "town house": "townhouse",
    "bungalow": "bungalow",
    "1-bedroom": "1-bedroom",
    "one bedroom": "1-bedroom",
    "2-bedroom": "2-bedroom",
    "two bedroom": "2-bedroom",
    "3-bedroom": "3-bedroom",
    "three bedroom": "3-bedroom",
}

GIBBERISH_REGEX_1 = re.compile(r"[a-zA-Z]{4,}\d+|\d+[a-zA-Z]{4,}")
GIBBERISH_REGEX_2 = re.compile(
    r"(asdf|qwerty|zxcv|ghjkl|1234|qwer|dfgh|hjkl|aaaa|zzzz|xxxx)"
)

WORKPLACE_REGEX = re.compile(
    r"(?:work at|workplace is at|workplace is|my workplace is|office is at|office in|near|close to|job at|workplace in)\s+([a-zA-Z0-9\s]+?)(?:,|\.|$|find|with|under)",
    re.IGNORECASE,
)

MAX_COMMUTE_REGEX = re.compile(
    r"(?:under|less than|within|max|below)\s*(\d+)\s*(?:min|mins|minute|minutes)",
    re.IGNORECASE,
)


def normalize_input(text: str) -> str:
    return re.sub(r"(\d+)\s*([a-zA-Z]+)", r"\1 \2", text, flags=re.IGNORECASE)


def has_gibberish_or_nonsense(doc: spacy.tokens.Doc) -> bool:
    vowels = set("aeiouyAEIOUY")
    for token in doc:
        if not token.is_alpha:
            if GIBBERISH_REGEX_1.search(token.text):
                return True
            continue

        text = token.text.lower()
        if len(text) > 5 and not any(c in vowels for c in text):
            return True
        if GIBBERISH_REGEX_2.search(text) or re.search(r"(.)\1{2,}", text):
            return True
    return False


def _apply_unit(value: float, unit: str | None) -> float:
    if unit in ("k", "thousand", "thousands"):
        return value * 1_000
    if unit in ("m", "million", "millions"):
        return value * 1_000_000
    if unit in ("b", "billion", "billions"):
        return value * 1_000_000_000
    return value


def parse_budget(text: str) -> float | None:
    text_clean = text.lower().replace(",", "")

    match_b = re.search(r"(\d+(?:\.\d+)?)\s*(?:b|billion|billions)", text_clean)
    if match_b:
        return float(match_b.group(1)) * 1_000_000_000

    match_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|million|millions)", text_clean)
    if match_m:
        return float(match_m.group(1)) * 1_000_000

    match_k = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|thousand|thousands)", text_clean)
    if match_k:
        return float(match_k.group(1)) * 1_000

    match_raw = re.findall(r"\b\d{5,10}\b", text_clean)
    return float(match_raw[0]) if match_raw else None


def parse_downpayment_budget(text: str) -> float | None:
    """Matches '500k downpayment', '500k for downpayment', 'downpayment of 500k', etc."""
    text_clean = text.lower().replace(",", "")

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(k|thousand|thousands|m|million|millions|b|billion|billions)?\s*(?:downpayment|down payment|dp)\b",
        text_clean,
    )
    if match:
        return _apply_unit(float(match.group(1)), match.group(2))

    match2 = re.search(
        r"(?:downpayment|down payment|dp)(?:\s+of|\s+is)?\s+(\d+(?:\.\d+)?)\s*(k|thousand|thousands|m|million|millions|b|billion|billions)?",
        text_clean,
    )
    if match2:
        return _apply_unit(float(match2.group(1)), match2.group(2))

    return None


def parse_monthly_budget(text: str) -> float | None:
    """Matches '4k per month', '4k monthly', '4k a month', etc."""
    text_clean = text.lower().replace(",", "")

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(k|thousand|thousands|m|million|millions)?\s*(?:per month|a month|monthly|/month|each month)",
        text_clean,
    )
    if match:
        return _apply_unit(float(match.group(1)), match.group(2))

    return None


def parse_max_commute_time(text: str) -> int | None:
    match = MAX_COMMUTE_REGEX.search(text)
    return int(match.group(1)) if match else None


def is_downpayment_mention(text: str) -> bool:
    text_lower = text.lower()
    return any(k in text_lower for k in DOWNPAYMENT_KEYWORDS)


def is_valid_location_candidate(candidate: str) -> bool:
    """Reject regex captures that are generic phrases rather than real place names,
    e.g. 'in my work site location' should not be sent to the geocoder."""
    words = candidate.lower().split()
    if not words:
        return False
    if any(w in GENERIC_LOCATION_WORDS for w in words):
        return False
    if len(words) > 5:
        return False
    return True


def extract_layout_type(text: str) -> str | None:
    """Detects an interior/layout preference (studio, loft, penthouse, etc.)
    so it can be matched against the DB's free-text layout_type column."""
    text_lower = text.lower()
    for phrase, normalized in LAYOUT_KEYWORDS.items():
        if phrase in text_lower:
            return normalized
    return None


def extract_preferences(text: str, doc: spacy.tokens.Doc) -> dict:
    text_lower = text.lower()

    category = None
    if any(k in text_lower for k in HOUSE_KEYWORDS):
        category = "house"
    elif any(k in text_lower for k in CONDO_KEYWORDS):
        category = "condo"

    locations = [
        ent.text
        for ent in doc.ents
        if ent.label_ in ("GPE", "FAC", "LOC", "ORG")
    ]

    downpayment_budget = parse_downpayment_budget(text)
    monthly_budget = parse_monthly_budget(text)

    # Only fall back to the generic single-number parser when neither a
    # downpayment-specific nor monthly-specific amount was found, so we
    # don't double-count the same number as both "budget" and "downpayment".
    general_budget = None
    if not downpayment_budget and not monthly_budget:
        general_budget = parse_budget(text)

    return {
        "budget": general_budget,
        "downpayment_budget": downpayment_budget,
        "monthly_budget": monthly_budget,
        "is_downpayment": is_downpayment_mention(text),
        "category": category,
        "layout_type": extract_layout_type(text),
        "locations": locations,
        "has_subdivision": "subdivision" in text_lower or "village" in text_lower,
        "wants_near_office": any(k in text_lower for k in WORKPLACE_KEYWORDS),
    }