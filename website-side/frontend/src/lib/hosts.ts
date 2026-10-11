// The public site and the Management System live on separate domains, so they
// install as two separate apps (an installed app covers every page under its
// address; on one domain the public app would also claim /manage, and the
// browser would treat Alty MSA as "already installed").
//
//   VITE_SITE_URL  e.g. https://alty-thesis.vercel.app  -> public site
//   VITE_MSA_URL   e.g. https://alty-msa.vercel.app     -> /manage (Alty MSA)
//
// Both domains point at this same deployment. When either is unset (local
// development, preview deployments) everything stays on the current address.
import { areaOf } from "./pwa"

const clean = (value: string | undefined) => (value ?? "").trim().replace(/\/+$/, "")
const SITE_URL = clean(import.meta.env.VITE_SITE_URL)
const MSA_URL = clean(import.meta.env.VITE_MSA_URL)

const originOf = (url: string) => {
  try { return new URL(url).origin } catch { return "" }
}
const SITE_ORIGIN = originOf(SITE_URL)
const MSA_ORIGIN = originOf(MSA_URL)
const SPLIT = Boolean(SITE_ORIGIN && MSA_ORIGIN && SITE_ORIGIN !== MSA_ORIGIN)

/** Where this path belongs when it is opened on the wrong domain; null when it is on the right one. */
export function crossHostUrl(pathname: string, rest = ""): string | null {
  if (!SPLIT) return null
  const here = window.location.origin
  const area = areaOf(pathname)
  if (here === MSA_ORIGIN) {
    if (pathname === "/") return `${MSA_ORIGIN}/manage` // the MSA domain opens on the Management System
    return area === "site" ? `${SITE_ORIGIN}${pathname}${rest}` : null
  }
  if (here === SITE_ORIGIN && area === "manage") return `${MSA_ORIGIN}${pathname}${rest}`
  return null
}

/** Send the browser to the right domain for the current page. True when leaving. */
export function moveToOwnHost(): boolean {
  const { pathname, search, hash } = window.location
  const target = crossHostUrl(pathname, search + hash)
  if (!target) return false
  window.location.replace(target)
  return true
}
