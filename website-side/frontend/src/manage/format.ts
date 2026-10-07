// Formatting and role helpers shared by the management pages.
import { locale, t } from "./i18n"

export const peso = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "—" // missing, not zero
  const n = Number(value)
  return Number.isFinite(n) ? `₱${Math.round(n).toLocaleString("en-PH")}` : "—"
}

export const pesoShort = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "—"
  const n = Number(value)
  if (!Number.isFinite(n)) return "—"
  return n >= 1e9 ? `₱${+(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `₱${+(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `₱${Math.round(n / 1e3)}K` : `₱${n}`
}

// Times are shown in Philippine time with a 12-hour clock ("2:30 PM").
const PH_ZONE = "Asia/Manila"
const clock = (d: Date) =>
  d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: PH_ZONE })
const day = (d: Date, zone = PH_ZONE) =>
  d.toLocaleDateString(locale(), { month: "short", day: "numeric", year: "numeric", timeZone: zone })
const parse = (value: unknown) => {
  if (!value) return null
  const d = new Date(String(value))
  return Number.isNaN(d.getTime()) ? null : d
}

export const date = (value: unknown): string => {
  const d = parse(value)
  return d ? day(d) : "—"
}

/** "Oct 7, 2026 · 2:30 PM" (record timestamps: uploads, sign-ins, edits). */
export const dateTime = (value: unknown): string => {
  const d = parse(value)
  return d ? `${day(d)} · ${clock(d)}` : "—"
}

/** A transaction's date and time. A date stated without a time is stored at
 *  00:00 UTC; it shows as the date alone rather than a made-up time. */
export const transactionDate = (value: unknown): string => {
  const d = parse(value)
  if (!d) return "—"
  const dateOnly = d.getUTCHours() === 0 && d.getUTCMinutes() === 0 && d.getUTCSeconds() === 0 && d.getUTCMilliseconds() === 0
  return dateOnly ? day(d, "UTC") : `${day(d)} · ${clock(d)}`
}

/** RESERVED -> Reserved, ON_HOLD -> On hold (in the chosen language). */
export const statusLabel = (value: unknown): string => {
  const text = String(value ?? "").replace(/_/g, " ").trim().toLowerCase()
  return text ? t(text[0].toUpperCase() + text.slice(1)) : "—"
}

export const text = (value: unknown): string => (value === null || value === undefined || value === "" ? "—" : String(value))

// Mirrors the backend role groups (app/core/security.py). The API enforces
// them; the web only hides actions a role can't perform.
const MANAGEMENT = new Set(["administrator", "general manager", "president"])
const FILING = new Set([...MANAGEMENT, "filing manager"])
export const isManagement = (role?: string | null) => MANAGEMENT.has(String(role ?? "").toLowerCase())
export const canEditListings = (role?: string | null) => FILING.has(String(role ?? "").toLowerCase())
/** Filing actions: edit/archive/reprocess/delete documents, manage property photos. */
export const canFile = canEditListings

export const fileSize = (bytes: unknown): string => {
  const n = Number(bytes)
  if (!Number.isFinite(n)) return "—"
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`
}

export const contains = (haystack: unknown[], needle: string) => {
  const q = needle.trim().toLowerCase()
  return !q || haystack.some((value) => String(value ?? "").toLowerCase().includes(q))
}
