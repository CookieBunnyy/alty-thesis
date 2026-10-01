import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { ApiError, AuthContext, CLIENT_URL, TOKEN_KEY, requestJson, type Session, type SignUpInput } from "@/lib/auth"
import type { ClientProfile } from "@/types"

const readToken = () => {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readToken)
  const [client, setClient] = useState<ClientProfile | null>(null)
  const [isReady, setIsReady] = useState(!readToken())

  const store = useCallback((next: string | null) => {
    try {
      if (next) window.localStorage.setItem(TOKEN_KEY, next)
      else window.localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* storage blocked: signed in for this visit only */
    }
    setToken(next)
  }, [])

  const signOut = useCallback(() => {
    store(null)
    setClient(null)
  }, [store])

  // Restore the session (and drop expired tokens) on load.
  useEffect(() => {
    if (!token || client) return
    let current = true
    requestJson<ClientProfile>(`${CLIENT_URL}/me`, {}, token)
      .then((profile) => current && setClient(profile))
      .catch((error: ApiError) => {
        if (current && (error.status === 401 || error.status === 403)) signOut()
      })
      .finally(() => current && setIsReady(true))
    return () => {
      current = false
    }
  }, [token, client, signOut])

  const begin = useCallback(
    (session: Session) => {
      store(session.access_token)
      setClient(session.client)
      setIsReady(true)
    },
    [store],
  )

  const signIn = useCallback(
    async (email: string, password: string) =>
      begin(await requestJson<Session>(`${CLIENT_URL}/login`, { method: "POST", body: JSON.stringify({ email, password }) })),
    [begin],
  )

  const signUp = useCallback(
    async (input: SignUpInput) =>
      begin(await requestJson<Session>(`${CLIENT_URL}/register`, { method: "POST", body: JSON.stringify(input) })),
    [begin],
  )

  const authed = useCallback(
    async <T,>(path: string, init: RequestInit = {}) => {
      try {
        return await requestJson<T>(`${CLIENT_URL}${path}`, init, token)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) signOut()
        throw error
      }
    },
    [token, signOut],
  )

  const value = useMemo(
    () => ({ token, client, isReady, signIn, signUp, signOut, authed }),
    [token, client, isReady, signIn, signUp, signOut, authed],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
