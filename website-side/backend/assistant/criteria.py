"""What a visitor is asking for, read from one chat message.

Everything here is plain text -> structured criteria (no data access), so it
can be tested on its own. ``search.py`` applies the criteria to listings and
``faq.py`` answers questions about how ALTY works.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# ---- vocabulary ------------------------------------------------------------------

# Same standard categories as the website (frontend/src/lib/categories.ts).
CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "condominium": ("Condominium", ["condominium", "condo unit", "condos", "condo", "studio", "loft"]),
    "house-and-lot": ("House and Lot", ["house and lot", "house & lot", "house n lot", "h&l", "single detached",
                                        "single-detached", "bungalow", "villa", "houses", "house"]),
    "townhouse": ("Townhouse", ["townhouses", "townhouse", "town house", "rowhouse", "row house"]),
    "duplex": ("Duplex", ["duplex", "semi-detached", "semi detached"]),
    "apartment": ("Apartment", ["apartments", "apartment", "flat"]),
    "lot": ("Lot Only", ["lot only", "vacant lot", "residential lot", "raw land", "land only", "bare lot"]),
    "commercial": ("Commercial", ["commercial space", "commercial", "office space", "retail space"]),
    "warehouse": ("Warehouse / Industrial", ["warehouse", "industrial"]),
}


def category_key(raw: str | None) -> str | None:
    """The standard category of a listing's stored category text."""
    if not raw:
        return None
    value = " ".join(raw.lower().split())
    for key, (label, aliases) in CATEGORIES.items():
        if value == label.lower() or value in aliases:
            return key
    for key, (_label, aliases) in CATEGORIES.items():
        if any(alias in value for alias in aliases):
            return key
    return "lot" if value == "lot" else None


# Amenity keys as stored in listings (amenity_list), with the words people use.
AMENITIES: dict[str, list[str]] = {
    "pool": ["swimming pool", "pool"],
    "gym": ["gym", "fitness center", "fitness centre", "fitness"],
    "security": ["24/7 security", "security guard", "security", "gated", "guarded", "cctv", "guard"],
    "clubhouse": ["clubhouse", "club house"],
    "playground": ["playground", "play area", "kids area"],
    "function_hall": ["function hall", "event hall", "events hall", "party hall"],
    "helipad": ["helipad"],
    "basketball_court": ["basketball court", "basketball"],
    "garden": ["garden"],
    "jogging_path": ["jogging path", "jogging"],
}
AMENITY_LABELS = {key: key.replace("_", " ") for key in AMENITIES}

# Nearby establishment groups as stored (nearby_establishments), with synonyms.
ESTABLISHMENTS: dict[str, tuple[str, list[str]]] = {
    "schools": ("school", ["schools", "school", "university", "college", "campus", "daycare", "kindergarten"]),
    "hospitals": ("hospital", ["hospitals", "hospital", "clinic", "medical center", "medical"]),
    "malls": ("mall", ["malls", "mall", "shopping center", "shopping", "supermall"]),
    "markets": ("market", ["markets", "market", "palengke", "grocery", "supermarket"]),
    "transit": ("public transport", ["transit", "mrt", "lrt", "train", "bus stop", "bus", "jeep", "jeepney",
                                     "terminal", "station", "public transport", "transportation", "commute"]),
    "parks": ("park", ["parks", "park", "plaza"]),
    "churches": ("church", ["churches", "church", "chapel", "parish"]),
}

FEATURES = {  # boolean listing columns
    "has_balcony": ("balcony", ["balcony", "balconies", "terrace"]),
    "has_kitchen": ("kitchen", ["kitchen"]),
    "has_backyard": ("backyard", ["backyard", "back yard", "yard", "lawn"]),
    "has_garage": ("garage / parking", ["garage", "parking", "carport", "car port", "parking slot", "parking space"]),
}

_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                 "seven": "7", "eight": "8", "nine": "9", "ten": "10", "single": "1", "a couple of": "2"}

# ---- patterns -----------------------------------------------------------------------

