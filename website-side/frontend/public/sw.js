// Service worker for the two installable apps (Abellar Realty and Alty MSA).
// Pages: network first, falling back to the last copy of the app shell, then
// to an offline notice. Built files (/assets/, hashed names) and icons: cache
// first. API calls go to another server and are never cached here.
const VERSION = "alty-v1"
const SHELL = "/index.html"
const OFFLINE = "/offline.html"

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll([OFFLINE, "/icons/site-192.png", "/icons/manage-192.png"])))
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener("fetch", (event) => {
  const { request } = event
  if (request.method !== "GET") return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(VERSION).then((cache) => cache.put(SHELL, copy))
          }
          return response
        })
        .catch(async () => (await caches.match(SHELL)) || (await caches.match(OFFLINE))),
    )
    return
  }

  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(request).then((cached) =>
        cached ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(VERSION).then((cache) => cache.put(request, copy))
          }
          return response
        }),
      ),
    )
  }
})
