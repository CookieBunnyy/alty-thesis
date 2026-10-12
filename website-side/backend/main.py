import time
from contextlib import asynccontextmanager

import numpy as np
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from assistant import criteria as crit
from assistant.faq import answer as faq_answer
from assistant.search import filter_rows, nearby_bonus, peso, sort_key, why
from config import supabase
from keywords import (
    AREA_REGEX,
    WORKPLACE_REGEX,
    extract_preferences,
    is_valid_area_candidate,
    is_valid_location_candidate,
    normalize_input,
    parse_max_commute_time,
)
from ml.recommender import PropertyRecommender
from schemas import UserPrompt
from services.geocoding import MAIN_API_URL, calculate_osrm_commute, distance_km, geocode_location
from services.place_names import place_entities, warm_up as warm_up_place_names
from services.property_service import format_listing_row

# Minimum TF-IDF similarity for a message to count as a property request.
# Tune it on your real data: print the max similarity for a few valid queries
# and a few gibberish ones, then pick a value between the two groups.
DOMAIN_THRESHOLD = 0.1
# Listings are re-read at most this often, so new listings, lot areas and
# drawn boundaries reach MIA without a restart.
REFRESH_SECONDS = 300

recommender = PropertyRecommender()
_loaded_at = 0.0


def _fetch_listings() -> list[dict]:
    """Available listings, from the main ALTY API (the same data as the website,
    with lot areas, boundaries and uploaded photos); Supabase if it can't be reached."""
    if MAIN_API_URL:
        try:
            res = requests.get(f"{MAIN_API_URL}/api/v1/public/properties", params={"status": "AVAILABLE"}, timeout=20)
            if res.status_code == 200 and isinstance(res.json(), list):
                return [format_listing_row(row) for row in res.json()]
        except Exception as exc:  # noqa: BLE001 - fall back to Supabase
            print(f"Main API listings unavailable: {exc}")
    response = supabase.table("listings").select("*").execute()
    return [
        format_listing_row(row)
        for row in (response.data or [])
        if str(row.get("status") or "AVAILABLE").upper() == "AVAILABLE"
    ]


def load_recommender():
    global _loaded_at
    recommender.fit(_fetch_listings())
    _loaded_at = time.monotonic()


def _fresh_listings() -> list[dict]:
    if time.monotonic() - _loaded_at > REFRESH_SECONDS:
        try:
            load_recommender()
        except Exception as exc:  # noqa: BLE001 - keep serving the last good copy
            print(f"Listing refresh failed: {exc}")
    return recommender.rows


@asynccontextmanager
async def lifespan(app: FastAPI):
    warm_up_place_names()  # spaCy loads in the background; startup does not wait
    try:
        load_recommender()
    except Exception as exc:  # noqa: BLE001 - start anyway; the next chat retries
        print(f"Initial listing load failed: {exc}")
    yield


