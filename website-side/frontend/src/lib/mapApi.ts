// Map data client. All routing, traffic and place search goes through the
// main Alty API (/api/v1/map/*), which talks to the providers; no provider
// key or URL lives in the website.
import { API_URL } from "@/config"
import type {
  CommuteResult,
  LocationPoint,
  MapCapabilities,
  NearbyAgentsResult,
  PlaceResult,
} from "@/types"

const MAP_URL = `${API_URL}/api/v1/map`

export class MapApiError extends Error {}

const FRIENDLY: Record<number, string> = {
  404: "No road route was found between these points.",
  429: "Too many map requests. Please wait a moment and try again.",
  503: "Route information is currently unavailable.",
}

async function getJson<T>(url: string, token?: string | null): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined)
  } catch {
    throw new MapApiError("Can't reach the ALTY server. Check your connection and try again.")
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    // The backend already returns user-safe messages; never show raw errors.
    const detail = (payload as { detail?: unknown }).detail
    throw new MapApiError(
      typeof detail === "string" ? detail : FRIENDLY[response.status] ?? "Map information is currently unavailable.",
    )
  }
  return payload as T
}

// Results are cached per request and requested only when a property is
// selected — never for every marker. Commute results expire after
// COMMUTE_TTL_MS because live-traffic travel times change.
const cache = new Map<string, { promise: Promise<unknown>; expires: number }>()
const COMMUTE_TTL_MS = 2 * 60 * 1000

function cached<T>(key: string, load: () => Promise<T>, ttlMs = Infinity): Promise<T> {
  const hit = cache.get(key)
  if (hit && hit.expires > Date.now()) return hit.promise as Promise<T>
  const promise = load().catch((error) => {
    cache.delete(key) // failures are retried on the next request
    throw error
  })
  cache.set(key, { promise, expires: Date.now() + ttlMs })
  return promise
}

const coord = (value: number) => value.toFixed(5)

export const getCapabilities = () => cached("capabilities", () => getJson<MapCapabilities>(`${MAP_URL}/capabilities`))

const commuteParams = (origin: LocationPoint, destination: { lat: number; lng: number }) =>
  new URLSearchParams({
    origin_lat: coord(origin.lat),
    origin_lng: coord(origin.lng),
    dest_lat: coord(destination.lat),
    dest_lng: coord(destination.lng),
  })

export function getCommute(origin: LocationPoint, destination: { lat: number; lng: number }, fresh = false) {
  const params = commuteParams(origin, destination)
  if (fresh) cache.delete(`commute:${params}`)
  return cached(`commute:${params}`, () => getJson<CommuteResult>(`${MAP_URL}/commute?${params}`), COMMUTE_TTL_MS)
}

export const searchPlaces = (query: string) =>
  cached(`geocode:${query.trim().toLowerCase()}`, () =>
    getJson<{ results: PlaceResult[] }>(`${MAP_URL}/geocode?${new URLSearchParams({ q: query.trim() })}`),
  ).then((data) => data.results)

export const reversePlace = (lat: number, lng: number) =>
  cached(`reverse:${coord(lat)},${coord(lng)}`, () =>
    getJson<{ result: PlaceResult | null }>(`${MAP_URL}/reverse-geocode?lat=${coord(lat)}&lng=${coord(lng)}`),
  ).then((data) => data.result)

// Agents' phone numbers are only returned to a signed-in client, so the
// cache keeps signed-in and signed-out answers apart.
export const getNearbyAgents = (listingId: number | string, token?: string | null) =>
  cached(`agents:${listingId}:${token ? token.slice(-16) : "public"}`, () =>
    getJson<NearbyAgentsResult>(`${API_URL}/api/v1/public/properties/${listingId}/nearby-agents`, token),
  )

export const trafficTileUrl = (theme: "dark" | "light") => `${MAP_URL}/traffic/tiles/{z}/{x}/{y}.png?theme=${theme}`

/** Browser geolocation, only ever on an explicit user action. */
export function requestCurrentPosition(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new MapApiError("Your browser doesn't support location access."))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
      (error) =>
        reject(
          new MapApiError(
            error.code === error.PERMISSION_DENIED
              ? "Location access was denied. Allow it in your browser settings, or search for the place instead."
              : "Your location couldn't be determined. Try again or search for the place instead.",
          ),
        ),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  })
}

export const formatKm = (meters: number) => `${(meters / 1000).toFixed(meters < 10000 ? 1 : 0)} km`

export function formatMinutes(seconds: number) {
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}
