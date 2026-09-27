from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import nlp, supabase
from keywords import (
    WORKPLACE_REGEX,
    extract_preferences,
    has_gibberish_or_nonsense,
    is_valid_location_candidate,
    normalize_input,
    parse_max_commute_time,
)
from schemas import UserPrompt
from services.geocoding import calculate_osrm_commute, geocode_location
from services.property_service import format_listing_row

app = FastAPI(title="Property Recommendation Assistant", version="1.0.0")

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
        return [format_listing_row(row) for row in (response.data or [])]
    except Exception as e:
        return {"error": str(e)}


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
    doc = nlp(normalized_message)

    if has_gibberish_or_nonsense(doc):
        return {
            "status": "rejected",
            "reply": "I could not understand your request because it contains unrecognized or invalid words.",
            "recommendations": [],
        }

    preferences = extract_preferences(normalized_message, doc)

    work_lat, work_lng, work_name = (
        prompt.workplace_lat,
        prompt.workplace_lng,
        prompt.workplace_name,
    )
    detected_workplace = None
    geocode_failed = False

    # Detect location phrases
    workplace_match = WORKPLACE_REGEX.search(normalized_message)
    if workplace_match:
        candidate = workplace_match.group(1).strip()
        if is_valid_location_candidate(candidate):
            geo = geocode_location(candidate)
            if geo:
                work_lat, work_lng, work_name = geo["lat"], geo["lng"], geo["name"]
                detected_workplace = geo
            else:
                geocode_failed = True
        # else: generic phrase like "my work site location" was captured —
        # not a real place name, so we skip geocoding it and fall back to
        # whatever workplace_lat/lng the frontend already had set.

    max_commute_mins = parse_max_commute_time(normalized_message)

    if geocode_failed and not preferences["budget"] and not preferences["category"]:
        return {
            "status": "rejected",
            "reply": "I couldn't locate that workplace address. Could you try a more specific name (e.g., 'BGC Taguig' or 'Makati CBD')?",
            "recommendations": [],
        }

    has_any_criteria = (
        preferences["budget"]
        or preferences["downpayment_budget"]
        or preferences["monthly_budget"]
        or preferences["category"]
        or preferences["layout_type"]
        or work_name
    )

    if not has_any_criteria:
        return {
            "status": "casual_chat",
            "reply": "Hello! I am your real estate assistant. Please provide your budget or workplace (e.g., 'I work at BGC Taguig').",
            "recommendations": [],
        }

    try:
        query = supabase.table("listings").select("*")

        if preferences["downpayment_budget"]:
            query = query.lte("initial_dp", preferences["downpayment_budget"])
        if preferences["monthly_budget"]:
            query = query.lte("monthly_rate", preferences["monthly_budget"])
        if preferences["budget"]:
            budget_column = "initial_dp" if preferences["is_downpayment"] else "price_total"
            query = query.lte(budget_column, preferences["budget"])
        if preferences["category"]:
            query = query.ilike("category", preferences["category"])
        if preferences["layout_type"]:
            query = query.ilike("layout_type", f"%{preferences['layout_type']}%")
        if preferences["has_subdivision"]:
            query = query.or_(
                "village_name.ilike.%subdivision%,village_name.ilike.%village%"
            )

        rows = query.execute().data or []
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Database error: {str(e)}",
            "recommendations": [],
        }

    results = [format_listing_row(row) for row in rows]

    # Calculate routes & filter by commute time
    if work_lat and work_lng:
        filtered = []
        for item in results:
            if item.get("lat") and item.get("lng"):
                commute = calculate_osrm_commute(
                    item["lat"], item["lng"], work_lat, work_lng
                )
                if commute:
                    item["commute_info"] = commute
                    if (
                        max_commute_mins
                        and commute["duration_mins"] > max_commute_mins
                    ):
                        continue
            filtered.append(item)

        filtered.sort(
            key=lambda x: x.get("commute_info", {}).get(
                "duration_mins", float("inf")
            )
            if x.get("commute_info")
            else float("inf")
        )
        results = filtered

    results = results[:3]

    if not results:
        return {
            "status": "no_match",
            "reply": "No available listings found matching your specifications.",
            "preferences_detected": preferences,
            "detected_workplace": detected_workplace,
            "recommendations": [],
        }

    reply_msg = (
        f"I found {len(results)} properties within {max_commute_mins} mins commute to {work_name}."
        if work_name and max_commute_mins
        else f"I calculated travel routes to {work_name} and ranked them by shortest commute!"
        if work_name
        else f"With a downpayment of ₱{preferences['downpayment_budget']:,.2f} and ₱{preferences['monthly_budget']:,.2f} monthly, I recommend '{results[0]['title']}'."
        if preferences["downpayment_budget"] and preferences["monthly_budget"]
        else f"Based on your downpayment of ₱{preferences['downpayment_budget']:,.2f}, I recommend '{results[0]['title']}'."
        if preferences["downpayment_budget"]
        else f"Based on your monthly budget of ₱{preferences['monthly_budget']:,.2f}, I recommend '{results[0]['title']}'."
        if preferences["monthly_budget"]
        else f"You mentioned wanting a {preferences['layout_type']} unit — here's '{results[0]['title']}'."
        if preferences["layout_type"]
        else f"Based on your budget of ₱{preferences['budget']:,.2f}, I recommend '{results[0]['title']}'."
        if preferences["budget"]
        else "Here are the top options matching your search."
    )

    return {
        "status": "recommendation_found",
        "reply": reply_msg,
        "preferences_detected": preferences,
        "detected_workplace": detected_workplace,
        "recommendations": results,
    }