const scope = self.registration.scope;
const prefix = `firebase-preflight:${scope}:`;
const cacheName = prefix + VERSION;
const precache = new Set(ASSETS.map(asset => new URL(asset, scope).href));
const landing = new URL("index.html", scope).href;

self.addEventListener("install", event => {
  event.waitUntil(caches.open(cacheName).then(cache => cache.addAll([...precache])));
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(prefix) && key !== cacheName)
      .map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = request.url === scope ? landing : request.url;
  if (request.method !== "GET" || !precache.has(url)) return;
  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    return (await cache.match(url)) ?? fetch(request);
  })());
});
