// The visitor's workplace, kept only for this browsing session: it survives
// page reloads and navigation, and is forgotten when the tab or browser is
// closed (sessionStorage), so a returning visitor sets it again.
import type { LocationPoint } from "@/types"

const KEY = "alty-workplace"

// Earlier versions kept the workplace forever in localStorage; drop it once.
try {
  window.localStorage.removeItem(KEY)
} catch {
  /* storage blocked */
}

export function loadWorkplace(): LocationPoint | null {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(KEY) ?? "null")
    return saved && Number.isFinite(saved.lat) && Number.isFinite(saved.lng) && saved.name ? saved : null
  } catch {
    return null
  }
}

export function saveWorkplace(place: LocationPoint | null) {
  try {
    if (place) window.sessionStorage.setItem(KEY, JSON.stringify(place))
    else window.sessionStorage.removeItem(KEY)
  } catch {
    /* storage blocked: kept in memory for this page only */
  }
}

/** Straight-line distance in km between two points (haversine). */
export function kmBetween(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** "Near your workplace" radius choices (straight-line km); 20 km by default. */
export const RADIUS_OPTIONS_KM = [5, 10, 20, 30, 50] as const
export const DEFAULT_RADIUS_KM = 20
