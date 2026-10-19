/* DOMIORA — service worker.
 * Règles de confidentialité : seuls les fichiers statiques publics (/static/) sont mis en
 * cache. Les pages HTML, l'API, la messagerie, les documents et les médias privés ne sont
 * jamais stockés : ils passent toujours par le réseau. Hors connexion, une page d'information
 * statique est affichée à la place d'une navigation.
 */
const VERSION = "domiora-static-v1";
const OFFLINE_URL = "/hors-ligne/";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.add(new Request(OFFLINE_URL, { cache: "reload" }))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL)));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy));
        }
        return res;
      }))
    );
  }
});
