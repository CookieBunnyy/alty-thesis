"""Price and closing-cost breakdown for a property purchase (Philippines).

An estimate for explaining the total cost to a buyer, computed on the
selling price. The official computation uses the HIGHER of the selling
price, the BIR zonal value and the assessor's fair market value, and local
rates differ per city, so the page always presents this as an estimate.

Rates (settings, so they can be updated without code changes):
- Documentary stamp tax 1.5% (NIRC Sec. 196), customarily paid by the buyer.
- Local transfer tax: up to 0.75% in Metro Manila cities/municipality and up
  to 0.5% in provinces (Local Government Code Secs. 135 and 151), buyer.
- Registration fee at the Registry of Deeds (LRA schedule), about 0.25%, buyer.
- Notarial fee for the deed of sale, commonly about 1%, buyer.
- VAT 12% when a VAT-registered seller (a developer, in the course of
  business) sells: a residential lot, or a house and lot above the BIR
  VAT-exempt threshold. Developer prices normally already include it.
- Capital gains tax 6% when the seller is not in the business of selling
  property; customarily paid by the seller.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings
from app.models.partner import Partner
from app.models.property_listing import PropertyListing

# Metro Manila (NCR): its 16 cities and 1 municipality, plus well-known
# districts people write instead of the city.
NCR_PLACES = (
    "metro manila", "ncr", "manila", "quezon city", "caloocan", "las pinas", "las piñas", "makati", "malabon",
    "mandaluyong", "marikina", "muntinlupa", "navotas", "paranaque", "parañaque", "pasay", "pasig", "pateros",
    "san juan city", "taguig", "valenzuela", "bgc", "bonifacio global city", "fort bonifacio", "ortigas",
    "alabang", "eastwood", "cubao", "rockwell", "binondo", "ermita", "malate", "sta. mesa", "santa mesa",
    "diliman", "novaliches", "greenhills", "mckinley", "filinvest city", "vertis north",
)
# A province named in the address wins over a same-named place ("San Juan, Batangas").
PROVINCES = (
    "cavite", "laguna", "batangas", "rizal", "bulacan", "pampanga", "tarlac", "nueva ecija", "zambales", "bataan",
    "quezon province", "cebu", "davao", "iloilo", "pangasinan", "benguet", "antipolo", "tagaytay",
)
LOT_ONLY = ("lot only", "vacant lot", "residential lot", "raw land", "land only")
CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _has(text: str, words: tuple[str, ...]) -> str | None:
    return next((w for w in words if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text)), None)


def location_of(listing: PropertyListing | None) -> dict:
    """Whether the property is in Metro Manila, from its address text."""
    text = " ".join(str(v) for v in (listing.village_name, listing.title, listing.details) if v).lower() \
        if listing else ""
    province = _has(text, PROVINCES)
    ncr = _has(text, NCR_PLACES)
    if province:
        return {"metro_manila": False, "matched": province,
                "reason": f"The address mentions {province.title()}, outside Metro Manila."}
    if ncr:
        return {"metro_manila": True, "matched": ncr,
                "reason": f"The address mentions {ncr.title() if len(ncr) > 3 else ncr.upper()}, in Metro Manila."}
    return {"metro_manila": False, "matched": None,
            "reason": "The address doesn't name a Metro Manila city, so the provincial rate is used."}


def breakdown(listing: PropertyListing | None, price: Decimal, partner: Partner | None = None) -> dict:
    price = Decimal(price or 0)
    location = location_of(listing)
    category = (listing.category or "").lower() if listing else ""
    is_lot = any(word in category for word in LOT_ONLY) or category.strip() == "lot"
    developer = partner is not None and (partner.partner_type or "").upper() == "DEVELOPER"
    threshold = Decimal(str(settings.VAT_EXEMPT_DWELLING_MAX))

    if not developer:
        vat = {"applies": False, "amount": Decimal(0), "code": "NOT_DEVELOPER",
               "reason": "No VAT: the seller isn't recorded as a developer, so a sale by an individual owner is "
                         "assumed (capital gains tax applies instead)."}
    elif not is_lot and price <= threshold:
        vat = {"applies": False, "amount": Decimal(0), "code": "EXEMPT", "threshold": threshold,
               "reason": f"VAT-exempt: a residential dwelling sold for ₱{threshold:,.0f} or less."}
    else:
        rate = Decimal(str(settings.VAT_RATE))
        vat = {"applies": True, "amount": _money(price * rate / (1 + rate)), "code": "INCLUDED",
               "reason": "The developer's sale is subject to 12% VAT, normally already included in the listed "
                         "price; this is the VAT part of the price, not an extra charge."}

    transfer_rate = Decimal(str(settings.TRANSFER_TAX_METRO if location["metro_manila"]
                                else settings.TRANSFER_TAX_PROVINCE))
    lines = [
        ("transfer_tax", "Local transfer tax", transfer_rate,
         "Paid to the city or province treasurer. Metro Manila up to 0.75%; provinces up to 0.5%."),
        ("documentary_stamp_tax", "Documentary stamp tax", Decimal(str(settings.DST_RATE)),
         "Paid to the BIR on the deed of sale (1.5%)."),
        ("registration_fee", "Registration fee", Decimal(str(settings.REGISTRATION_FEE_RATE)),
         "Paid to the Registry of Deeds to transfer the title (about 0.25%, from the LRA schedule)."),
        ("notarial_fee", "Notarial fee", Decimal(str(settings.NOTARIAL_FEE_RATE)),
         "Notarizing the deed of absolute sale (commonly about 1%)."),
    ]
    buyer = [{"key": key, "label": label, "rate": float(rate), "amount": _money(price * rate), "note": note}
             for key, label, rate, note in lines]
    buyer_total = sum((item["amount"] for item in buyer), Decimal(0))
    seller = []
    if not developer:
        cgt = Decimal(str(settings.CAPITAL_GAINS_TAX_RATE))
        seller.append({"key": "capital_gains_tax", "label": "Capital gains tax", "rate": float(cgt),
                       "amount": _money(price * cgt),
                       "note": "6% to the BIR, customarily paid by the seller (not the buyer)."})
    return {
        "price": _money(price),
        "location": location,
        "seller_is_developer": developer,
        "property_kind": "lot" if is_lot else "dwelling",
        "vat": vat,
        "buyer_fees": buyer,
        "buyer_fees_total": _money(buyer_total),
        "total_cost": _money(price + buyer_total),
        "seller_fees": seller,
        "basis": "Estimated on the selling price. Official taxes use the higher of the selling price, the BIR zonal "
                 "value or the assessor's fair market value, and local rates can differ; confirm the final "
                 "amounts with the BIR, the city treasurer and the Registry of Deeds.",
    }
