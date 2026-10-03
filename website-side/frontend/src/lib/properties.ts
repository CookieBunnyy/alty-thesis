import { API_URL } from "@/config"
import type { Property } from "@/types"

// Every listing the public may see: available ones plus reserved and sold
// (shown with their status badge). The API's default is AVAILABLE only.
export const PUBLIC_PROPERTIES_URL = `${API_URL}/api/v1/public/properties?status=AVAILABLE,RESERVED,SOLD`

export const isAvailable = (property: Property) => String(property.status ?? "AVAILABLE").toUpperCase() === "AVAILABLE"

const ORDER: Record<string, number> = { AVAILABLE: 0, RESERVED: 1, SOLD: 2 }

/** 0 available, 1 reserved, 2 sold. */
export const availabilityRank = (property: Property) => ORDER[String(property.status ?? "AVAILABLE").toUpperCase()] ?? 3

/** Available listings first, then reserved, then sold (stable within each). */
export function sortByAvailability(properties: Property[]): Property[] {
  return [...properties].sort((a, b) => availabilityRank(a) - availabilityRank(b))
}
