import { useCallback, useEffect, useState } from "react"
import { navigate, useLocation } from "@/lib/router"

// Last data each page loaded, kept for this browser tab. Opening a page again
// shows it immediately while fresh data loads in the background, instead of a
// blank skeleton on every visit. Cleared on sign-out (clearApiCache).
const cache = new Map<string, unknown>()

export function clearApiCache() {
  cache.clear()
}

/** Load data from the API when the page opens; ``reload`` fetches again.
 *  With ``cacheKey`` the previous result (if any) is shown straight away and
 *  then refreshed. Use a key that includes any filters the load depends on. */
export function useApiData<T>(load: () => Promise<T>, cacheKey?: string) {
  const [data, setData] = useState<T | null>(() => (cacheKey && cache.has(cacheKey) ? (cache.get(cacheKey) as T) : null))
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const reload = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const fresh = await load()
      if (cacheKey) cache.set(cacheKey, fresh)
      setData(fresh)
    } catch (loadError) {
      setError((loadError as Error).message)
    } finally {
      setLoading(false)
    }
  }, [load, cacheKey])
  useEffect(() => {
    // Fetching from the API (an external system) when the page opens.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload()
  }, [reload])
  const setAndCache = useCallback((next: T) => {
    if (cacheKey) cache.set(cacheKey, next)
    setData(next)
  }, [cacheKey])
  return { data, setData: setAndCache, error, loading, reload }
}

/** The record open in the side panel, kept in the URL (?id=…) so it can be
 *  linked to from other pages and survives a reload. */
export function useOpenRecord() {
  const { pathname, search } = useLocation()
  const id = search.get("id")
  const open = useCallback((next: string) => navigate(`${pathname}?id=${encodeURIComponent(next)}`), [pathname])
  const close = useCallback(() => navigate(pathname, { replace: true }), [pathname])
  return { id, open, close }
}
