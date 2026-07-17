/* ARKLAND Web Store — Progressive Web App service worker.
 *
 * Estratégia segura para loja autenticada e dinâmica:
 * - /api/*  → network-only (nunca grava em Cache Storage)
 * - HTML/navegação → network-first sem cachear o documento
 * - assets estáticos (js/css/img/fontes) → cache-first com atualização em background
 */
"use strict";

const CACHE_NAME = "arkland-webstore-static-v1";
const PRECACHE_URLS = [
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

const STATIC_EXT_RE =
  /\.(?:js|css|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|eot|map)(?:\?|$)/i;

function isApiRequest(url) {
  return url.pathname === "/api" || url.pathname.startsWith("/api/");
}

function isNavigationOrHtml(request, url) {
  if (request.mode === "navigate") return true;
  const accept = request.headers.get("accept") || "";
  if (accept.includes("text/html")) return true;
  const path = url.pathname;
  return path === "/" || path.endsWith(".html");
}

function isStaticAsset(url) {
  if (url.pathname === "/service-worker.js") return false;
  if (url.pathname === "/manifest.webmanifest") return true;
  return STATIC_EXT_RE.test(url.pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch (_) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  // Nunca cachear APIs autenticadas / dinâmicas.
  if (isApiRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }

  // HTML da loja muda com auth/sessão — sempre rede; sem put no cache.
  if (isNavigationOrHtml(request, url)) {
    event.respondWith(
      fetch(request, { cache: "no-store" }).catch(() =>
        new Response(
          "<!DOCTYPE html><html lang=\"pt-BR\"><head><meta charset=\"UTF-8\" />" +
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />" +
            "<title>ARKLAND — offline</title></head><body style=\"font-family:sans-serif;" +
            "background:#060402;color:#d4c8a8;padding:40px;text-align:center;\">" +
            "<h1>Sem conexão</h1><p>A loja ARKLAND precisa de internet para carregar.</p>" +
            "<p><a href=\"/\" style=\"color:#00c8ff;\">Tentar novamente</a></p></body></html>",
          { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
        )
      )
    );
    return;
  }

  if (!isStaticAsset(url)) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request);
      const networkPromise = fetch(request)
        .then((response) => {
          if (response && response.ok && response.type === "basic") {
            cache.put(request, response.clone()).catch(() => {});
          }
          return response;
        })
        .catch(() => cached);
      return cached || networkPromise;
    })
  );
});
