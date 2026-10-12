// Lot sizes: square metres, switching to hectares from 10,000 m² (1 ha).
const SQM_PER_HECTARE = 10_000

const number = (value: number, digits = 2) => value.toLocaleString("en-PH", { maximumFractionDigits: digits })

/** Short form for cards: "250 sqm" or "64 ha". */
export function lotAreaShort(sqm: number | string | null | undefined): string | null {
  const value = Number(sqm)
  if (!sqm || !Number.isFinite(value) || value <= 0) return null
  return value >= SQM_PER_HECTARE ? `${number(value / SQM_PER_HECTARE)} ha` : `${number(value, 0)} sqm`
}

/** Full form for details: "250 sqm" or "640,000 sqm (64 hectares)". */
export function lotAreaLong(sqm: number | string | null | undefined): string | null {
  const value = Number(sqm)
  if (!sqm || !Number.isFinite(value) || value <= 0) return null
  if (value < SQM_PER_HECTARE) return `${number(value)} sqm`
  const hectares = value / SQM_PER_HECTARE
  return `${number(value, 0)} sqm (${number(hectares)} hectare${hectares === 1 ? "" : "s"})`
}
