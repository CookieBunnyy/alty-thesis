// Common amenities of Philippine house-and-lot subdivisions and condominiums,
// offered in the amenities dropdown. Anything else goes in "Other amenities"
// (the listing's other_amenities column), typed in as text.

export const AMENITY_GROUPS: { label: string; for: "house" | "condo" | "both"; items: string[] }[] = [
  {
    label: "Common to both", for: "both",
    items: ["Swimming pool", "Clubhouse", "24/7 security", "CCTV", "Playground", "Fitness gym", "Function hall",
      "Jogging path", "Landscaped gardens", "Parking area", "Backup power", "Water supply / cistern"],
  },
  {
    label: "House and lot (subdivision)", for: "house",
    items: ["Gated entrance", "Perimeter fence", "Basketball court", "Multi-purpose court", "Chapel",
      "Parks and open spaces", "Covered court", "Tennis court", "Commercial strip", "Shuttle terminal"],
  },
  {
    label: "Condominium (building)", for: "condo",
    items: ["Elevators", "Lobby and reception", "Concierge", "Sky lounge / roof deck", "Kids' play area",
      "Laundry area", "Garbage chute", "Fire sprinkler system", "Retail shops", "Co-working space"],
  },
]

export const ALL_AMENITIES = AMENITY_GROUPS.flatMap((group) => group.items)

/** The listing's amenity_list as names (older records may store an object). */
export const amenityNames = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.map(String) : raw && typeof raw === "object" ? Object.keys(raw as Record<string, unknown>) : []

/** Condominium categories list the building amenities first. */
export const isCondo = (category: string) => /condo|condominium|unit|studio/i.test(category)
