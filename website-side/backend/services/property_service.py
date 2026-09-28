import json

FLOAT_FIELDS = ["lat", "lng", "price_total", "monthly_rate", "initial_dp"]
JSON_FIELDS = ["amenity_list", "nearby_establishments"]


def format_listing_row(row: dict) -> dict:
    item = dict(row)

    for key in FLOAT_FIELDS:
        item[key] = float(item[key]) if item.get(key) is not None else None

    for key in JSON_FIELDS:
        if isinstance(item.get(key), str):
            try:
                item[key] = json.loads(item[key])
            except Exception:
                pass

    return item