app = FastAPI(
    title="Property Recommendation Assistant", version="2.0.0", lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/properties")
async def get_properties():
    try:
        response = supabase.table("listings").select("*").execute()
        return [
            format_listing_row(row)
            for row in (response.data or [])
            if str(row.get("status") or "AVAILABLE").upper() == "AVAILABLE"
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Unable to load available properties."
        ) from exc


@app.get("/agents")
async def get_active_agents():
    try:
        response = supabase.table("agents").select("agent_id, full_name, status").execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to load agents.") from exc
    return [
        {
            "agent_id": row["agent_id"],
            "full_name": row["full_name"],
            "status": row.get("status"),
        }
        for row in (response.data or [])
        if str(row.get("status") or "").upper() == "ACTIVE"
        and row.get("agent_id")
        and row.get("full_name")
    ]


# Client transactions are submitted to the main Alty API
# (POST /api/v1/public/transactions), which validates the property, matches or
# creates the client, records the transaction and updates the property status.


@app.post("/admin/retrain")
async def retrain():
    """Call this after listings change to refit the model now."""
    load_recommender()
    return {"listings": len(recommender.rows)}


# Words that describe a kind of place, not a named location: "near a school"
# asks for a nearby school, it is not a place to look up on the map.
_PLACE_KIND_WORDS = {w for _label, words in crit.ESTABLISHMENTS.values() for w in words} | {
    w for words in crit.AMENITIES.values() for w in words} | {"a", "an", "the", "some", "good", "big", "nice"}


def _is_place_kind(candidate: str) -> bool:
    words = candidate.lower().split()
    return bool(words) and " ".join(words) in _PLACE_KIND_WORDS or all(w in _PLACE_KIND_WORDS for w in words)


def _reply(status: str, text: str, context: dict | None, **extra) -> dict:
    return {"status": status, "reply": text, "recommendations": [], "context": context, **extra}


def _follow_up(c: crit.Criteria, has_place: bool) -> str | None:
    """One question about the most useful preference still missing."""
    if not (c.max_price or c.min_price or c.max_downpayment or c.max_monthly):
        return "What's your budget? You can give a total price, a down payment, or a monthly amount."
    if not has_place:
        return "Where do you work or want to live? I can check travel times from your workplace."
    if not c.category:
        return "Do you prefer a condo, house and lot, or townhouse?"
    if not c.min_bedrooms and c.category not in {"lot", "commercial", "warehouse"}:
        return "How many bedrooms do you need?"
    return None


@app.post("/chat")
async def chat_assistant(prompt: UserPrompt):
    raw_message = prompt.message.strip()
    previous = crit.Criteria.from_dict(prompt.context)

    if len(raw_message) < 2:
        return _reply("rejected", "Please enter a valid message regarding your property preferences.", prompt.context)

    rows = _fresh_listings()

    if crit.wants_reset(raw_message):
        previous = crit.Criteria()
        rest = crit.clean(raw_message)
        if len(rest.split()) <= 4:
            return _reply("casual_chat", "Okay, let's start over. What kind of property are you looking for, and what's your budget?", None)

    # ---- questions MIA answers directly (how to reserve, what is a lot boundary...) ----
    faq = faq_answer(raw_message, rows)
    if faq:
        return _reply("casual_chat", faq[1], prompt.context, intent=faq[0])

    normalized_message = normalize_input(raw_message)
    wanted, money_text = crit.parse(raw_message)
    preferences = extract_preferences(money_text)
    if preferences["downpayment_budget"]:
        wanted.max_downpayment = preferences["downpayment_budget"]
    if preferences["monthly_budget"]:
        wanted.max_monthly = preferences["monthly_budget"]
    if preferences["budget"] and not (wanted.min_price or wanted.max_price):
        if preferences["is_downpayment"]:
            wanted.max_downpayment = preferences["budget"]
        else:
            wanted.max_price = preferences["budget"]
    wanted.max_commute_mins = wanted.max_commute_mins or parse_max_commute_time(normalized_message)
    has_money = bool(wanted.max_price or wanted.min_price or wanted.max_downpayment or wanted.max_monthly)

    # ---- workplace detection ----
    work_lat, work_lng, work_name = (
        prompt.workplace_lat,
        prompt.workplace_lng,
        prompt.workplace_name,
    )
    detected_workplace = None
    unlocated_workplace = None  # named, but the map lookup failed

    # "I work at X" sets the workplace; "near / in / close to X" is only where
    # the property should be. A failed lookup never stops the search: the
    # scikit-learn ranking still matches the place name against listing text.
    area_name = area_point = None
    # Place names found by spaCy's English model (empty until it has loaded).
    places = place_entities(normalized_message)
    workplace_match = WORKPLACE_REGEX.search(normalized_message)
    if workplace_match:
        candidate = workplace_match.group(1).strip()
        if not is_valid_location_candidate(candidate):
            # "I work at the Accenture office in Makati": keep the place name
            # spaCy found inside the phrase ("Makati").
            inside = [
                p["text"] for p in places
                if p["start"] >= workplace_match.start(1) and p["end"] <= workplace_match.end(1)
                and is_valid_location_candidate(p["text"])
            ]
            candidate = inside[-1] if inside else candidate
        if is_valid_location_candidate(candidate):
            geo = geocode_location(candidate)
            if geo:
                work_lat, work_lng, work_name = geo["lat"], geo["lng"], geo["name"]
                detected_workplace = geo
            else:
                unlocated_workplace = candidate
    else:
        area_match = AREA_REGEX.search(normalized_message)
        candidate = area_match.group(1).strip() if area_match else ""
        if not (candidate and is_valid_area_candidate(candidate)) or _is_place_kind(candidate):
            # No "near / in X" cue: use a place name spaCy recognised,
            # e.g. "condo Ayala Alabang under 5M".
            named = [p["text"] for p in places if is_valid_area_candidate(p["text"]) and not _is_place_kind(p["text"])]
            candidate = named[0] if named else ""
        if candidate and is_valid_area_candidate(candidate) and not _is_place_kind(candidate):
            area_name = candidate
            area_point = geocode_location(candidate)

    # ---- follow-ups refine the last search ("how about with 2 bathrooms?") ----
    names_place = bool(area_name or workplace_match)
    says_something = not wanted.is_empty()  # before merging: gibberish must not re-run the last search
    if not previous.is_empty() and (crit.is_refinement(raw_message)
                                    or (says_something and not wanted.category and not names_place)):
        wanted = previous.merged_with(wanted)
        if previous.max_price and wanted.min_price and not wanted.max_price:
            wanted.max_price = None

    # ---- is this a property request? ----
    in_domain = recommender.is_in_domain(normalized_message, DOMAIN_THRESHOLD)
    if not (in_domain or has_money or work_name or area_name or unlocated_workplace or says_something):
        return _reply(
            "casual_chat",
            "I'm not sure I understood. I'm MIA, and I can help you find a property: tell me your budget, the kind "
            "of property, bedrooms, lot size, amenities, or your workplace (e.g., \"3-bedroom house under 5M near a "
            "school\"). You can also ask me how reserving works.",
            prompt.context,
        )

    if not rows:
        return _reply("no_match", "There are no available listings right now. Please check again soon.", wanted.to_dict())

    # ---- requirements first, then rank what's left ----
    allowed, relaxed = filter_rows(rows, wanted)
    ranked = recommender.rank(
        normalized_message,
        budget=wanted.max_price,
        monthly=wanted.max_monthly,
        downpayment=wanted.max_downpayment,
        top_n=len(rows),
    )
    keep = {id(rows[i]) for i in allowed}
    candidates = [c for c in ranked if id(c["row"]) in keep]
    for c in candidates:
        c["score"] = 0.65 * c["score"] + 0.35 * nearby_bonus(c["row"], wanted) if wanted.near else c["score"]
    order = sort_key(wanted)
    candidates.sort(key=(lambda c: (order(c["row"]), -c["score"])) if order else (lambda c: -c["score"]))
    candidates = candidates[:20]

    # ---- commute only for the top candidates ----
    max_commute_mins = wanted.max_commute_mins
    for c in candidates:
        item = dict(c["row"])  # copy, so cached rows are never mutated
        c["item"] = item
        c["commute"] = None

        if work_lat and work_lng and item.get("lat") and item.get("lng"):
            commute = calculate_osrm_commute(
                item["lat"], item["lng"], work_lat, work_lng
            )
            if commute:
                c["commute"] = commute
                item["commute_info"] = commute

        mins = c["commute"]["duration_mins"] if c["commute"] else None
        c["commute_score"] = 1.0 if mins is None else float(np.exp(-mins / 60))
        if max_commute_mins and mins and mins > max_commute_mins:
            c["commute_score"] *= 0.1  # soft penalty instead of a hard drop

        c["final"] = 0.7 * c["score"] + 0.3 * c["commute_score"]

        # "near Makati": listings closer to the named area rank higher.
        if area_point and item.get("lat") and item.get("lng"):
            km = distance_km(float(item["lat"]), float(item["lng"]), area_point["lat"], area_point["lng"])
            c["final"] = 0.6 * c["final"] + 0.4 * float(np.exp(-km / 5))

    if wanted.sort == "commute_asc":
        candidates.sort(key=lambda c: c["commute"]["duration_mins"] if c["commute"] else float("inf"))
    elif not order:
        candidates.sort(key=lambda c: -c["final"])
    results = [c["item"] for c in candidates[:3]]

    if not results:
        return _reply("no_match", "No available listings match that yet. Try a wider budget or fewer requirements.",
                      wanted.to_dict(), detected_workplace=detected_workplace)

    # ---- reply: what MIA understood, what matched, and one follow-up question ----
    understood = crit.describe(wanted, peso)
    lines = []
    if understood:
        lines.append("Looking for: " + " · ".join(understood) + ".")
    if work_name and not relaxed:
        lines.append(f"I checked travel times to {work_name}.")
    if area_name:
        lines.append(f"Closest to {area_name.title()} first.")
    if relaxed:
        lines.append("No available property has all of that, so I left out: " + ", ".join(relaxed)
                     + ". Here are the closest matches:")
    else:
        total = len(allowed)
        lines.append(f"{total} matching propert{'y' if total == 1 else 'ies'}"
                     + (f", here are the top {len(results)}:" if total > len(results) else ":"))
    for index, item in enumerate(results, 1):
        place = f" ({item.get('village_name')})" if item.get("village_name") else ""
        detail = why(item, wanted)
        lines.append(f"{index}. {item.get('title')}{place}" + (f" — {detail}" if detail else ""))
    if max_commute_mins and work_name:
        over = [i for i in results if (i.get("commute_info") or {}).get("duration_mins", 0) > max_commute_mins]
        if over:
            lines.append(f"Note: {len(over)} of these take longer than {max_commute_mins} min; they were the closest available.")
    if unlocated_workplace:
        lines.append(
            f"(I couldn't find '{unlocated_workplace}' on the map, so commute times aren't included — "
            "you can set your workplace with the Set Workplace button.)"
        )
    question = _follow_up(wanted, bool(work_name or area_name or unlocated_workplace))
    if question:
        lines.append(question)
    lines.append("You can refine this, e.g. \"how about with 2 bathrooms?\", or say \"start over\".")

    return {
        "status": "recommendation_found",
        "reply": "\n".join(lines),
        "preferences_detected": preferences,
        "criteria": wanted.to_dict(),
        "context": wanted.to_dict(),
        "relaxed": relaxed,
        "detected_workplace": detected_workplace,
        "recommendations": results,
    }
