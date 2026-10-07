from contextlib import asynccontextmanager

import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
from services.geocoding import calculate_osrm_commute, distance_km, geocode_location
from services.place_names import place_entities, warm_up as warm_up_place_names
from services.property_service import format_listing_row

# Minimum TF-IDF similarity for a message to count as a property request.
# Tune it on your real data: print the max similarity for a few valid queries
# and a few gibberish ones, then pick a value between the two groups.
DOMAIN_THRESHOLD = 0.1


recommender = PropertyRecommender()


def load_recommender():
    response = supabase.table("listings").select("*").execute()
    rows = [
        format_listing_row(row)
        for row in (response.data or [])
        if str(row.get("status") or "AVAILABLE").upper() == "AVAILABLE"
    ]
    recommender.fit(rows)


@asynccontextmanager
async def lifespan(app: FastAPI):
    warm_up_place_names()  # spaCy loads in the background; startup does not wait
    load_recommender()
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
    """Call this after listings change in Supabase to refit the model."""
    load_recommender()
    return {"listings": len(recommender.rows)}


@app.post("/chat")
async def chat_assistant(prompt: UserPrompt):
    raw_message = prompt.message.strip()

    if len(raw_message) < 3:
        return {
            "status": "rejected",
            "reply": "Please enter a valid message regarding your property preferences.",
            "recommendations": [],
        }

    normalized_message = normalize_input(raw_message)
    preferences = extract_preferences(normalized_message)
    has_money = bool(
        preferences["budget"]
        or preferences["downpayment_budget"]
        or preferences["monthly_budget"]
    )

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
        if not (candidate and is_valid_area_candidate(candidate)):
            # No "near / in X" cue: use a place name spaCy recognised,
            # e.g. "condo Ayala Alabang under 5M".
            named = [p["text"] for p in places if is_valid_area_candidate(p["text"])]
            candidate = named[0] if named else ""
        if candidate and is_valid_area_candidate(candidate):
            area_name = candidate
            area_point = geocode_location(candidate)

    max_commute_mins = parse_max_commute_time(normalized_message)

    # ---- is this a property request? (replaces the gibberish + no-criteria rules) ----
    in_domain = recommender.is_in_domain(normalized_message, DOMAIN_THRESHOLD)
    if not (in_domain or has_money or work_name or area_name or unlocated_workplace):
        return {
            "status": "casual_chat",
            "reply": "Hello! I am your real estate assistant. Tell me your budget, the kind of property you want, or your workplace (e.g., 'I work at BGC Taguig').",
            "recommendations": [],
        }

    # ---- rank all listings with scikit-learn ----
    candidates = recommender.rank(
        normalized_message,
        budget=preferences["budget"],
        monthly=preferences["monthly_budget"],
        downpayment=preferences["downpayment_budget"],
        is_downpayment=preferences["is_downpayment"],
        top_n=20,
    )

    # ---- commute only for the top candidates ----
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

    candidates.sort(key=lambda c: -c["final"])
    results = [c["item"] for c in candidates[:3]]

    if not results:
        return {
            "status": "no_match",
            "reply": "No available listings found matching your specifications.",
            "preferences_detected": preferences,
            "detected_workplace": detected_workplace,
            "recommendations": [],
        }

    # ---- reply message ----
    parts = []
    if preferences["downpayment_budget"] and preferences["monthly_budget"]:
        parts.append(
            f"a downpayment of ₱{preferences['downpayment_budget']:,.2f} and ₱{preferences['monthly_budget']:,.2f} monthly"
        )
    elif preferences["downpayment_budget"]:
        parts.append(f"a downpayment of ₱{preferences['downpayment_budget']:,.2f}")
    elif preferences["monthly_budget"]:
        parts.append(f"a monthly budget of ₱{preferences['monthly_budget']:,.2f}")
    elif preferences["budget"]:
        parts.append(f"a budget of ₱{preferences['budget']:,.2f}")

    criteria_text = " with ".join(parts)

    if work_name and max_commute_mins:
        reply_msg = (
            f"Based on {criteria_text}, " if criteria_text else ""
        ) + f"I found {len(results)} properties within {max_commute_mins} mins commute to {work_name}."
    elif work_name:
        reply_msg = (
            f"You mentioned wanting {criteria_text} near {work_name} — "
            if criteria_text
            else f"I calculated travel routes to {work_name} — "
        ) + f"here's '{results[0]['title']}', ranked by best match and commute."
    elif area_name:
        reply_msg = (
            f"Here are available properties near {area_name.title()}"
            + (f" for {criteria_text}" if criteria_text else "")
            + f" — the best match is '{results[0]['title']}'."
        )
    elif criteria_text:
        reply_msg = f"You mentioned wanting {criteria_text} — here's '{results[0]['title']}'."
    else:
        reply_msg = f"Here are the top {len(results)} listings matching your search."

    if unlocated_workplace:
        reply_msg += (
            f" (I couldn't find '{unlocated_workplace}' on the map, so commute times aren't included — "
            "you can set your workplace with the Set Workplace button.)"
        )

    return {
        "status": "recommendation_found",
        "reply": reply_msg,
        "preferences_detected": preferences,
        "detected_workplace": detected_workplace,
        "recommendations": results,
    }