_BEDROOMS = re.compile(r"\b(\d{1,2})\s*\+?\s*-?\s*(?:bed(?:room)?s?|br|bdrm?s?|bd|rooms?)\b")
_BATHROOMS = re.compile(r"\b(\d{1,2})\s*\+?\s*-?\s*(?:bath(?:room)?s?|ba|t\s*&\s*bs?|t\s*and\s*bs?|cr'?s?|comfort\s*rooms?|toilets?)\b")
_AREA_UNIT = r"(sq\.?\s*m(?:eters?|etres?)?|sqm|square\s*met(?:er|re)s?|m2|m²|hectares?|ha)\b"
_AREA = re.compile(r"(?:(under|below|less than|at most|max(?:imum)?|up to|not more than|at least|min(?:imum)?|"
                   r"more than|over|above|bigger than|larger than)\s+)?(\d[\d,]*(?:\.\d+)?)\s*" + _AREA_UNIT)
_BIG_LOT = re.compile(r"\b(?:big|bigger|biggest|large|larger|largest|wide|wider|widest|spacious|huge)\s+"
                      r"(?:lot|lots|land|area|space|property|properties|house|houses|home|homes)\b")
_BOUNDARY = re.compile(r"\b(?:lot\s+)?(?:boundar(?:y|ies)|outline|outlined|lot\s+plan|surveyed|survey\s+plan|"
                       r"lot\s+shape|lot\s+map)\b")
_GARAGE_SPACES = re.compile(r"\b(\d)\s*-?\s*(?:car|cars)\s*(?:garage|parking|carport)?\b|"
                            r"\b(?:garage|parking)\s+(?:for|of)\s+(\d)\s*(?:cars?)?\b")
_WALKING = re.compile(r"\bwalk(?:ing|able)?\s*(?:distance)?\b")
_WITHIN_KM = re.compile(r"\bwithin\s+(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?)\b")
_MONEY = r"(\d+(?:\.\d+)?)\s*(k|thousands?|m|million|millions|b|billion)?"
_RANGE = re.compile(rf"\b(?:between\s+)?(?:php|₱|p)?\s*{_MONEY}\s*(?:-|to|and|–)\s*(?:php|₱|p)?\s*{_MONEY}\b")
_MIN_PRICE = re.compile(rf"\b(?:above|over|more than|at least|minimum of|min of|starting at)\s+(?:php|₱|p)?\s*{_MONEY}\b")
_COMMUTE_HOURS = re.compile(r"(?:under|less than|within|max|below|no more than)\s*(?:an?|one|1)\s*(?:hour|hr)\b")
_COMMUTE_MINS = re.compile(r"(?:under|less than|within|max|below|no more than)\s*(\d+)\s*(?:min|mins|minute|minutes)\b")
_RESET = re.compile(r"\b(?:start over|new search|reset|clear (?:my )?(?:search|filters?)|forget (?:that|it))\b")
_REFINE = re.compile(r"^(?:how about|what about|and |also|with |only |just |but |instead|make it|ones? |those|"
                     r"same|cheaper|bigger|smaller|any with|any that)|\b(?:instead|as well|too|those|them|these)\b")

_SORTS: list[tuple[str, re.Pattern]] = [
    ("dp_asc", re.compile(r"\b(?:lowest|smallest|cheapest|low|minimal|zero|no)\s+(?:down\s*payment|downpayment|dp)\b")),
    ("monthly_asc", re.compile(r"\b(?:lowest|smallest|cheapest|low|affordable)\s+(?:monthly|monthly\s+(?:rate|payment|amortization)|amortization)\b")),
    ("price_asc", re.compile(r"\b(?:cheapest|lowest[- ]priced|least expensive|most affordable|lowest price|"
                             r"cheaper|budget[- ]friendly|affordable)\b")),
    ("price_desc", re.compile(r"\b(?:most expensive|priciest|luxury|luxurious|high[- ]end|premium)\b")),
    ("lot_desc", _BIG_LOT),
    ("bedrooms_desc", re.compile(r"\b(?:most|many|lots of|more)\s+(?:bed)?rooms\b")),
    ("commute_asc", re.compile(r"\b(?:closest|nearest|shortest)\s+(?:to\s+(?:my\s+)?(?:work|office|workplace)|commute|travel)\b|"
                               r"\b(?:short|quick|fast)\s+(?:commute|travel)\b")),
]


