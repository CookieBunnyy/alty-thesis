import re

# Only text -> value extraction lives here (money, minutes, place names).
# Deciding WHAT to recommend is done by ml/recommender.py.

GENERIC_LOCATION_WORDS = {
    "location", "area", "place", "site", "office", "work",
    "workplace", "job", "here", "there", "commute", "property",
    "me", "my", "it", "budget", "total", "month", "mins", "minutes",
}

_STOP = r"(?:,|\.|$|\b(?:and|but|find|with|under)\b)"

WORKPLACE_REGEX = re.compile(
    r"(?:"
    r"work(?:ing)?\s+(?:at|in)\b"
    r"|(?:my\s+)?workplace\s+is\s+at\b"
    r"|(?:my\s+)?workplace\s+is\s+in\b"
    r"|(?:my\s+)?workplace\s+is\b"
    r"|(?:my\s+)?workplace\s+(?:at|in)\b"
    r"|office\s+is\s+at\b"
    r"|office\s+is\s+in\b"
    r"|office\s+(?:at|in)\b"
    r"|based\s+(?:at|in)\b"
    r"|job\s+at\b"
    r")\s+([a-zA-Z0-9\s]+?)" + _STOP,
    re.IGNORECASE,
)

# Where the visitor wants the PROPERTY ("near Makati", "close to BGC", "in
# Pasig"): a location preference used for ranking, never a workplace. Checked
# only when WORKPLACE_REGEX did not match, so "I work in Makati" stays a workplace.
AREA_REGEX = re.compile(
    r"\b(?:near|nearby|close\s+to|around|in|at)\s+(?:the\s+)?([a-zA-Z][a-zA-Z0-9\s]*?)" + _STOP,
    re.IGNORECASE,
)

MAX_COMMUTE_REGEX = re.compile(
    r"(?:under|less than|within|max|below)\s*(\d+)\s*(?:min|mins|minute|minutes)",
    re.IGNORECASE,
)

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(?:\s*(k|thousands?|m|millions?|b|billions?)\b)?"

_MULTIPLIERS = {
    "k": 1_000, "thousand": 1_000, "thousands": 1_000,
    "m": 1_000_000, "million": 1_000_000, "millions": 1_000_000,
    "b": 1_000_000_000, "billion": 1_000_000_000, "billions": 1_000_000_000,
}

DOWNPAYMENT_RE_1 = re.compile(
    rf"\b{_NUM}{_UNIT}\s*(?:for\s+)?(?:downpayment|down payment|dp)\b"
)
DOWNPAYMENT_RE_2 = re.compile(
    rf"\b(?:downpayment|down payment|dp)(?:\s+of|\s+is)?\s+{_NUM}{_UNIT}"
)
MONTHLY_RE = re.compile(
    rf"\b{_NUM}{_UNIT}\s*(?:per month|a month|monthly|/month|each month)"
)
BUDGET_RE = re.compile(rf"\b{_NUM}\s*(k|thousands?|m|millions?|b|billions?)\b")
DOWNPAYMENT_WORD_RE = re.compile(r"\b(?:downpayment|down payment|dp)\b")


def normalize_input(text: str) -> str:
    return re.sub(r"(\d+)\s*([a-zA-Z]+)", r"\1 \2", text, flags=re.IGNORECASE)


def _apply_unit(value: float, unit: str | None) -> float:
    return value * _MULTIPLIERS.get(unit, 1)


def parse_budget(text: str) -> float | None:
    text_clean = text.lower().replace(",", "")
    match = BUDGET_RE.search(text_clean)
    if match:
        return _apply_unit(float(match.group(1)), match.group(2))
    raw = re.findall(r"\b\d{5,10}\b", text_clean)
    return float(raw[0]) if raw else None


def parse_downpayment_budget(text: str) -> float | None:
    text_clean = text.lower().replace(",", "")
    for pattern in (DOWNPAYMENT_RE_1, DOWNPAYMENT_RE_2):
        match = pattern.search(text_clean)
        if match:
            return _apply_unit(float(match.group(1)), match.group(2))
    return None


def parse_monthly_budget(text: str) -> float | None:
    text_clean = text.lower().replace(",", "")
    match = MONTHLY_RE.search(text_clean)
    if match:
        return _apply_unit(float(match.group(1)), match.group(2))
    return None


def parse_max_commute_time(text: str) -> int | None:
    match = MAX_COMMUTE_REGEX.search(text)
    return int(match.group(1)) if match else None


def is_downpayment_mention(text: str) -> bool:
    return bool(DOWNPAYMENT_WORD_RE.search(text.lower()))


def is_valid_location_candidate(candidate: str) -> bool:
    words = candidate.lower().split()
    if not words:
        return False
    if any(w in GENERIC_LOCATION_WORDS for w in words):
        return False
    if len(words) > 5:
        return False
    return True


def extract_preferences(text: str) -> dict:
    """Numbers only. Category / layout / area are handled by the ML recommender."""
    downpayment_budget = parse_downpayment_budget(text)
    monthly_budget = parse_monthly_budget(text)

    general_budget = None
    if not downpayment_budget and not monthly_budget:
        general_budget = parse_budget(text)

    return {
        "budget": general_budget,
        "downpayment_budget": downpayment_budget,
        "monthly_budget": monthly_budget,
        "is_downpayment": is_downpayment_mention(text),
    }

_AREA_SKIP_FIRST = {"a", "an", "my", "your", "our", "this", "that", "the", "least", "most", "front", "terms"}


def is_valid_area_candidate(candidate: str) -> bool:
    """A short place name ("Makati", "BGC Taguig"), not a phrase like "a gated village"."""
    words = candidate.lower().split()
    return (
        is_valid_location_candidate(candidate)
        and len(words) <= 3
        and words[0] not in _AREA_SKIP_FIRST
    )
