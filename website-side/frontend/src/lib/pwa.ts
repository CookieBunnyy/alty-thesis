// Progressive Web App support: two installable apps on one site.
//   - "Abellar Realty" (the public site, /)        -> /manifest.webmanifest
//   - "Alty MSA" (Management System, /manage)       -> /manage.webmanifest
// index.html picks the right manifest before the page loads; this module keeps
// it in step on in-app navigation, registers the service worker and holds the
// browser's install prompt for the Install app buttons.
import { useSyncExternalStore } from "react"

export type AppArea = "site" | "manage"

export const areaOf = (pathname: string): AppArea =>
  pathname === "/manage" || pathname.startsWith("/manage/") ? "manage" : "site"

const APPS: Record<AppArea, { manifest: string; title: string; icon: string; favicon: string; theme: string }> = {
  site: { manifest: "/manifest.webmanifest", title: "Abellar Realty", icon: "/icons/site-180.png", favicon: "/icons/site-favicon.png", theme: "#11160A" },
  manage: { manifest: "/manage.webmanifest", title: "Alty MSA", icon: "/icons/manage-180.png", favicon: "/icons/manage-favicon.png", theme: "#1D2116" },
}

// Chrome/Edge's install prompt (not in the TS DOM types).
interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>
}

let pending: { event: InstallPromptEvent; area: AppArea } | null = null
let version = 0
const listeners = new Set<() => void>()
const notify = () => {
  version += 1
  listeners.forEach((listener) => listener())
}

const INSTALLED_KEY = (area: AppArea) => `alty-pwa-installed-${area}`
const remember = (area: AppArea, installed: boolean) => {
  try {
    if (installed) localStorage.setItem(INSTALLED_KEY(area), "1")
    else localStorage.removeItem(INSTALLED_KEY(area))
  } catch { /* storage blocked: the button just stays visible */ }
}
const remembered = (area: AppArea) => {
  try { return localStorage.getItem(INSTALLED_KEY(area)) === "1" } catch { return false }
}

const currentArea = () => areaOf(window.location.pathname)

/** Point the page at the manifest, icons and colour of the given app. */
export function applyManifest(area: AppArea) {
  const app = APPS[area]
  const link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]')
  if (!link || link.getAttribute("href") === app.manifest) return
  link.setAttribute("href", app.manifest)
  document.querySelector('link[rel="icon"]')?.setAttribute("href", app.favicon)
  document.querySelector('link[rel="apple-touch-icon"]')?.setAttribute("href", app.icon)
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", app.theme)
  document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute("content", app.title)
}

/** Running as an installed app (its own window / home-screen app). */
export const isStandalone = () =>
  window.matchMedia("(display-mode: standalone)").matches ||
  window.matchMedia("(display-mode: window-controls-overlay)").matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true

export type InstallPlatform = "ios" | "safari" | "firefox" | "chromium"
export function installPlatform(): InstallPlatform {
  const ua = navigator.userAgent
  if (/iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return "ios"
  if (/firefox|fxios/i.test(ua)) return "firefox"
  if (/safari/i.test(ua) && !/chrome|chromium|crios|edg/i.test(ua)) return "safari"
  return "chromium"
}

/** Call once at start-up (before React renders). */
export function setupPwa() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault() // we show our own button instead of the mini-infobar
    pending = { event: event as InstallPromptEvent, area: currentArea() }
    remember(pending.area, false) // offered again -> it is not installed (any more)
    notify()
  })
  window.addEventListener("appinstalled", () => {
    remember(pending?.area ?? currentArea(), true)
    pending = null
    notify()
  })
  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => { /* the site works without it */ })
    })
  }
}

const subscribe = (listener: () => void) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Install state for the app of `area`. */
export function useInstall(area: AppArea) {
  useSyncExternalStore(subscribe, () => version)
  const standalone = isStandalone()
  const canPrompt = pending !== null && pending.area === area
  return {
    /** Hide the button: already running as the app, or installed here and not offered again. */
    hidden: standalone || (!canPrompt && remembered(area)),
    canPrompt,
    platform: installPlatform(),
    /** Show the browser's install dialog; false when there is none to show. */
    async install(): Promise<boolean> {
      if (!pending || pending.area !== area) return false
      const { event } = pending
      await event.prompt()
      const { outcome } = await event.userChoice
      if (outcome === "accepted") {
        remember(area, true)
        pending = null
      }
      notify()
      return true
    },
  }
}
