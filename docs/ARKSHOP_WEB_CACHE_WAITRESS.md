# Cache curto + Waitress (Fases 4 e 5) — Web Store

> Módulos: `plugin/arkshop_web/ttl_cache.py`, `plugin/arkshop_web/waitress_config.py`  
> Pool MySQL (Fase 1): `plugin/arkshop_web/db_pool.py` — **não alterar aqui**

---

## Fase 4 — O que é cacheado

| Domínio | Endpoint / path | TTL | Header |
|--------|------------------|-----|--------|
| Lista produtos loja | `GET /api/catalog` (+ bootstrap partilhado) | **15s** default (+ SWR) | `X-Catalog-Cache` |
| Configs sistema | `GET /api/settings`, `GET /api/config` | **10s** (5–15) | `X-Short-Cache` |
| Status servidores | `GET /api/servers`, `GET /api/servers/connect-status` | **10s** | `X-Short-Cache` |
| Sync recentes | `GET /api/admin/sync-all-permissions/status` (só job parado) | **10s** | `X-Short-Cache` |

**Não cacheado (proibido):** `GET /api/player/pix/<id>/status` e qualquer poll de pagamento tempo-real.

Backend: **in-memory TTL** (`ttl_cache.py`). Redis **não** está no projeto — não foi introduzido.

Env úteis:

| Variável | Default | Efeito |
|----------|---------|--------|
| `ARKSHOP_SHORT_CACHE_TTL_SEC` | `10` | TTL dos caches curtos (clamp 5–15) |
| `ARKSHOP_CATALOG_CACHE_TTL_SEC` | `15` | TTL catálogo público |

Invalidação: gravação de settings/servers/config e start de sync-all limpam os namespaces afectados.

---

## Fase 5 — Waitress final

Waitress corre **1 processo**. A fórmula do plano `workers ≈ (CPU×2)+1` define o número de **threads**, limitado a **4–8**.

| Parâmetro | Valor |
|-----------|--------|
| Threads (auto) | `clamp((CPU×2)+1, 4, 8)` |
| Cap ao pool | **ligado por default** → `threads ≤ pool_size` |
| Pool Fase 1 | `pool_size=20`, `max_overflow=10` → total ≤ 30 |
| `channel_timeout` | 180 |
| `connection_limit` | 500 |
| `backlog` | 2048 |

Env:

| Variável | Efeito |
|----------|--------|
| `ARKSHOP_HTTP_THREADS` | Override explícito (ainda ≥4; cap ao pool se activo) |
| `ARKSHOP_HTTP_THREADS_FORCE=1` | Sem cap ao pool (perigoso) |
| `ARKSHOP_HTTP_THREADS_CAP_TO_POOL=0` | Desliga cap (legado) |

Exemplo (4 CPUs): fórmula=9 → threads=**8**; pool=20 → OK (8 ≪ 30).

---

## Como stress-testar

Pré-requisitos: Web Store a correr (`python plugin/arkshop_web/app.py` ou TEK), MariaDB up.

### 1. Catálogo / home (leitura quente)

```bash
# hey (https://github.com/rakyll/hey) — 100 concurrent, 30s
hey -z 30s -c 100 -m GET http://127.0.0.1:5177/api/catalog
hey -z 30s -c 100 -m GET http://127.0.0.1:5177/api/public/home
```

Esperado: maioria `X-Catalog-Cache: HIT` / `X-Home-Cache: HIT|STALE`; latência p95 ≪ fila antiga (50s+).

### 2. Admin settings/servers (cache curto)

Com sessão admin (cookie) ou via browser DevTools → Network: dois GET seguidos a `/api/settings` devem mostrar `X-Short-Cache: MISS` depois `HIT`.

### 3. Observabilidade

```bash
# admin autenticado
curl -s http://127.0.0.1:5177/api/admin/metrics | python -m json.tool
curl -s http://127.0.0.1:5177/api/admin/diagnostics/database | python -m json.tool
```

Verificar: `cache.short_ttl`, `pool.checked_out` estável, sem `QueuePool` timeout nos logs.

### 4. Pagamentos (regressão negativa)

Sob carga, poll PIX **não** deve devolver `X-Short-Cache`. Confirmar no Network tab em `/api/player/pix/.../status`.

### 5. Pytest de regressão

```bash
cd plugin/arkshop_web
python -m pytest tests/test_ttl_cache.py tests/test_waitress_config.py tests/test_short_ttl_endpoints.py tests/test_public_catalog_cache.py tests/test_public_home_cache.py tests/test_db_pool.py -q
```

---

## Riscos

1. **Stale até 15s** em config/servers após edição noutro processo (multi-instância no mesmo host é bloqueada pelo instance lock; workers multi-host não partilham RAM).
2. **Threads 4–8** vs carga histórica com 32: fila HTTP pode crescer se RCON/MP ainda bloquearem workers — depende da Fase 2 (background I/O).
3. **FORCE=1 + threads altas** pode voltar a esgotar o pool MySQL (20+10).
4. Catálogo TTL 15s (antes 45s) regenera enrich mais vezes; SWR mitiga spikes.
