import { useCallback, useEffect, useState } from "react"
import { navigate, useLocation } from "@/lib/router"

/** Load data from the API when the page opens; ``reload`` fetches again. */
export function useApiData<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const reload = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      setData(await load())
    } catch (loadError) {
      setError((loadError as Error).message)
    } finally {
      setLoading(false)
    }
  }, [load])
  useEffect(() => {
    // Fetching from the API (an external system) when the page opens.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload()
  }, [reload])
  return { data, setData, error, loading, reload }
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
