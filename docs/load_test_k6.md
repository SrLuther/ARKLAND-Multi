# Load test básico — Web Store ARKLAND

Script de referência para validar home, catálogo e bootstrap sob carga leve.

## Pré-requisitos

- [k6](https://k6.io/docs/get-started/installation/) instalado
- Web Store acessível (ex.: `http://127.0.0.1:5000`)

## Executar

```bash
k6 run -e BASE_URL=http://127.0.0.1:5000 tools/k6/webstore_smoke.js
```

## O que medir

- `http_req_duration` p95 em `/api/public/home` e `/api/catalog` (alvo < 500 ms com cache quente)
- Taxa de `304` quando `If-None-Match` reutiliza ETag
- Ausência de 500 HTML em rotas `/api/*`
- Pool MySQL: consultar `GET /api/admin/metrics` (admin) — `pool_wait_p95_ms` estável

## Cenários sugeridos

1. **Smoke** — 5 VUs, 30 s (script incluído)
2. **Spike catálogo** — 20 VUs, 2 min, só GET `/api/catalog`
3. **Bootstrap autenticado** — requer cookie de sessão exportado; não incluído no smoke público
