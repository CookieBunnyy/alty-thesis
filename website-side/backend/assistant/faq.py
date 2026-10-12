"""Frequently asked questions about ALTY and buying through Abellar Realty.

Answers describe only what the website and Abellar Realty's process actually
do. Questions about the listings themselves ("how many condos are there?",
"what is the price range?") are answered from the current listings.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from .criteria import CATEGORIES, category_key, clean
from .search import lot_sqm, peso

# A message that asks to SEE properties is a search, even if it also matches a
# question below ("which houses have a lot boundary?").
SEARCH_CUES = re.compile(
    r"\b(?:i want|i need|i'?m looking|looking for|look for|find|show|search|recommend|suggest|any |are there|"
    r"is there|do you have|which (?:properties|ones?|houses?|condos?|units?|listings?)|list (?:of|the|all)|"
    r"give me|help me find|budget|under \d|below \d|within \d|\d+ ?(?:bed|bath|sqm|br\b))"
)
QUESTION = re.compile(r"\?|^(?:what|how|why|when|where|who|can|could|do|does|is|are|will|should|may)\b")


@dataclass
class Faq:
    key: str
    patterns: list[str]
    answer: Callable[[list[dict]], str] | str
    # Answer even when the message also reads like a search (greetings, thanks).
    always: bool = False

    def matches(self, text: str) -> bool:
        return any(re.search(p, text) for p in self.patterns)


def _inventory(rows: list[dict]) -> str:
    if not rows:
        return "There are no available listings right now. Please check again soon, new properties are added regularly."
    counts = Counter(CATEGORIES.get(category_key(r.get("category")) or "", ("Other",))[0] for r in rows)
    parts = ", ".join(f"{n} {label}" for label, n in counts.most_common())
    return (f"Right now there are {len(rows)} available properties: {parts}. "
            "Tell me what you're looking for (type, budget, bedrooms, lot size, or where you work) and I'll pick the best matches.")


def _price_range(rows: list[dict]) -> str:
    prices = sorted(p for r in rows if (p := r.get("price_total")))
    if not prices:
        return "I don't have prices for the current listings yet."
    lines = [f"Available properties range from {peso(prices[0])} to {peso(prices[-1])}."]
    by_type: dict[str, list[float]] = {}
    for r in rows:
        if r.get("price_total"):
            label = CATEGORIES.get(category_key(r.get("category")) or "", ("Other",))[0]
            by_type.setdefault(label, []).append(float(r["price_total"]))
    if len(by_type) > 1:
        lines.append(" ".join(f"{label}: {peso(min(v))}–{peso(max(v))}." if len(v) > 1 else f"{label}: {peso(v[0])}."
                              for label, v in sorted(by_type.items())))
    monthly = [m for r in rows if (m := r.get("monthly_rate"))]
    if monthly:
        lines.append(f"Monthly payments start at {peso(min(monthly))}.")
    return " ".join(lines)


def _locations(rows: list[dict]) -> str:
    places = Counter(str(r.get("village_name")).split(",")[-1].strip() or str(r.get("village_name"))
                     for r in rows if r.get("village_name"))
    if not places:
        return "The listings are on the Property Map; open it to see where each one is."
    top = ", ".join(name for name, _ in places.most_common(8))
    return (f"Our available properties are in {top}. Open the Property Map to see them all, "
            "or tell me a city or your workplace and I'll show the closest ones.")


def _boundary(rows: list[dict]) -> str:
    drawn = sum(1 for r in rows if r.get("boundary"))
    return ("A lot boundary is the outline of the property's lot, drawn by Abellar Realty on a satellite map. "
            "It shows the lot's shape, approximate area and the length of each side. On the Property Map, select a "
            "property and choose \"View lot on satellite\" to see it. The measurements are estimates from the map, "
            "not a land survey, so ask the agent for the official survey or title for exact figures. "
            + (f"{drawn} available {'property has' if drawn == 1 else 'properties have'} a drawn boundary; "
               "ask me \"show properties with a lot boundary\" to see them." if drawn else
               "No available property has a drawn boundary yet."))


def _lot_area(rows: list[dict]) -> str:
    areas = sorted(a for r in rows if (a := lot_sqm(r)))
    tail = (f" Available lots range from {areas[0]:,.0f} to {areas[-1]:,.0f} sqm." if areas else "")
    return ("Lot area is the size of the land, in square meters (sqm); large lots are shown in hectares "
            "(1 hectare = 10,000 sqm). Every property card shows it, and properties with a drawn boundary also show "
            "the measured area." + tail + " Try \"house and lot with at least 200 sqm\".")


FAQS: list[Faq] = [
    Faq("greeting", [r"^(?:hi|hello|hey|good (?:morning|afternoon|evening|day)|kumusta|musta|yo|hola)\b[!. ]*$"],
        "Hi! I'm MIA, your Marketing Intelligence Assistant. I can find properties by budget, down payment, monthly "
        "payment, bedrooms, bathrooms, lot size, amenities, nearby schools or malls, and travel time to your work. "
        "What are you looking for?", always=True),
    Faq("thanks", [r"^(?:thanks?|thank you|ty|salamat|thx)(?: (?:so much|a lot|po|mia))*[!. ]*$"],
        "You're welcome! Ask me anytime if you want to see more properties.", always=True),
    Faq("who", [r"\bwho are you\b", r"\bwhat(?:'s| is) your name\b", r"\bwhat is mia\b", r"\bwhat does mia\b",
                r"\bare you (?:a )?(?:bot|robot|human|real)\b"],
        "I'm MIA, the Marketing Intelligence Assistant of Abellar Realty. I'm a chatbot that reads the current "
        "listings and recommends the ones that fit you. For viewings, reservations and documents, an Abellar agent "
        "will help you."),
    Faq("help", [r"\bwhat can you do\b", r"\bhow (?:do|can) (?:i )?use (?:you|this|mia)\b", r"^help\b", r"\bwhat (?:can|should) i ask\b"],
        "You can tell me things like: \"3-bedroom house and lot under 5M\", \"condo with a pool near a mall\", "
        "\"lot of at least 200 sqm with a lot boundary\", \"down payment of 300k and 15k monthly\", or "
        "\"I work at BGC, within 30 minutes\". You can keep refining: \"how about with 2 bathrooms?\". "
        "Say \"start over\" to begin a new search."),
    Faq("reserve", [r"\bhow (?:do|can|to) (?:i )?(?:reserve|buy|purchase|avail|get)\b", r"\breservation process\b",
                    r"\bprocess (?:of|to|for) (?:buying|reserving|purchasing)\b", r"\bhow does (?:buying|reserving|reservation) work\b",
                    r"\bsteps? (?:to|for) (?:buy|reserve|purchase)\b", r"\bpaano (?:mag|bumili|mag-?reserve)"],
        "To reserve or buy: open the property and choose \"Reserve / Purchase\". You'll see the Abellar agents near "
        "that property; call or text one and mention the property code. Your agent prepares the reservation or "
        "purchase documents with you and submits them to Abellar Realty, which records the transaction. Signing in "
        "with a client account lets you follow your recorded transactions and rate your agent afterwards."),
    Faq("reservation_fee", [r"\breservation fee\b", r"\bhow much (?:is|to) (?:the )?reserv", r"\bmagkano (?:ang )?reserv"],
        "The reservation fee is agreed with your agent for the specific property. It isn't an extra cost: it is "
        "deducted from your down payment. After reserving, the remaining down payment is usually due about a month "
        "later, and the monthly payments start the month after that."),
    Faq("payment_terms", [r"\bwhat is (?:a |the )?(?:down ?payment|dp|monthly (?:rate|amortization))\b",
                          r"\bhow (?:is|are) (?:the )?(?:monthly|down ?payment|dp|payments?) (?:computed|calculated|work)",
                          r"\bpayment (?:terms|scheme|plan|schedule)\b", r"\binstall?ment\b", r"\bamortization\b",
                          r"\bspot cash\b|\bcash (?:payment|basis)\b"],
        "Each listing shows three amounts: the total price, the down payment, and the monthly rate. The down payment "
        "(minus your reservation fee) is paid first, then the rest of the price is paid in monthly payments of the "
        "listed rate. For example, ask me \"300k down payment and 15k monthly\" and I'll find properties within "
        "both. Your agent can confirm cash or other payment options for a specific property."),
    Faq("financing", [r"\bpag-?ibig\b", r"\bbank (?:loan|financing)\b", r"\bin-?house financing\b", r"\bhousing loan\b",
                      r"\bloan\b", r"\bfinancing\b"],
        "Financing (bank loan, Pag-IBIG or in-house terms) depends on the property and the developer, so your agent "
        "will confirm what's available and help with the application. Meanwhile, I can find properties whose down "
        "payment and monthly rate fit your budget: just tell me the amounts."),
    Faq("requirements", [r"\brequirements?\b", r"\bdocuments? (?:needed|required|to bring|do i need)\b",
                         r"\bwhat (?:do i|should i) (?:need|bring|prepare)\b"],
        "Your agent will tell you exactly what's needed for the property you choose; commonly that's valid IDs and "
        "proof of income, plus the reservation documents your agent prepares with you. Choose \"Reserve / Purchase\" "
        "on a property to contact an agent near it."),
    Faq("contact", [r"\bcontact (?:an? |the )?(?:agent|broker|you|abellar|someone)\b", r"\btalk to (?:an? |the )?(?:agent|person|human|someone)\b",
                    r"\bphone number\b", r"\bhow (?:can|do) i (?:reach|call|contact)\b", r"\bagent near\b"],
        "Open any property and choose \"Reserve / Purchase\" to see the Abellar agents nearest to it, with their "
        "contact numbers. You'll be asked to sign in first so the agent knows who you are."),
    Faq("viewing", [r"\b(?:site )?(?:visit|viewing|tripping|tour|inspection|ocular)\b", r"\bsee the (?:house|property|unit) (?:in person|personally)\b"],
        "Site visits are arranged with an Abellar agent. Open the property, choose \"Reserve / Purchase\", and call "
        "or text an agent near it to set a schedule."),
    Faq("account", [r"\b(?:sign ?up|register|create (?:an )?account|log ?in|sign ?in)\b", r"\bdo i need (?:an )?account\b"],
        "You can browse, use the map and chat with me without an account. A free client account (Sign Up at the top) "
        "is needed to contact agents about reserving, to follow your recorded transactions, and to rate your agent."),
    Faq("commute", [r"\bhow (?:do you|is the|is) (?:compute|calculate)?.*(?:travel|commute) time\b",
                    r"\bset (?:my )?workplace\b", r"\bhow (?:does|do) (?:the )?(?:commute|travel time|workplace)\b",
                    r"\btravel time\b(?!.*\b(?:under|within|less)\b)"],
        "Set your workplace with \"Set Workplace\" on the Property Map (search a place, use your location, or pick it "
        "on the map), or just tell me \"I work at Makati\". I then show the road distance and travel time by car, "
        "motorcycle, bike or walking for each property, and the map only shows properties within your chosen radius. "
        "You can also say \"within 30 minutes of my work\"."),
    Faq("nearby", [r"\bnearby establishments?\b", r"\bwhat(?:'s| is) near\b", r"\bnear(?:by)? (?:places|amenities)\b"],
        "Select a property on the Property Map to see its nearby schools, hospitals, malls, markets, parks and "
        "transport stops with their distances. You can also ask me \"house near a school\" or \"condo within 1 km "
        "of a mall\"."),
    Faq("boundary", [r"\bwhat(?:'s| is| are) (?:a |the )?lot boundar", r"\bmeaning of (?:the )?lot boundar",
                     r"\bhow (?:do i|can i|to) (?:see|view|check) (?:the )?(?:lot )?boundar", r"\bboundar(?:y|ies) mean\b",
                     r"\bexplain (?:the )?(?:lot )?boundar"], _boundary),
    Faq("lot_area", [r"\bwhat(?:'s| is) (?:a |the )?(?:lot area|sqm|floor area)\b", r"\bhow big is a hectare\b",
                     r"\bsqm mean", r"\bwhat is a hectare\b"], _lot_area),
    Faq("inventory", [r"\bhow many (?:properties|listings|houses|units|condos)\b", r"\bwhat (?:kinds?|types?) of (?:properties|houses|homes)\b",
                      r"\bwhat (?:properties|listings) (?:do you have|are available)\b", r"\bproperty types\b"], _inventory, always=True),
    Faq("price_range", [r"\bprice range\b", r"\bhow much (?:are|is) (?:the |your )?(?:properties|houses|condos|units|listings)\b",
                        r"\bcheapest (?:price|you have)\b", r"\bstarting price\b", r"\bmagkano\b"], _price_range, always=True),
    Faq("locations", [r"\bwhere are (?:the |your )?(?:properties|listings|houses)\b", r"\bwhat (?:areas|cities|locations|places)\b",
                      r"\bwhich (?:areas|cities|locations)\b"], _locations, always=True),
    Faq("status", [r"\bwhat does (?:reserved|sold|available) mean\b", r"\bis (?:it|this) (?:still )?available\b"],
        "\"Available\" properties can be reserved now. \"Reserved\" means another buyer has reserved it; it may become "
        "available again if that reservation is cancelled. \"Sold\" properties are no longer for sale. I only "
        "recommend available ones."),
]


def answer(message: str, rows: list[dict]) -> tuple[str, str] | None:
    """(intent, reply) when the message is a question MIA answers directly;
    None when it should be treated as a property search."""
    text = clean(message)
    is_search = bool(SEARCH_CUES.search(text))
    for faq in FAQS:
        if faq.matches(text) and (faq.always or not is_search):
            reply = faq.answer(rows) if callable(faq.answer) else faq.answer
            return faq.key, reply
    return None
