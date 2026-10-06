// Website client accounts. Uses the main Alty API's client portal
// (/api/v1/client/*): same users table, password hashing and tokens as the
// desktop, but a separate Client role that can't open internal endpoints.
import { createContext, useContext } from "react"
import { API_URL } from "@/config"
import type { ClientProfile } from "@/types"

export const TOKEN_KEY = "alty-client-token"
export const CLIENT_URL = `${API_URL}/api/v1/client`

export class ApiError extends Error {
  status: number
  /** The response's ``detail`` (e.g. {message, existing_document} for a duplicate upload). */
  detail: unknown
  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

const detailText = (payload: unknown, fallback: string) => {
  const detail = (payload as { detail?: unknown })?.detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object" && typeof (detail as { message?: unknown }).message === "string")
    return (detail as { message: string }).message
  if (Array.isArray(detail)) return detail.map((item) => String(item?.msg ?? item).replace(/^Value error, /, "")).join("; ")
  return fallback
}

export async function requestJson<T>(url: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        // JSON bodies only; FormData (file uploads) sets its own multipart type.
        ...(typeof init.body === "string" ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError("Can't reach Abellar Realty right now. Check your connection and try again.", 0)
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok)
    throw new ApiError(detailText(payload, "Something went wrong. Please try again."), response.status, (payload as { detail?: unknown })?.detail)
  return payload as T
}

export type Session = { access_token: string; client: ClientProfile }
export type SignUpInput = { full_name: string; email: string; phone_number: string; location?: string; password: string }

export type AuthValue = {
  token: string | null
  client: ClientProfile | null
  isReady: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (input: SignUpInput) => Promise<void>
  signOut: () => void
  /** Authenticated request; signs out automatically on an expired token. */
  authed: <T>(path: string, init?: RequestInit) => Promise<T>
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>")
  return value
}
