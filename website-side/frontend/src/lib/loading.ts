// Tracks in-flight requests to the ALTY servers so the top progress bar can
// show that the site is working, not frozen. Every page loads through
// fetch(), so watching fetch covers all of them without touching each call.
import { useSyncExternalStore } from "react"
import { API_URL, CHAT_API_URL } from "@/config"

let active = 0
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((listener) => listener())

export function beginActivity() {
  active += 1
  if (active === 1) emit()
}

export function endActivity() {
  active = Math.max(0, active - 1)
  if (active === 0) emit()
}

export function useActivity(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => active > 0,
  )
}

const tracked = (input: RequestInfo | URL) => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url
  return url.startsWith(API_URL) || url.startsWith(CHAT_API_URL)
}

/** Wrap window.fetch once (at startup) to count ALTY API requests. */
export function installFetchTracking() {
  const original = window.fetch.bind(window)
  if ((original as { altyTracked?: boolean }).altyTracked) return
  const wrapped = (input: RequestInfo | URL, init?: RequestInit) => {
    if (!tracked(input)) return original(input, init)
    beginActivity()
    return original(input, init).finally(endActivity)
  }
  ;(wrapped as { altyTracked?: boolean }).altyTracked = true
  window.fetch = wrapped as typeof window.fetch
}
