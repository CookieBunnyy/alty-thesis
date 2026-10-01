import { useCallback, useEffect, useState } from "react"
import { getCommute } from "@/lib/mapApi"
import type { CommuteResult, LocationPoint, Property } from "@/types"

export type CommuteState = {
  result: CommuteResult | null
  error: string | null
  isLoading: boolean
  updatedAt: Date | null
  refresh: () => void
}

const LIVE_REFRESH_MS = 2 * 60 * 1000
const noop = () => {}
const IDLE: CommuteState = { result: null, error: null, isLoading: false, updatedAt: null, refresh: noop }

/** Road routes from the workplace to one property, for every travel mode.
 *  Requested only for the selected property; repeated calls (map + panel,
 *  re-selection) reuse the cached response. With a live-traffic provider the
 *  result is refreshed every two minutes while the property stays selected. */
export function useCommute(workplace: LocationPoint | null | undefined, property: Property | null | undefined) {
  const origin = workplace ? { lat: workplace.lat, lng: workplace.lng, name: workplace.name } : null
  const destination = property?.lat != null && property?.lng != null ? { lat: property.lat, lng: property.lng } : null
  const key = origin && destination ? `${origin.lat},${origin.lng}->${destination.lat},${destination.lng}` : null
  const [state, setState] = useState<{
    key: string | null
    result: CommuteResult | null
    error: string | null
    updatedAt: Date | null
  }>({ key: null, result: null, error: null, updatedAt: null })
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!key || !origin || !destination) return
    let current = true
    getCommute(origin, destination, nonce > 0)
      .then((result) => current && setState({ key, result, error: null, updatedAt: new Date() }))
      .catch((error: Error) => current && setState({ key, result: null, error: error.message, updatedAt: null }))
    return () => {
      current = false
    }
    // origin/destination are derived from `key`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce])

  const live = state.key === key && Boolean(state.result?.live_traffic)
  useEffect(() => {
    if (!live) return
    const timer = window.setInterval(() => setNonce((n) => n + 1), LIVE_REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [live, key])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])

  if (!key) return IDLE
  if (state.key !== key) return { ...IDLE, isLoading: true, refresh }
  return { result: state.result, error: state.error, isLoading: false, updatedAt: state.updatedAt, refresh }
}
