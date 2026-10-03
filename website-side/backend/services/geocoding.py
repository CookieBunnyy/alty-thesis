import math
import os
import time

import requests

_geocode_cache: dict[str, dict] = {}

# The main Alty API geocodes with caching and Nominatim's 1 request/second
# policy (GET /api/v1/map/geocode); it is tried first. Set MAIN_API_URL on the
# chatbot's Render service. Direct Nominatim is the fallback and must identify
# the app with a contact (Nominatim usage policy), set by GEOCODER_USER_AGENT.
MAIN_API_URL = os.getenv("MAIN_API_URL", "https://alty-thesis-52z9.onrender.com").rstrip("/")
USER_AGENT = os.getenv(
    "GEOCODER_USER_AGENT", "AltyRealtyChatbot/2.0 (+https://alty-thesis.vercel.app)"
)


def _via_main_api(location_name: str) -> dict | None:
    if not MAIN_API_URL:
        return None
    try:
        res = requests.get(f"{MAIN_API_URL}/api/v1/map/geocode", params={"q": location_name}, timeout=8)
        if res.status_code == 200:
            results = res.json().get("results") or []
            if results:
                return {"name": location_name, "lat": float(results[0]["lat"]), "lng": float(results[0]["lng"])}
    except Exception as e:
        print(f"Main API geocoding error: {e}")
    return None


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance, used only to rank listings near a named area."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def geocode_location(location_name: str) -> dict | None:
    cache_key = location_name.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    result = _via_main_api(location_name)
    if result:
        _geocode_cache[cache_key] = result
        return result

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": USER_AGENT}
    params = {"q": location_name, "countrycodes": "ph", "format": "json", "limit": 1}

    for attempt in range(2):  # try once, retry once on failure/rate-limit
        try:
            res = requests.get(url, params=params, headers=headers, timeout=5)
            if res.status_code == 200:
                results = res.json()
                if results:
                    data = results[0]
                    result = {
                        "name": location_name,
                        "lat": float(data["lat"]),
                        "lng": float(data["lon"]),
                    }
                    _geocode_cache[cache_key] = result
                    return result
            elif res.status_code == 429:
                time.sleep(1.1)
                continue
        except Exception as e:
            print(f"Geocoding error (attempt {attempt + 1}): {e}")
            time.sleep(0.5)

    return None


def calculate_osrm_commute(
    prop_lat: float, prop_lng: float, work_lat: float, work_lng: float
) -> dict | None:
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{prop_lng},{prop_lat};{work_lng},{work_lat}?overview=false"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("routes"):
                route = data["routes"][0]
                duration_mins = round(route["duration"] / 60.0)

                score = (
                    "Excellent"
                    if duration_mins <= 20
                    else "Good"
                    if duration_mins <= 35
                    else "Moderate"
                    if duration_mins <= 50
                    else "Far"
                )

                return {
                    "distance_km": round(route["distance"] / 1000.0, 1),
                    "duration_mins": duration_mins,
                    "convenience_score": score,
                }
    except Exception as e:
        print(f"OSRM calculation error: {e}")
    return None