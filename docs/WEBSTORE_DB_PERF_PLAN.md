# Plano de Performance — Web Store + MariaDB

> **Status:** activo (P0 em curso)  
> **Data:** 2026-07-25  
> **Âmbito:** `plugin/arkshop_web` + MariaDB (não TEK desktop)  
> **Objectivo:** acabar com timeouts / `Unexpected token '<'` (HTML/DOCTYPE) / admin «Carregando…» eterno — com fases verificáveis, não patches soltos.

---

## 1. Diagnóstico honesto

### 1.1 O que JÁ existe (não inventar crédito)

| Área | O que está feito | Onde |
|------|------------------|------|
| Pedidos admin | `COUNT(*)` opt-in (`include_total=1`); `LIMIT+1` → `has_more`; `load_only` sem `payload_json` | `app.py` `admin_list_orders` |
| UI Pedidos | `fetchJson` + `beginTablePageFetch` + pager sem total | `static/index.html` `loadAdminOrders` |
| SeasonLand Ops (parcial) | `list_season_pass_orders` sem COUNT; UI Ops orders/audit com `fetchJson` + `include_total=0` | `season_pass_service.py`, `index.html` |
| Índices hot-path | `store_users`, `orders`, `point_payments`, market, `audit_events (event_type, created_at)` + self-heal | `app.py` `_HOT_PATH_INDEX_SPECS` |
| Pool / sessões | `db_pool.py`, force-release antes de I/O externo, teardown rollback | `db_pool.py`, `app.py` |
| Waitress | threads / channel_timeout / backlog configuráveis | `waitress_config.py` + `app.py` `__main__` |
| Cache curto | `ttl_cache.py`; catalog/home/bootstrap SWR; ETag catalog/home | `ttl_cache.py`, `app.py` |
| Bootstrap | 1 sessão DB; catálogo primeiro; budget; cache local por steam_id | `/api/store/bootstrap` + `index.html` |
| Catálogo UI | Paginação DOM **20**/página (filtros re-paginam); API full cache intacta | `index.html` `CATALOG_DOM_PAGE_SIZE` |
| Entregas | pending cache vazio/TTL; `load_only`; recover stale fast-path | pending paths em `app.py` |
| Admin jogador | essencial barato + `/heavy` lazy; sem DDL no request | `app.py` admin players |
| UI listagens | `fetchJson` + `readFetchJson` (mensagem PT se DOCTYPE); muitas tabelas com pager 10 | `index.html` |
| Docs relacionados | Cache/Waitress (parcialmente desactualizado vs defaults reais) | `docs/ARKSHOP_WEB_CACHE_WAITRESS.md` |
| Perf TEK (outro produto) | UI desktop — **fora deste plano** | `docs/PROJETO_PERFORMANCE_UI.md` |

**Nota de honestidade:** houve muitas correcções P0 pontuais (pool, bootstrap, pedidos, home). **Não** houve um plano único Web Store+DB com critérios de sucesso até este documento. Sintomas ainda se repetem porque listagens admin críticas e defaults de `COUNT(*)` ficaram inconsistentes.

### 1.2 O que AINDA causa timeout / DOCTYPE / carga pesada

| Sintoma observável | Causa real | Ficheiro / função |
|--------------------|------------|-------------------|
| Admin **Auditoria** «Carregando…» / `Unexpected token '<'` | UI usa `fetch` + `r.json()` cru; backend **faz COUNT por default** (`want_total` = true se omitir `include_total`) | `index.html` `loadAudit`; `app.py` `admin_list_audit` |
| Admin **PIX/Doações** lento na mesma página | Mesmo padrão: COUNT default + agregação `stats` full-table; `r.json()` cru | `loadPixAudit`; `admin_pix_audit` |
| SeasonLand Ops (já mitigado na UI) | Antes: COUNT/`LIKE sp:%` + `r.json()`; backend lista já `has_more` | restante: métricas Ops ainda `LIKE sp:%` GROUP BY |
| Mercado browse lento | `include_total=True` → `query.count()` | `market_listings.py` listagens |
| Tickets / sugestões / notifications | `.count()` ORM em listagens | `ticket_service.py`, `suggestion_service.py`, `notification_service.py` |
| DOCTYPE genérico sob carga | Waitress/proxy devolve HTML de erro/timeout; frontend sem `fetchJson` → parse JSON falha | dezenas de `r.json()` em `index.html` (mutações admin, players, home raw, etc.) |
| Docs Waitress desactualizados | `waitress_config.py` default 4–8; changelog falou 32 + pool 32 — **defaults no código = 4–8 / pool 20** salvo env | alinhar doc + env de produção |
| ~~Encomenda `Timeout (15s)` em `/api/player/dino-order/species`~~ | ~~`list_gallery_species` → `list_species_public` (catálogo inteiro + multipliers + ícones) + N×`quote()`/`_resolve_species_economy`~~ | **Mitigado (2026-07-25):** vitrine snapshot + meta batch ~20 keys + α/β + cache TTL 30s; UI timeout 20s só safety |

