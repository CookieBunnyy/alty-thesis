// Calls to the staff auth endpoints that need more than the JSON body: whether
// the server asks for the security check, and how long a cooldown lasts.
import { useEffect, useState } from "react"
import { API_URL } from "@/config"

export const AUTH_URL = `${API_URL}/api/v1/auth`

export type AuthReply<T> = {
  ok: boolean
  status: number
  data: T | null
  /** The server's message (always generic for sign-in and recovery). */
  message: string
  captchaRequired: boolean
  /** Seconds to wait (429 responses). */
  retryAfter: number
}

export async function authRequest<T>(path: string, init: RequestInit): Promise<AuthReply<T>> {
  let response: Response
  try {
    response = await fetch(`${AUTH_URL}${path}`, { ...init, headers: { Accept: "application/json", ...init.headers } })
  } catch {
    return { ok: false, status: 0, data: null, message: "Can't reach the server. Check your connection and try again.", captchaRequired: false, retryAfter: 0 }
  }
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>
  const detail = payload?.detail
  return {
    ok: response.ok,
    status: response.status,
    data: response.ok ? (payload as T) : null,
    message: typeof detail === "string" ? detail : typeof payload?.message === "string" ? (payload.message as string) : "",
    captchaRequired: response.headers.get("X-Captcha-Required") === "true",
    retryAfter: Number(response.headers.get("Retry-After")) || 0,
  }
}

export type SecurityConfig = { captcha_site_key: string | null; password_reset_enabled: boolean; password_reset_minutes: number }

let cached: Promise<SecurityConfig> | null = null

/** Public sign-in settings from the API (Turnstile site key, recovery on/off). */
export function useSecurityConfig(): SecurityConfig | null {
  const [config, setConfig] = useState<SecurityConfig | null>(null)
  useEffect(() => {
    let alive = true
    cached ??= authRequest<SecurityConfig>("/security-config", {}).then((reply) => {
      if (!reply.ok || !reply.data) {
        cached = null
        return { captcha_site_key: null, password_reset_enabled: false, password_reset_minutes: 20 }
      }
      return reply.data
    })
    cached.then((value) => alive && setConfig(value))
    return () => { alive = false }
  }, [])
  return config
}

/** Counts down from `seconds` (0 = idle). */
export function useCountdown(): [number, (seconds: number) => void] {
  const [left, setLeft] = useState(0)
  useEffect(() => {
    if (left <= 0) return
    const timer = window.setTimeout(() => setLeft((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [left])
  return [left, setLeft]
}

export const formatWait = (seconds: number) =>
  seconds >= 60 ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}` : `${seconds}s`
