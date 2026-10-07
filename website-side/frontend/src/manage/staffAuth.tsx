// Staff (management) accounts on the web: the same /api/v1/auth endpoints,
// users, roles and permissions as the desktop app. Website client accounts are
// refused by those endpoints, so a client token never opens management pages.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { t } from "./i18n"
import { clearApiCache } from "./useApiData"
import { API_URL } from "@/config"
import { ApiError, requestJson } from "@/lib/auth"
import { EXPIRED_KEY, StaffAuthContext, type StaffUser } from "./staffContext"

const AUTH_URL = `${API_URL}/api/v1/auth`
const TOKEN_KEY = "alty-staff-token"

/** When the token stops working (ms since epoch), from its "exp" claim. */
function expiresAt(token: string | null): number | null {
  try {
    const payload = JSON.parse(atob(token!.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")))
    return typeof payload.exp === "number" ? payload.exp * 1000 : null
  } catch {
    return null
  }
}


// "Stay signed in" keeps the token in localStorage; otherwise it lasts for
// this browser session only (shared office computers).
function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY) ?? window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function storeToken(token: string | null, remember = false) {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY)
    window.localStorage.removeItem(TOKEN_KEY)
    if (token) (remember ? window.localStorage : window.sessionStorage).setItem(TOKEN_KEY, token)
  } catch {
    /* storage blocked: signed in while this page stays open */
  }
}

export function StaffAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken)
  const [user, setUser] = useState<StaffUser | null>(null)
  const [isReady, setIsReady] = useState(!readToken())

  const signOut = useCallback((reason?: "expired") => {
    clearApiCache() // the next person must not see this account's data
    const current = readToken()
    const stillValid = current && (expiresAt(current) ?? Infinity) > Date.now()
    if (current && stillValid && reason !== "expired") {
      // Records LOGOUT in the audit log; signing out locally never waits for it.
      // (An expired session can't be logged out on the server — it already ended.)
      void fetch(`${AUTH_URL}/logout`, { method: "POST", headers: { Authorization: `Bearer ${current}` } }).catch(() => {})
    }
    if (reason === "expired") {
      try { window.sessionStorage.setItem(EXPIRED_KEY, "1") } catch { /* storage blocked */ }
    }
    storeToken(null)
    setToken(null)
    setUser(null)
    setIsReady(true)
  }, [])

  // Sign out the moment the session expires, so nothing keeps calling the API
  // with a token the server will refuse (that was the source of 401 errors).
  useEffect(() => {
    const expiry = expiresAt(token)
    if (!token || expiry === null) return
    const timer = window.setTimeout(() => signOut("expired"), Math.max(0, expiry - Date.now()))
    return () => window.clearTimeout(timer)
  }, [token, signOut])

  // Restore a saved session; drop it when expired or not a staff account.
  useEffect(() => {
    if (!token || user) return
    let current = true
    requestJson<StaffUser>(`${AUTH_URL}/me`, {}, token)
      .then((me) => current && setUser(me))
      .catch((error: ApiError) => {
        if (!current) return
        if (error.status === 401 || error.status === 403) {
          storeToken(null)
          setToken(null)
        }
      })
      .finally(() => current && setIsReady(true))
    return () => {
      current = false
    }
  }, [token, user])

  const signIn = useCallback(async (username: string, password: string, remember: boolean) => {
    // OAuth2 password form, as the desktop sends it.
    const body = new URLSearchParams({ username, password })
    const session = await requestJson<{ access_token: string }>(`${AUTH_URL}/login`, {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    })
    const me = await requestJson<StaffUser>(`${AUTH_URL}/me`, {}, session.access_token)
    storeToken(session.access_token, remember)
    try { window.sessionStorage.removeItem(EXPIRED_KEY) } catch { /* storage blocked */ }
    setToken(session.access_token)
    setUser(me)
    setIsReady(true)
  }, [])

  const api = useCallback(
    async <T,>(path: string, init: RequestInit = {}) => {
      try {
        return await requestJson<T>(`${API_URL}/api/v1${path}`, init, token)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) signOut("expired") // back to sign-in
        throw error
      }
    },
    [token, signOut],
  )

  const apiBlob = useCallback(
    async (path: string) => {
      let response: Response
      try {
        response = await fetch(`${API_URL}/api/v1${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      } catch {
        throw new ApiError(t("Can't reach the server. Check your connection and try again."), 0)
      }
      if (response.status === 401) signOut("expired")
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        const detail = (payload as { detail?: unknown }).detail
        throw new ApiError(typeof detail === "string" ? t(detail) : t("The file is currently unavailable."), response.status, detail)
      }
      return response.blob()
    },
    [token, signOut],
  )

  const can = useCallback((page: string) => Boolean(user?.permissions.includes(page)), [user])

  /** Re-read the signed-in account (e.g. after changing your own photo). */
  const reloadUser = useCallback(async () => {
    if (token) setUser(await requestJson<StaffUser>(`${AUTH_URL}/me`, {}, token))
  }, [token])

  const value = useMemo(
    () => ({ token, user, isReady, signIn, signOut: () => signOut(), api, apiBlob, can, reloadUser }),
    [token, user, isReady, signIn, signOut, api, apiBlob, can, reloadUser],
  )
  return <StaffAuthContext.Provider value={value}>{children}</StaffAuthContext.Provider>
}