### 1.3 Critérios de sucesso (mensuráveis)

| Métrica | Alvo | Como medir |
|---------|------|------------|
| `GET /api/admin/audit` (1ª página, sem filtros) | p95 **&lt; 2 s**; body JSON; `total` null por default | Network DevTools; log `duration_ms` se existir |
| `GET /api/admin/orders` | p95 **&lt; 2 s**; `total` null; `has_more` bool | já parcialmente OK — regressão em pytest |
| `GET /api/admin/season-pass/orders` | p95 **&lt; 3 s**; sem COUNT | Network + pytest Ops |
| Admin Auditoria / Pedidos / SeasonLand Ops no browser | **zero** `Unexpected token '<'` em uso normal | Console; abrir abas 5× |
| `/api/catalog` / `/api/public/home` sob carga leve | HIT/STALE em header; tipicamente **&lt; 3 s** | Headers `X-Catalog-Cache` / `X-Home-Cache` |
| `GET /api/player/dino-order/species` (aba Encomenda) | p95 **&lt; 2–3 s**; sem timeout 15s no browser | Network DevTools; hard refresh → Encomenda |
| Pool Waitress | sem fila crónica (task queue depth estável) | logs Waitress / diagnostics |

---

## 2. Fases

Ordem obrigatória: **P0 → P1 → P2**. Não saltar para micro-opts enquanto P0 falhar no browser.

Estimativas: **S** ≤ 0,5 dia · **M** 0,5–2 dias · **L** &gt; 2 dias.

---

### Fase P0 — Alto impacto, baixo risco (parar a hemorragia)

#### P0.1 — Admin Auditoria: padrão Pedidos

| | |
|--|--|
| **Sintoma** | Página Auditoria timeout / DOCTYPE / «Carregando…» |
| **Causa** | `admin_list_audit`: `want_total` default **true**; `loadAudit`: `fetch`+`r.json()` e paginação exige `total` |
| **Mudança** | Backend: `include_total` **opt-in** (igual orders). Frontend: `include_total=0` + `fetchJson` + `has_more` / `stepTablePage` |
| **Validar** | pytest: default `total is None` + `has_more`; Network: request sem COUNT lento; UI Prev/Next funciona |
| **Estimativa** | **S** |

#### P0.2 — Fechar SeasonLand Ops (se incompleto)

| | |
|--|--|
| **Sintoma** | Ops fila/claims DOCTYPE |
| **Causa** | COUNT + `r.json()` (já mitigado em código local) |
| **Mudança** | Confirmar `list_season_pass_orders` LIMIT+1; UI `fetchJson`; audit Ops `include_total=0` |
| **Validar** | `pytest …/test_seasonland_delivery_reliability.py::test_ops_list_season_pass_orders_filters` |
| **Estimativa** | **S** (já quase feito) |

#### P0.3 — PIX audit na mesma página Admin

| | |
|--|--|
| **Sintoma** | Aba Auditoria lenta mesmo com audit OK |
| **Causa** | `admin_pix_audit` COUNT default + `stats` full scan; `loadPixAudit` raw JSON |
| **Mudança** | `include_total` opt-in; UI `include_total=0` + `fetchJson` + `has_more`; `include_stats=1` só na 1ª página (offset=0) |
| **Validar** | pytest `test_pix_audit.py` (actualizar asserts se default stats mudar); Network |
| **Estimativa** | **S** |

#### P0.4 — Sync changelog + reinício

| | |
|--|--|
| **Sintoma** | Build instalada sem as correcções |
| **Causa** | `index.html` / serviço estático em memória |
| **Mudança** | nota Unreleased em `version.py` + `python scripts/sync_changelog_md.py`; reiniciar Web Store; hard refresh |
| **Validar** | CHANGELOG reflecte Unreleased; browser sem cache SW antigo |
| **Estimativa** | **S** |

**P0 done quando:** abrir Pedidos + Auditoria + SeasonLand Ops 5× sem DOCTYPE; audit/orders Network &lt; 2–3 s na 1ª página; aba **Encomenda** carrega galeria sem `Timeout (15s)`.

#### P0.5 — Encomenda `/api/player/dino-order/species` (hotspot galeria)

| | |
|--|--|
| **Sintoma** | Aba Encomenda: `Timeout (15s) em /api/player/dino-order/species` |
| **Causa** | `list_gallery_species`: `list_species_public` (todas ACTIVE + multipliers + ícones) + N×`quote()`/`_resolve_species_economy` |
| **Mudança** | Snapshot vitrine + meta batch ~20 keys + preço mínimo α/β; cache TTL 30s; UI timeout 20s só safety |
| **Validar** | pytest gallery cache / avoids list_species_public; hard refresh → Encomenda &lt; 3 s |
| **Estimativa** | **S** |
| **Estado** | ✅ (2026-07-25) |

