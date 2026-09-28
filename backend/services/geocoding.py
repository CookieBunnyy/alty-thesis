import time
import requests

_geocode_cache: dict[str, dict] = {}


def geocode_location(location_name: str) -> dict | None:
    cache_key = location_name.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "AltyThesisApp/1.0"}
    params = {"q": f"{location_name}, Philippines", "format": "json", "limit": 1}

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