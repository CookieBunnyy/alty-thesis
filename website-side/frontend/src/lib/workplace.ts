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
