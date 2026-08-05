# Garantias pré-release — ArkShop Web (Flask / MySQL)

Documento curto: o que a suite automatizada **já prova** vs o que **só a prática no host** valida.  
Não substitui lançamento; aumenta confiança antes do update. O utilizador decide o momento.

---

## Mapa das otimizações (Fases 1–5)

| Fase | Módulo(s) | Papel |
|------|-----------|--------|
| 1 Pool | `db_pool.py`, `app._configure_database`, `src/pages/db_local_server.py` | `pool_size=20`, overflow=10, recycle=1800, timeout=5; pico=30; MariaDB `--max-connections=180`, `--wait-timeout=600` |
| 2 BG I/O | `background_tasks.py`, `payment_jobs.py`, `pending_jobs.py` | MP/RCON fora do worker HTTP; recover ENTREGANDO ~10s; dedupe; **INLINE ignorado em production** |
| 3 Índices | `app._ensure_hot_path_indexes` | Índices compostos orders/payments; READY só se todos presentes; self-heal |
| 4 Cache | `ttl_cache.py` + rotas settings/servers/config | TTL 5–15s; **PIX proibido**; empty-cache pending **não** com ENTREGANDO |
| 5 Waitress | `waitress_config.py` | Threads 4–8, cap `pool−headroom`; diagnostics usa `resolve_http_threads` (nunca mentir 32) |

---

## Garantido por teste automatizado

Correr (a partir de `plugin/arkshop_web`):

```bash
python -m pytest `
  tests/test_prod_adversarial_p0.py `
  tests/test_pre_release_guarantees.py `
  tests/test_db_pool.py `
  tests/test_ttl_cache.py `
  tests/test_waitress_config.py `
  tests/test_short_ttl_endpoints.py `
  tests/test_fase2_background_io.py `
  tests/test_concurrency_guards.py `
  tests/test_external_io_guards.py `
  tests/test_db_diagnostics.py `
  tests/test_pending_delivery_optimizations.py `
  -q
```

| Garantia | Onde |
|----------|------|
| `py_compile` / `ast` nos módulos tocados + `app.py` | `test_pre_release_guarantees` |
| Anti-padrão: PIX sem `ttl_cache` / `X-Short-Cache` | static + runtime header |
| MP fetch **antes** de abrir sessão DB | static `payment_jobs` |
| Sessão libertada (`force=True`) mesmo com erro no confirm MP | unit |
| Double-start: interval / pending-stale / catalog-feed / runtime workers | concurrency + pre-release |
| Retry scheduler reinicia se thread morreu | `test_retry_scheduler_restarts_dead_thread` |
| Retry secondary workers após falha de boot | concurrency |
| **Schedulers no boot** (não dependem do 1.º request; `/api/auth/me` é skip) | `test_prod_adversarial_p0` + bloco fim `app.py` |
| **`ARKSHOP_BG_INLINE` ignorado se `ARKSHOP_ENV=production`** | adversarial + `background_tasks` |
| Interval worker arranca em production apesar de INLINE | adversarial |
| Circuit open → `/api/health` 200; rotas DB → 503 | isolation |
| Threads Waitress ≤ pool − headroom; diagnostics ≠ 32 | waitress + adversarial + diagnostics |
| Pico pool 30 vs MariaDB 180 (instâncias seguras) | `db_pool` + adversarial |
| Admin orders: sem COUNT no default; `has_more` via LIMIT+1 | `test_app.TestAdminOrdersList` |
| Claim **não** chama recover se scheduler vivo; **sim** se morto | fase2 + pending_delivery |
| Empty-cache **proibido** se há ENTREGANDO; invalida se scheduler morto | pending_delivery |
| PIX status não bloqueia no MP (enqueue bg) | fase2 |
| Pool: `db_session` sob carga leve → `checkedout()==0` | pre-release |
| MariaDB flags no arranque TEK | static `db_local_server` |
| JSON tocados (`CustomShop/catalog.json*`) válidos se existirem | static |

---

## Só a prática no host valida

Checklist manual pós-deploy (sem `_release.ps1`):

1. **Arranque** — Web Store sobe; logs com `runtime_workers_started` / `boot_snapshot` **antes** de qualquer request de jogador (TEK pode só pingar `/api/auth/me`).
2. **Pool sob carga real** — `hey`/`ab` em `/api/catalog` e `/api/public/home` (ver `docs/ARKSHOP_WEB_CACHE_WAITRESS.md`); `checked_out` estável em `/api/admin/diagnostics/database`; `waitress_threads_configured` ∈ 4–8; sem `QueuePool` timeout.
3. **MariaDB portable** — mysqld com `max_connections=180` e `wait_timeout=600`; não abrir >~5 instâncias da Web Store no mesmo host (`max_safe_app_instances`).
4. **Env production** — `ARKSHOP_ENV=production`; se `ARKSHOP_BG_INLINE` estiver no ambiente por engano, log de erro e comportamento async (não sync).
5. **PIX real** — poll no Network **sem** `X-Short-Cache`; crédito após approve MP.
6. **Webhook MP** — ACK rápido; crédito em background.
7. **DeliverPending** — claim sem stall com scheduler vivo; se matar a thread `arkshop-pending-stale`, claim seguinte ainda recupera ENTREGANDO stale.
8. **Admin Pedidos** — 1.ª página rápida; `has_more`; `include_total=1` só quando pedido.
9. **Índices** — `hot_path_indexes_ready` true após migrate; CREATE INDEX não bloqueia requests longos.
10. **Schedulers vivos** — após horas, `arkshop-retry` / `arkshop-pending-stale` / catalog-feed activas (ou self-restart).
11. **Circuit breaker** — MySQL down → 503 em rotas DB; health 200; após cooldown
   half-open com 1 probe; sucesso em query normal fecha o circuit (não só ping diagnostics).

---

## Bugs P0 corrigidos (pré-launch)

| # | Sintoma | Fix |
|---|---------|-----|
| 1 | TEK pingava `/api/auth/me` (skip) → schedulers nunca subiam | `_start_runtime_workers_once()` no boot DB (`SKIP_DB_BOOT!=1`) |
| 2 | Empty-cache com ENTREGANDO escondia recover; scheduler morto = fila presa | Não cachear vazio se ENTREGANDO; `_maybe_recover_stale_on_claim` se scheduler morto |
| 3 | `ARKSHOP_BG_INLINE=1` em production = sync + schedulers “OK” mas mortos | INLINE ignorado se `ARKSHOP_ENV=production` |
| 4 | Diagnostics reportava 32 threads | `resolve_http_threads` (4–8 / cap pool) |
| 5 | Retry scheduler com flag INITIALIZED + thread morta não reiniciava | `is_alive()` em `_initialize_scheduler_if_needed` + re-chamada em todo request pós-boot |

---

## O que isto **não** prova

- Latência RCON/MP/Steam em mapas offline reais  
- Contenção InnoDB / locks longos em produção  
- Multi-host (cache in-memory não partilhado)  
- Waitress sob carga com I/O externo ainda síncrono em algum path legado  
- Correctness financeira end-to-end com Mercado Pago live  
- Comportamento com várias instâncias a partilhar o mesmo MariaDB (só orçamento teórico)

O utilizador decide o momento do update.
