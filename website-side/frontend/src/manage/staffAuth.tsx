// Staff (management) accounts on the web: the same /api/v1/auth endpoints,
// users, roles and permissions as the desktop app. Website client accounts are
// refused by those endpoints, so a client token never opens management pages.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { API_URL } from "@/config"
import { ApiError, requestJson } from "@/lib/auth"
import { StaffAuthContext, type StaffUser } from "./staffContext"

const AUTH_URL = `${API_URL}/api/v1/auth`
const TOKEN_KEY = "alty-staff-token"


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

  const signOut = useCallback(() => {
    const current = readToken()
    if (current) {
      // Records LOGOUT in the audit log; signing out locally never waits for it.
      void fetch(`${AUTH_URL}/logout`, { method: "POST", headers: { Authorization: `Bearer ${current}` } }).catch(() => {})
    }
    storeToken(null)
    setToken(null)
    setUser(null)
    setIsReady(true)
  }, [])

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
    setToken(session.access_token)
    setUser(me)
    setIsReady(true)
  }, [])

  const api = useCallback(
    async <T,>(path: string, init: RequestInit = {}) => {
      try {
        return await requestJson<T>(`${API_URL}/api/v1${path}`, init, token)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) signOut() // expired: back to sign-in
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
        throw new ApiError("Can't reach the server. Check your connection and try again.", 0)
      }
      if (response.status === 401) signOut()
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        const detail = (payload as { detail?: unknown }).detail
        throw new ApiError(typeof detail === "string" ? detail : "The file is currently unavailable.", response.status, detail)
      }
      return response.blob()
    },
    [token, signOut],
  )

  const can = useCallback((page: string) => Boolean(user?.permissions.includes(page)), [user])

  const value = useMemo(
    () => ({ token, user, isReady, signIn, signOut, api, apiBlob, can }),
    [token, user, isReady, signIn, signOut, api, apiBlob, can],
  )
  return <StaffAuthContext.Provider value={value}>{children}</StaffAuthContext.Provider>
}
