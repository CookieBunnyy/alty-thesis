// The staff session token, shared by the one Sign In page (/signin, for buyers
// and staff) and the Management System. "Stay signed in" keeps it in
// localStorage; otherwise it lasts for this browser session only (shared
// office computers).
import { ApiError } from "@/lib/auth"
import { authRequest } from "./authRequests"
import { EXPIRED_KEY } from "./staffContext"

export const STAFF_TOKEN_KEY = "alty-staff-token"

export function readStaffToken(): string | null {
  try {
    return window.sessionStorage.getItem(STAFF_TOKEN_KEY) ?? window.localStorage.getItem(STAFF_TOKEN_KEY)
  } catch {
    return null
  }
}

export function storeStaffToken(token: string | null, remember = false) {
  try {
    window.sessionStorage.removeItem(STAFF_TOKEN_KEY)
    window.localStorage.removeItem(STAFF_TOKEN_KEY)
    if (token) (remember ? window.localStorage : window.sessionStorage).setItem(STAFF_TOKEN_KEY, token)
  } catch {
    /* storage blocked: signed in while this page stays open */
  }
}

/** Staff sign-in (username + password, plus the security check when the
 *  server asks for it). Stores the session and returns its token; throws an
 *  ApiError whose detail says whether a check is needed or how long to wait. */
export async function staffSignIn(username: string, password: string, remember: boolean, captchaToken?: string | null): Promise<string> {
  const body = new URLSearchParams({ username, password })
  if (captchaToken) body.set("captcha_token", captchaToken)
  const reply = await authRequest<{ access_token: string }>("/login", {
    method: "POST",
    body,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })
  if (!reply.ok || !reply.data) {
    throw new ApiError(reply.message, reply.status, { captchaRequired: reply.captchaRequired, retryAfter: reply.retryAfter })
  }
  storeStaffToken(reply.data.access_token, remember)
  try { window.sessionStorage.removeItem(EXPIRED_KEY) } catch { /* storage blocked */ }
  return reply.data.access_token
}
