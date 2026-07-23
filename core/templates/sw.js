/* Service Worker de FitTrack
   Estrategia: red primero (la app es dinamica); si no hay conexion,
   responde desde cache lo ultimo que se vio. Los archivos estaticos
   se guardan en cache al pasar. */
const CACHE = 'fittrack-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // no interceptar CDN/MP

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Guardar copia de paginas y estaticos que cargan bien
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
