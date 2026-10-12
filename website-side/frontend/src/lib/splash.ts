// The welcome screen in index.html covers the first load. It stays until the
// page's first requests to the ALTY servers have finished (so visitors never
// see a blank page while the database is read), at least briefly so it
// doesn't flash, and never longer than MAX_MS: after that the page shows its
// own loading placeholders.
import { isActive, onActivityChange } from "./loading"

const MIN_MS = 900 // from the first paint, so the welcome doesn't flash by
const QUIET_MS = 250 // no requests for this long = the first data is in
const NONE_MS = 3000 // a page that requests nothing still gets past the welcome
const MAX_MS = 20000

export function dismissSplashWhenReady() {
  const splash = document.getElementById("alty-splash")
  if (!splash) return
  let quiet: number | undefined
  let seen = false // the page's code can load before its first request starts
  let stop = () => {}

  const finish = () => {
    stop()
    window.clearTimeout(quiet)
    window.clearTimeout(cap)
    const wait = Math.max(0, MIN_MS - performance.now())
    window.setTimeout(() => {
      splash.classList.add("is-done")
      window.setTimeout(() => splash.remove(), 500)
    }, wait)
  }
  // Each time requests go quiet, wait a moment in case the next one starts.
  const check = () => {
    window.clearTimeout(quiet)
    if (isActive()) seen = true
    else if (seen) quiet = window.setTimeout(finish, QUIET_MS)
  }
  const cap = window.setTimeout(finish, MAX_MS)
  const none = window.setTimeout(() => !seen && finish(), NONE_MS)
  stop = () => {
    unsubscribe()
    window.clearTimeout(none)
  }
  const unsubscribe = onActivityChange(check)
  check()
}
