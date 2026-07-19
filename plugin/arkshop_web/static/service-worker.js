/* ARKLAND Web Store — Progressive Web App service worker.
 *
 * Estratégia segura para loja autenticada e dinâmica:
 * - /api/catalog → stale-while-revalidate (público e não sensível; acelera warmup)
 * - restante /api/* → network-only (nunca grava em Cache Storage)
 * - HTML/navegação → network-only (no-store; nunca cachear index.html)
 * - ícones PWA pequenos → cache-first (precache)
 * - /species/icons/* e thumbs grandes → network-only (não competir com APIs
 *   no arranque nem encher Cache Storage; lazy no DOM)
 * - outros assets estáticos (js/css/fontes) → cache-first com atualização em background
 */
"use strict";

const CACHE_NAME = "arkland-webstore-static-v5";
const CATALOG_CACHE = "arkland-webstore-catalog-v1";
const PRECACHE_URLS = [
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

const STATIC_EXT_RE =
  /\.(?:js|css|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|eot|map)(?:\?|$)/i;

// Apenas o catálogo público pode ser servido do cache (stale-while-revalidate).
// Nunca /api/store/bootstrap (inclui sessão) nem mutações/admin/redeem.
function isPublicCatalog(url) {
  return url.pathname === "/api/catalog";
}

function isApiRequest(url) {
  return url.pathname === "/api" || url.pathname.startsWith("/api/");
}

function isNavigationOrHtml(request, url) {
  if (request.mode === "navigate") return true;
  const accept = request.headers.get("accept") || "";
  if (accept.includes("text/html")) return true;
  const path = url.pathname;
  return path === "/" || path.endsWith(".html") || path === "/index.html";
}

function isHeavyImageAsset(url) {
  // Ícones de espécie / thumbs de catálogo — dezenas/centenas de webp.
  // Não cachear: evita I/O do SW no warmup e pressão no disco/bandwidth.
  // team/*.png — network-only (conteúdo pode trocar com o mesmo path; ?v= + sem SW stale).
  const p = url.pathname;
  return (
    p.startsWith("/species/icons/") ||
    p.startsWith("/catalog/resources/team/") ||
    p.startsWith("/media/") ||
    /thumbnail|thumb_|\/thumbs?\//i.test(p)
  );
}

function isStaticAsset(url) {
  if (url.pathname === "/service-worker.js") return false;
  if (url.pathname === "/manifest.webmanifest") return true;
  if (isHeavyImageAsset(url)) return false;
  return STATIC_EXT_RE.test(url.pathname);
}

self.addEventListener("install", (event) => {
  // Force update imediato — não esperar tabs antigas fecharem.
  // Precache só ícones PWA pequenos — NUNCA species/icons nem index.html.
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([CACHE_NAME, CATALOG_CACHE]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
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

  // Catálogo público: stale-while-revalidate — devolve cache na hora e
  // atualiza em background. Só respostas OK e sem cookies de sessão.
  if (isPublicCatalog(url)) {
    event.respondWith(
      caches.open(CATALOG_CACHE).then(async (cache) => {
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
    return;
  }

  // Nunca cachear APIs autenticadas / dinâmicas (bootstrap, redeem, admin…).
  if (isApiRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }

  // HTML da loja — SEMPRE rede, nunca Cache Storage (evita overlay antigo preso).
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

  // Imagens pesadas (espécies/thumbs): network-only — não entram no Cache Storage.
  if (isHeavyImageAsset(url)) {
    event.respondWith(fetch(request));
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