@dataclass
class Criteria:
    category: str | None = None
    min_bedrooms: int | None = None
    min_bathrooms: int | None = None
    min_lot_sqm: float | None = None
    max_lot_sqm: float | None = None
    needs_boundary: bool = False
    features: list[str] = field(default_factory=list)          # has_* columns
    min_garage_spaces: int | None = None
    amenities: list[str] = field(default_factory=list)         # amenity keys
    near: list[str] = field(default_factory=list)              # establishment groups
    near_max_km: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    max_downpayment: float | None = None
    max_monthly: float | None = None
    max_commute_mins: int | None = None
    sort: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Criteria":
        if not isinstance(data, dict):
            return cls()
        allowed = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def is_empty(self) -> bool:
        return self == Criteria()

    def merged_with(self, newer: "Criteria") -> "Criteria":
        """Earlier answers kept, newer ones win (lists are combined)."""
        merged = Criteria(**self.to_dict())
        for name, value in newer.to_dict().items():
            if isinstance(value, list):
                setattr(merged, name, sorted(set(getattr(merged, name)) | set(value)))
            elif isinstance(value, bool):
                setattr(merged, name, getattr(merged, name) or value)
            elif value is not None:
                setattr(merged, name, value)
        return merged


def _money(value: str, unit: str | None) -> float:
    unit = (unit or "").lower()
    factor = 1_000 if unit.startswith(("k", "thousand")) else 1_000_000 if unit.startswith("m") else \
        1_000_000_000 if unit.startswith("b") else 1
    return float(value) * factor


def clean(text: str) -> str:
    """Lower case, number words as digits, "3bedroom" -> "3 bedroom"."""
    text = " " + text.lower().replace(",", "") + " "
    for word, digit in _NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    text = re.sub(r"(\d)([a-z²])", r"\1 \2", text)
    return " ".join(text.split())


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text) for w in words)


def parse(message: str) -> tuple[Criteria, str]:
    """Criteria found in the message, and the message with the parts that are
    not money removed (so "200 sqm" is never read as a ₱200 budget)."""
    text = clean(message)
    c = Criteria()

    # Category: longest alias first, so "house and lot" beats "house".
    best = None
    for key, (_label, aliases) in CATEGORIES.items():
        for alias in aliases:
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text) and (best is None or len(alias) > best[1]):
                best = (key, len(alias))
    if best:
        c.category = best[0]

    if m := _BEDROOMS.search(text):
        c.min_bedrooms = int(m.group(1))
    if m := _BATHROOMS.search(text):
        c.min_bathrooms = int(m.group(1))

    money_text = text
    for m in _AREA.finditer(text):
        qualifier, value, unit = m.group(1) or "", float(m.group(2)), m.group(3)
        sqm = value * 10_000 if unit.startswith(("hectare", "ha")) else value
        if qualifier in {"under", "below", "less than", "at most", "max", "maximum", "up to", "not more than"}:
            c.max_lot_sqm = sqm
        else:
            c.min_lot_sqm = sqm
        money_text = money_text.replace(m.group(0), " ")
    for pattern in (_BEDROOMS, _BATHROOMS, _GARAGE_SPACES, _WITHIN_KM, _COMMUTE_MINS):
        money_text = pattern.sub(" ", money_text)

    if _BOUNDARY.search(text):
        c.needs_boundary = True

    for column, (_label, words) in FEATURES.items():
        if _has(text, words):
            c.features.append(column)
    if m := _GARAGE_SPACES.search(text):
        c.min_garage_spaces = int(m.group(1) or m.group(2))
        if "has_garage" not in c.features:
            c.features.append("has_garage")

    for key, words in AMENITIES.items():
        if _has(text, words):
            c.amenities.append(key)
    # "pool" inside "car pool" or "gated" as part of a search for "gated village" still count.

    for key, (_label, words) in ESTABLISHMENTS.items():
        # "commute" alone is about travel time, not a transit stop.
        words = [w for w in words if w != "commute"]
        if _has(text, words):
            c.near.append(key)
    if c.near:
        if m := _WITHIN_KM.search(text):
            c.near_max_km = float(m.group(1))
        elif _WALKING.search(text):
            c.near_max_km = 1.0

    m = _RANGE.search(money_text)
    if m and re.match(r"\s*(?:/|a |per |each |monthly|month|mo|down|dp)", money_text[m.end():]):
        m = None  # "15k-20k monthly" is a monthly budget, not a price range
    if m:
        low, high = _money(m.group(1), m.group(2) or m.group(4)), _money(m.group(3), m.group(4))
        if high >= 10_000 and low < high:
            c.min_price, c.max_price = low, high
    elif m := _MIN_PRICE.search(money_text):
        value = _money(m.group(1), m.group(2))
        if value >= 10_000:
            c.min_price = value

    if m := _COMMUTE_MINS.search(text):
        c.max_commute_mins = int(m.group(1))
    elif _COMMUTE_HOURS.search(text):
        c.max_commute_mins = 60

    for name, pattern in _SORTS:
        if pattern.search(text):
            c.sort = name
            break

    c.features.sort()
    c.amenities.sort()
    c.near.sort()
    return c, money_text


