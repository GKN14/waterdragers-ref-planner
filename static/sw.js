// Service Worker voor Scheidsrechter Planning App
const CACHE_NAME = 'scheidsrechter-app-v1';
const urlsToCache = [
  '/',
  '/app/static/icon-192.png',
  '/app/static/icon-512.png'
];

// Installatie
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// Fetch requests
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version of fetch from network
        return response || fetch(event.request);
      })
  );
});

// Cleanup old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => cacheName !== CACHE_NAME)
          .map(cacheName => caches.delete(cacheName))
      );
    })
  );
});
