// Minimal service worker: precaches the app shell so the PWA itself
// still loads (not just its data) after connectivity drops. Deliberately
// plain JS in public/ rather than a Vite-bundled TS module — the app
// shell asset list below is enough to keep this simple, and it avoids a
// second Vite build entry.
//
// Voice clip caching is handled directly by the page via the Cache
// Storage API (see src/operator/clipPlayer.ts) — this service worker
// doesn't need to know about it.

const SHELL_CACHE = 'macenplast-shell-v1'
const SHELL_ASSETS = ['/', '/index.html', '/manifest.webmanifest']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .catch(() => {
        // Missing optional assets (e.g. no manifest yet) shouldn't block install.
      }),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== SHELL_CACHE).map((key) => caches.delete(key))),
      ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) return
  // Only the app shell navigation and its built assets — API calls go
  // through the operator app's own offline outbox, not this cache.
  if (!(event.request.mode === 'navigate' || url.pathname.startsWith('/assets/'))) return

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached
      return fetch(event.request)
        .then((response) => {
          const responseClone = response.clone()
          caches.open(SHELL_CACHE).then((cache) => cache.put(event.request, responseClone))
          return response
        })
        .catch(() => caches.match('/index.html'))
    }),
  )
})
