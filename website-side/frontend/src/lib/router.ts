// Minimal client-side router on the History API (the site had no routing
// before; this is its only routing system). Production hosting must serve
// index.html for unknown paths (SPA fallback), as `vite preview` does.
import { useSyncExternalStore } from "react"

const listeners = new Set<() => void>()
const subscribe = (listener: () => void) => {
  listeners.add(listener)
  window.addEventListener("popstate", listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener("popstate", listener)
  }
}
const snapshot = () => window.location.pathname + window.location.search

export function navigate(to: string, { replace = false } = {}) {
  if (to === snapshot()) return
  window.history[replace ? "replaceState" : "pushState"](null, "", to)
  listeners.forEach((listener) => listener())
  if (!replace) window.scrollTo({ top: 0 })
}

export function useLocation() {
  const current = useSyncExternalStore(subscribe, snapshot)
  const url = new URL(current, window.location.origin)
  return { pathname: url.pathname, search: url.searchParams, href: current }
}

/** "/agents/AGT-1" against "/agents/:id" -> { id: "AGT-1" } */
export function matchPath(pattern: string, pathname: string): Record<string, string> | null {
  const a = pattern.split("/").filter(Boolean)
  const b = pathname.split("/").filter(Boolean)
  if (a.length !== b.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < a.length; i++) {
    if (a[i].startsWith(":")) params[a[i].slice(1)] = decodeURIComponent(b[i])
    else if (a[i] !== b[i]) return null
  }
  return params
}

/** Where to go after signing in: only same-site paths are accepted. */
export const safeNext = (value: string | null) =>
  value && value.startsWith("/") && !value.startsWith("//") ? value : null
