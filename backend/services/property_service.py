import json


def format_listing_row(row: dict) -> dict:
    item = dict(row)
    item["lat"] = float(item["lat"]) if item.get("lat") is not None else None
    item["lng"] = float(item["lng"]) if item.get("lng") is not None else None
    item["price_total"] = (
        float(item["price_total"])
        if item.get("price_total") is not None
        else None
    )
    item["monthly_rate"] = (
        float(item["monthly_rate"])
        if item.get("monthly_rate") is not None
        else None
    )

    for key in ["amenity_list", "nearby_establishments"]:
        if isinstance(item.get(key), str):
            try:
                item[key] = json.loads(item[key])
            except Exception:
                pass

    return item