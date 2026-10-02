// Standard property categories. Listings store free text ("condo", "House &
// Lot"…); this maps them onto one list for filters, labels and counts.
// Keep in sync with PROPERTY_CATEGORIES in
// desktop-side/frontend/app/views/main/pages/properties.py.

export type Category = { key: string; label: string; aliases: string[] }

export const CATEGORIES: Category[] = [
  { key: "condominium", label: "Condominium", aliases: ["condo", "condominium", "condo unit", "studio", "loft"] },
  { key: "house-and-lot", label: "House and Lot", aliases: ["house", "house and lot", "house & lot", "single detached", "single-detached", "villa", "bungalow"] },
  { key: "townhouse", label: "Townhouse", aliases: ["townhouse", "town house", "rowhouse", "row house"] },
  { key: "duplex", label: "Duplex", aliases: ["duplex", "semi-detached", "semi detached"] },
  { key: "apartment", label: "Apartment", aliases: ["apartment", "apartment unit", "flat"] },
  { key: "lot", label: "Lot Only", aliases: ["lot", "lot only", "vacant lot", "residential lot", "land"] },
  { key: "commercial", label: "Commercial", aliases: ["commercial", "commercial space", "office", "office space", "retail", "shop"] },
  { key: "warehouse", label: "Warehouse / Industrial", aliases: ["warehouse", "industrial", "storage"] },
]

const normalize = (value: string) => value.trim().toLowerCase().replace(/\s+/g, " ")

/** The standard category for a listing's stored category (null if none). */
export function categoryOf(raw: string | null | undefined): Category | null {
  if (!raw) return null
  const value = normalize(raw)
  return (
    CATEGORIES.find((c) => c.aliases.includes(value) || normalize(c.label) === value) ??
    CATEGORIES.find((c) => c.aliases.some((alias) => value.includes(alias))) ??
    null
  )
}

/** Display label: the standard name, or the stored text if it isn't one. */
export const categoryLabel = (raw: string | null | undefined) => categoryOf(raw)?.label ?? (raw?.trim() || "Property")

/** Every standard category with how many of `items` belong to it. */
export function categoryCounts(items: { category?: string | null; count?: number }[]) {
  const counts = new Map<string, number>()
  for (const item of items) {
    const category = categoryOf(item.category)
    if (category) counts.set(category.key, (counts.get(category.key) ?? 0) + (item.count ?? 1))
  }
  return CATEGORIES.map((category) => ({ ...category, count: counts.get(category.key) ?? 0 }))
}