def wants_reset(message: str) -> bool:
    return bool(_RESET.search(clean(message)))


def is_refinement(message: str) -> bool:
    """A follow-up that narrows the last search ("how about 3 bedrooms?")."""
    return bool(_REFINE.search(clean(message)))


def describe(c: Criteria, peso) -> list[str]:
    """Short phrases for what MIA understood, in reading order."""
    parts = []
    if c.category:
        parts.append(CATEGORIES[c.category][0])
    if c.min_bedrooms:
        parts.append(f"{c.min_bedrooms}+ bedroom{'s' if c.min_bedrooms > 1 else ''}")
    if c.min_bathrooms:
        parts.append(f"{c.min_bathrooms}+ bathroom{'s' if c.min_bathrooms > 1 else ''}")
    if c.min_lot_sqm and c.max_lot_sqm:
        parts.append(f"lot {c.min_lot_sqm:,.0f}–{c.max_lot_sqm:,.0f} sqm")
    elif c.min_lot_sqm:
        parts.append(f"lot of at least {c.min_lot_sqm:,.0f} sqm")
    elif c.max_lot_sqm:
        parts.append(f"lot up to {c.max_lot_sqm:,.0f} sqm")
    if c.needs_boundary:
        parts.append("a drawn lot boundary")
    for column in c.features:
        label = FEATURES[column][0]
        if column == "has_garage" and c.min_garage_spaces:
            label = f"parking for {c.min_garage_spaces}+ car{'s' if c.min_garage_spaces > 1 else ''}"
        parts.append(label)
    parts += [AMENITY_LABELS[a] for a in c.amenities]
    if c.near:
        names = [ESTABLISHMENTS[n][0] for n in c.near]
        distance = f" within {c.near_max_km:g} km" if c.near_max_km else ""
        parts.append(f"near a {' and a '.join(names)}{distance}")
    if c.min_price and c.max_price:
        parts.append(f"{peso(c.min_price)}–{peso(c.max_price)}")
    elif c.min_price:
        parts.append(f"from {peso(c.min_price)}")
    elif c.max_price:
        parts.append(f"up to {peso(c.max_price)}")
    if c.max_downpayment:
        parts.append(f"down payment up to {peso(c.max_downpayment)}")
    if c.max_monthly:
        parts.append(f"up to {peso(c.max_monthly)} a month")
    if c.max_commute_mins:
        parts.append(f"within {c.max_commute_mins} min of your workplace")
    return parts