---

### Fase P1 — Listagens e defaults seguros

#### P1.0 — Catálogo UI: 20 cards/página (DOM)

| | |
|--|--|
| **Sintoma** | Catálogo ~527 itens — scroll/paint lento ao abrir aba |
| **Causa** | Render de todos os cards de uma vez (imagens lazy ajudam pouco se há centenas de nós) |
| **Mudança** | Client-side: `CATALOG_DOM_PAGE_SIZE=20` + Anterior/Próxima sobre lista já filtrada (Itens/Dinos/Kits/Licenças). Mantém `/api/catalog` full + cache/ETag/SWR (intencional). Sem virtual-scroll. |
| **Validar** | Hard refresh → Catálogo → ≤20 cards no DOM + pager; filtro/search volta à pág. 1 |
| **Estimativa** | **S** |
| **Estado** | ✅ (2026-07-25) |

#### P1.1 — Mercado: total opt-in

| | |
|--|--|
| **Sintoma** | Browse/admin market lento |
| **Causa** | `include_total: bool = True` → `query.count()` | `market_listings.py` |
| **Mudança** | Default false; UI `has_more`; filtro steam/status usa índices já existentes |
| **Validar** | Network browse; testes market list |
| **Estimativa** | **M** |

#### P1.2 — Tickets / sugestões / notifications COUNT

| | |
|--|--|
| **Sintoma** | Admin tickets / sugestões lentos com volume |
| **Causa** | `q.count()` / `SELECT COUNT(*)` por listagem |
| **Mudança** | LIMIT+1 / `has_more`; total opt-in |
| **Validar** | pytest tickets/suggestions |
| **Estimativa** | **M** |

#### P1.3 — Migrar `r.json()` críticos restantes

| | |
|--|--|
| **Sintoma** | DOCTYPE em mutações/admin (refund, players, home raw) |
| **Causa** | parse JSON sem `readFetchJson` |
| **Mudança** | Priorizar: home, players list, order actions admin, config save — usar `fetchJson` |
| **Validar** | Simular 502 HTML → mensagem PT, não SyntaxError |
| **Estimativa** | **M** |

#### P1.4 — SeasonLand métricas Ops

| | |
|--|--|
| **Sintoma** | Cards métricas Ops lentos |
| **Causa** | `LIKE 'sp:%'` GROUP BY em `orders` grandes | `season_pass_delivery_metrics` |
| **Mudança** | Restringir a status activos + índice `(status, original_order_id)` **só se** EXPLAIN justificar; ou cache TTL 30–60 s |
| **Validar** | EXPLAIN; Network metrics &lt; 2 s |
| **Estimativa** | **M** |

#### P1.5 — Alinhar docs Waitress/pool à realidade

| | |
|--|--|
| **Sintoma** | Ops configura 32 threads «porque o changelog disse» e docs dizem 4–8 |
| **Causa** | Drift documentação vs `waitress_config` / `db_pool` |
| **Mudança** | Actualizar `ARKSHOP_WEB_CACHE_WAITRESS.md` com defaults reais + env de produção recomendado |
| **Validar** | Doc = código |
| **Estimativa** | **S** |

**P1 done quando:** market + tickets + audit/pix sem COUNT no hot path; 0 SyntaxError DOCTYPE nas rotas admin críticas listadas.

---

### Fase P2 — Observabilidade e carga estrutural

#### P2.1 — Timing por endpoint admin

| | |
|--|--|
| **Sintoma** | «Está lento» sem saber se é DB, pool ou Waitress |
| **Causa** | Falta métrica uniforme |
| **Mudança** | Log estruturado `duration_ms` + `query_ms` / `pool_wait` nos GET admin list |
| **Validar** | Grep logs sob carga |
| **Estimativa** | **M** |

#### P2.2 — Índices só com EXPLAIN

| | |
|--|--|
| **Sintoma** | Queries lentas específicas em prod |
| **Causa** | Prefixo `LIKE '%x%'` / filtros sem índice |
| **Mudança** | Nunca criar índice «por feeling»; EXPLAIN em MariaDB prod → adicionar a `_HOT_PATH_INDEX_SPECS` |
| **Validar** | EXPLAIN type=range/ref; sem DDL no request HTTP |
| **Estimativa** | **L** (iterativo) |

#### P2.3 — Stress test controlado

