/**
 * ANNADATA Service Worker — v4
 * Strategy:
 *   - Static assets (CSS/JS/images/fonts): Cache-first, update in background
 *   - HTML navigation: Network-first, fall back to offline page
 *   - POST / non-GET: bypass (never cache)
 */

const SW_VERSION  = 'v4';
const STATIC_CACHE = `annadata-static-${SW_VERSION}`;
const PAGES_CACHE  = `annadata-pages-${SW_VERSION}`;

// Pre-cache these static assets on install
const PRECACHE_ASSETS = [
  '/static/css/dashboard.css',
  '/static/css/auth.css',
  '/static/css/base.css',
  '/static/css/splash.css',
  '/static/css/crop.css',
  '/static/css/sathi.css',
  '/static/css/schemes.css',
  '/static/css/profile_setup.css',
  '/static/css/pwa.css',
  '/static/js/pwa.js',
  '/static/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/offline',
];

/* ── Install ───────────────────────────────────────────────── */
self.addEventListener('install', function (event) {
  console.log('[SW] Installing', SW_VERSION);
  event.waitUntil(
    caches.open(STATIC_CACHE).then(function (cache) {
      return Promise.allSettled(
        PRECACHE_ASSETS.map(function (url) {
          return cache.add(url).catch(function (err) {
            console.warn('[SW] Failed to pre-cache:', url, err);
          });
        })
      );
    })
  );
  self.skipWaiting();
});

/* ── Activate ──────────────────────────────────────────────── */
self.addEventListener('activate', function (event) {
  console.log('[SW] Activating', SW_VERSION);
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys
          .filter(function (key) { return key !== STATIC_CACHE && key !== PAGES_CACHE; })
          .map(function (key) {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

/* ── Message (skip waiting from update banner) ─────────────── */
self.addEventListener('message', function (event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

/* ── Fetch ─────────────────────────────────────────────────── */
self.addEventListener('fetch', function (event) {
  var request = event.request;
  var url     = new URL(request.url);

  // Skip non-GET and cross-origin
  if (request.method !== 'GET') return;
  if (url.origin !== location.origin) return;

  // ── Static assets: cache-first, update in background ──────
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(function (cache) {
        return cache.match(request).then(function (cached) {
          var fetchPromise = fetch(request).then(function (response) {
            if (response && response.ok) {
              cache.put(request, response.clone());
            }
            return response;
          }).catch(function () { return cached; });

          return cached || fetchPromise;
        });
      })
    );
    return;
  }

  // ── HTML navigation: network-first, offline fallback ──────
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(function (response) {
          // Cache successful page loads for offline use
          if (response && response.ok) {
            var clone = response.clone();
            caches.open(PAGES_CACHE).then(function (cache) {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(function () {
          // Try cached page, then offline page
          return caches.match(request).then(function (cached) {
            return cached || caches.match('/offline');
          });
        })
    );
    return;
  }

  // ── Everything else: network with cache fallback ───────────
  event.respondWith(
    fetch(request).catch(function () {
      return caches.match(request);
    })
  );
});