| | |
|--|--|
| **Sintoma** | Regressões só aparecem com jogadores reais |
| **Causa** | Sem baseline |
| **Mudança** | Estender `docs/load_test_k6.md` a audit/orders/catalog; guardar p95 |
| **Validar** | k6 report antes/depois de cada fase |
| **Estimativa** | **M** |

#### P2.4 — Reduzir N+1 / payloads pesados restantes

| | |
|--|--|
| **Sintoma** | Detalhes/admin ainda pesados em casos edge |
| **Causa** | `SELECT *` / `payload_json` / joins |
| **Mudança** | Caso a caso com budget; preferir lazy |
| **Validar** | pytest + Network payload size |
| **Estimativa** | **L** |

**P2 done quando:** há baseline p95 guardada; novos índices só com EXPLAIN; load test no CI ou runbook.

---

## 3. Dependências operacionais

1. **Reiniciar o processo Web Store** após alterar `index.html` / `app.py` (HTML estático + Python em memória).
2. **Hard refresh** no browser (Ctrl+F5) e, se PWA, actualizar service worker / limpar cache da origem.
3. Índices hot-path: self-heal em background — **não** bloquear request; verificar logs `hot_path_indexes`.
4. Env relevantes (não mudar à cegas): `ARKSHOP_HTTP_THREADS`, `ARKSHOP_DB_POOL_SIZE`, `ARKSHOP_DB_READ_TIMEOUT`, `ARKSHOP_*_CACHE_TTL_SEC`.
5. MariaDB: `wait_timeout` &gt; `pool_recycle`; evitar DDL longo em horário de pico.

---

## 4. Anti-padrões — o que NÃO fazer

- Não «otimizar» CSS/JS minúsculo enquanto admin COUNT(*) ainda default-on.
- Não adicionar Redis / filas / microserviços neste plano.
- Não criar índices compostos sem EXPLAIN em dados reais.
- Não fazer `SELECT COUNT(*)` «só para mostrar Pág. 1/N» em tabelas grandes.
- Não usar `r.json()` cru em listagens admin — usar `fetchJson` / `readFetchJson`.
- Não segurar sessão SQLAlchemy durante RCON / Steam / Mercado Pago.
- Não subir Waitress threads acima do pool sem medir (starvation ↔ timeouts ↔ HTML).
- Não reescrever o frontend inteiro; padronizar o padrão Pedidos (has_more + opt-in total).
- Não marcar «tudo otimizado» no changelog sem critério da §1.3 verde.

---

## 5. Checklist de execução (ordem)

| # | Acção | Fase | Done? |
|---|--------|------|-------|
| 1 | Este documento commitado/presente no repo | — | ✅ |
| 2 | Backend `admin_list_audit` total opt-in | P0.1 | ✅ |
| 3 | UI `loadAudit` → fetchJson + include_total=0 + has_more | P0.1 | ✅ |
| 4 | Confirmar SeasonLand Ops has_more + testes | P0.2 | ✅ (código local; revalidar após reinício) |
| 5 | PIX audit include_total=0 + fetchJson (+ stats só pág. 1) | P0.3 | ☐ |
| 6 | version.py Unreleased + sync CHANGELOG | P0.4 | ✅ |
| 7 | Reiniciar Web Store + hard refresh; validar 3 abas admin | P0 | ☐ (acção do operador) |
| 8 | Catálogo UI paginado 20/página (DOM) | P1.0 | ✅ |
| 9 | Market total opt-in | P1.1 | ☐ |
| 10 | Tickets/suggestions has_more | P1.2 | ☐ |
| 11 | fetchJson nos hotspots restantes | P1.3 | ☐ |
| 12 | Métricas Ops + docs Waitress | P1.4–1.5 | ☐ |
| 13 | Observabilidade + EXPLAIN + k6 | P2 | ☐ |

---

## 6. As 5 primeiras acções que mudam a loja de verdade

1. **Desligar COUNT default** em `/api/admin/audit` (e PIX) — igual Pedidos.  
2. **`loadAudit` / `loadPixAudit` com `fetchJson` + `has_more`** — fim do DOCTYPE nessa página.  
3. **Confirmar SeasonLand Ops** já sem COUNT e com fetchJson (já no working tree).  
4. **Reiniciar Web Store + hard refresh** — sem isto o user continua a ver o JS antigo.  
5. **Só depois:** market + tickets COUNT (P1) — não dispersar antes de P0 verde no browser.

---

## 7. Referências de código

- Padrão bom: `admin_list_orders` + `loadAdminOrders`  
- Padrão bom (Ops): `list_season_pass_orders`, `loadSeasonlandOpsOrders/Audit`  
- Padrão mau (a corrigir em P0): `admin_list_audit` default COUNT; `loadAudit` raw fetch  
- Infra: `db_pool.py`, `ttl_cache.py`, `waitress_config.py`, `_HOT_PATH_INDEX_SPECS`
