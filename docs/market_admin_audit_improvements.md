# Plano de Melhorias — Auditoria Admin e Suporte do Mercado (ARKLAND Multi)

| Campo | Valor |
|-------|-------|
| **Status** | 📋 Planejamento — **sem implementação** |
| **Versão do documento** | 1.0 |
| **Data** | 2026-07-03 |
| **Escopo** | Auditoria, moderação, suporte e métricas do Comércio P2P (cryopod) |
| **Fora de escopo** | Código, migrações SQL definitivas, deploy |

---

## Sumário executivo

A auditoria admin do Mercado de Dinos existe em backend (`market_audit_events`, `market_audit_event()`) e tem uma aba dedicada no painel **Comércio → Admin → Auditoria Mercado**, mas a experiência operacional é **muito inferior** à auditoria geral da loja (`/api/admin/audit`) e à vitrine do vendedor (v1.9.192). O admin vê uma tabela plana sem detalhe, sem paginação, sem contexto de listing/claim/cryo, sem ligação com tickets e sem dashboard de abusos.

Este documento propõe evoluir o ecossistema em direção a um **centro de operações do mercado**: timeline rastreável por `market_trace_id`, moderação com contexto, suporte integrado e paridade web ↔ in-game.

**Referências de código atuais:**

| Componente | Caminho |
|------------|---------|
| Auditoria mercado | `plugin/arkshop_web/market_audit.py` |
| Modelo `MarketAuditEvent` | `plugin/arkshop_web/app.py` |
| Eventos e listagem | `plugin/arkshop_web/market_listings.py` |
| Rotas admin | `plugin/arkshop_web/market_routes.py` |
| UI aba Auditoria | `plugin/arkshop_web/static/index.html` (`page-market-admin`, tab `audit`) |
| Notificações vendedor | `plugin/arkshop_web/market_notify.py` |
| Moderação in-game | `plugin/CustomShop/src/ShopMarket.cpp` (`/mercado_admin`) |
| Auditoria loja (padrão ouro) | `plugin/arkshop_web/app.py` (`/api/admin/audit`) |
| Tickets | `plugin/arkshop_web/ticket_service.py` |

---

## 1. Diagnóstico do estado atual

### 1.1 O que já existe e funciona

#### Backend de auditoria dedicada

- Tabela `market_audit_events` com campos estruturados: `market_trace_id`, `event_type`, `severity`, `steam_id`, `counterparty_steam_id`, `listing_id`, `vault_id`, `claim_id`, `blob_hash`, valores econômicos (`computed_base_value`, `effective_price`, `points_delta`, `points_before`, `points_after`), versões (`parser_version`, `plugin_version`, `web_version`), `source`, `metadata_json`, `created_at`.
- Função central `market_audit_event()` em `market_audit.py` com log estruturado.
- Helper `mirror_critical_to_shop_audit()` definido mas **não utilizado** em nenhum fluxo — eventos CRITICAL do mercado não aparecem na auditoria geral da loja.

#### Tipos de evento já registrados (amostra)

| Evento | Contexto |
|--------|----------|
| `MARKET_DISPLAY_NAME_CHANGED` | Vitrine do vendedor |
| `MARKET_UPLOAD_CONFIRMED` / `MARKET_SPECIES_PENDING` | Upload cryopod |
| `MARKET_LISTING_ACTIVATED` / `MARKET_LISTING_PRICE_SET` | Preço e ativação |
| `MARKET_PURCHASE_COMPLETED` | Compra |
| `MARKET_CLAIM_*` | Resgate, expiração, reembolso |
| `MARKET_LISTING_PAUSED` / `WITHDRAW_REQUESTED` | Ações do vendedor |
| `MARKET_LISTING_ADMIN_REMOVED` / `ADMIN_PRICE` / `ADMIN_FLAGGED` | Moderação |
| `MARKET_LISTING_CLASSIFIED` / `PROMOTED` / `RECOMPUTED` | Classificação e economia |
| `MARKET_SELLER_LISTING_SOLD` / `BUYER_CLAIMED` / `ADMIN_FLAGGED` / `ADMIN_REMOVED` | Vitrine vendedor (v1.9.192) |
| `MARKET_SELLER_RECLAIM_DELIVERED` | Devolução após remoção admin |

#### APIs admin existentes

| Endpoint | Função |
|----------|--------|
| `GET /api/market/admin/audit` | Lista eventos (filtros: `event_type`, `steam_id`, `market_trace_id`; limit até 500) |
| `GET /api/market/admin/audit/export` | CSV (máx. 500 linhas, 8 colunas) |
| `POST .../listings/<id>/remove` | Remove + claim ao vendedor |
| `PATCH .../listings/<id>/price` | Ajuste de preço admin |
| `POST .../listings/<id>/flag` | Flag + pausa |
| `POST /api/market/plugin/admin` | Paridade `/mercado_admin` in-game |
| `GET .../species/pending-classification` | Fila de classificação |
| `POST .../listings/classify` (+ bulk) | Homologação de espécie |

#### UI web admin

- Aba **Comércio → Admin** com três tabs: Espécies, Classificar, **Auditoria Mercado**.
- Moderação **Remover** e **Flag** embutida nos cards de browse/vitrine (apenas admins logados).
- Aba auditoria mercado: 3 filtros de texto livre + tabela de 7 colunas, **sem paginação**, **sem modal de detalhe**, **sem links** para listing/jogador.

#### Vendedor (v1.9.192 — ver §11)

- `GET /api/market/my/audit` — subconjunto `SELLER_VITRINE_EVENT_TYPES`.
- Notificações in-app + labels amigáveis na Minha Loja.
- Admin **não** tem equivalente enriquecido.

#### Moderação in-game

- `/mercado_admin remover|preco|flag <id>` → mesma API plugin que a web.
- Sem consulta de histórico, sem preview de stats, sem listagem de anúncios suspeitos.

#### Tickets (parcial)

- Sistema de tickets implementado (`support_tickets`, categoria `mercado`).
- Campo `order_id` no ticket; **sem** `listing_id` / `claim_id` / `market_trace_id` estruturados.
- Links em mensagens são URLs livres (`links_json`), não referências tipadas ao mercado.

### 1.2 Lacunas críticas (pain points)

| # | Lacuna | Impacto operacional |
|---|--------|---------------------|
| L1 | UI auditoria mercado é tabela crua vs. auditoria loja (paginação, busca `q`, modal detalhe, total) | Admin não investiga incidentes com eficiência |
| L2 | `steam_id` no filtro só bate no campo `steam_id` do evento — em moderação o admin fica em `steam_id`, vendedor em `metadata.seller` | Busca por vendedor falha em muitos eventos |
| L3 | Sem filtro por `listing_id`, `claim_id`, `severity`, intervalo de datas, `source` | Impossível isolar um caso |
| L4 | CSV limitado a 500 registros e 8 colunas — sem `metadata`, `counterparty`, `blob_hash` | Export inútil para análise forense |
| L5 | Sem endpoint `GET /api/market/admin/audit/<id>` nem timeline por listing/trace | Não há “história completa” de um anúncio |
| L6 | Sem painel admin de **listagens** (busca global, status, flagados, vendidos) | Moderação só no browse público ou fila PENDING |
| L7 | Sem preview admin de metadata cryo (stats, imprint, blob_hash, breakdown) fora do card de classificação | Suporte não valida “dino prometido vs. entregue” |
| L8 | Sem ações em lote (flag/remove múltiplos, pausar vitrine inteira) | Abuso em escala exige cliques repetidos |
| L9 | Sem ban/suspend comércio por vendedor (`commerce_enabled` só toggle manual implícito) | Reincidência sem ferramenta |
| L10 | Tickets mercado sem vínculo estruturado → admin abre 4 abas (audit shop, audit mercado, comércio, jogadores) | MTTR alto em disputas P2P |
| L11 | `mirror_critical_to_shop_audit` não wired | Alertas staff na auditoria unificada não disparam |
| L12 | Sem métricas/dashboard (volume, flags, top vendedores, claims expirados) | Gestão reativa, não proativa |
| L13 | Paridade in-game limitada a 3 comandos sem `listar`/`info` | Moderação in-game cega |
| L14 | Eventos admin web gravam em `audit_events` genérico **e** `market_audit_events` de forma **inconsistente** (ex.: remove na rota HTTP chama só `audit_event("MARKET_LISTING_ADMIN_REMOVED")` na shop audit, enquanto `market_listings` grava o evento correto em `market_audit_events`) | Duplicidade/confusão entre trilhas |

### 1.3 Comparativo: Auditoria Loja vs. Auditoria Mercado

| Recurso | `/api/admin/audit` (loja) | `/api/market/admin/audit` (mercado) |
|---------|---------------------------|-------------------------------------|
| Paginação com `total` | ✅ | ❌ |
| Busca textual `q` | ✅ | ❌ |
| Filtro severity | ✅ | ❌ (campo existe no DB) |
| Detalhe por ID | ✅ `GET .../audit/<id>` | ❌ |
| Modal na UI | ✅ `viewAuditDetail` | ❌ |
| Export | — | CSV parcial (500) |
| Actor vs. target | `actor_steam_id` / `target_steam_id` | `steam_id` / `counterparty_steam_id` (sem convenção documentada) |
| IP / User-Agent | ✅ | ❌ |

**Conclusão:** o backend do mercado é **mais rico** que o da loja em campos de domínio, mas a **superfície admin** está uma geração atrás da auditoria shop e da experiência vendedor v1.9.192.

---

## 2. Personas

### 2.1 Admin (dono / superuser)

- **Objetivo:** governança da economia, espécies, decisões finais em abusos graves, auditoria forense.
- **Necessidades:** dashboard, export completo, correlacionar trace_id → listing → transação → pontos Âmbar, ban de vendedor, override de preço sem teto.
- **Ferramentas atuais:** aba Comércio Admin (espécies, classificar, auditoria básica), auditoria loja, jogadores, tickets.
- **Frustração:** “sei que o evento existe no banco, mas não consigo ver o contexto na UI”.

### 2.2 Moderador (staff in-game + web limitada)

- **Objetivo:** remover anúncios abusivos, ajustar preços absurdos, sinalizar listings, classificar espécies novas.
- **Necessidades:** fila de suspeitos, ações rápidas in-game (`/mercado_admin`), motivo obrigatório, histórico do que já fez.
- **Ferramentas atuais:** `/mercado_admin`, botões Flag/Remover no browse (se admin web), tab Classificar.
- **Frustração:** sem listar anúncios por vendedor ou preço fora do teto; sem ver se vendedor é reincidente.

### 2.3 Suporte (equipe tickets — `support_steamids`)

- **Objetivo:** resolver ticket categoria `mercado` (claim falhou, dino errado, timer, reembolso, moderação contestada).
- **Necessidades:** timeline unificada listing + claims + audit + ticket; abrir ticket pré-preenchido a partir de listing; ver saldo Âmbar e claims pendentes.
- **Ferramentas atuais:** fila tickets admin, auditoria mercado (pobre), browse mercado.
- **Frustração:** jogador manda “anúncio #1234” e o atendente caça manualmente em várias telas.

### 2.4 Vendedor (referência — já melhorado em v1.9.192)

- **Objetivo:** vender, acompanhar vendas e ações da moderação.
- **Já tem:** notificações in-app, `/api/market/my/audit`, labels PT-BR na vitrine.
- **Gap residual:** não vê eventos técnicos (upload, classificação) — por design; admin deveria ver o superset.

---

## 3. Melhorias por área

### 3.1 Auditoria e eventos

#### Campos e convenções

| Melhoria | Descrição |
|----------|-----------|
| **Padronizar papéis** | Documentar e aplicar: `steam_id` = ator primário (comprador, vendedor ou admin conforme evento); `counterparty_steam_id` = outra parte. Incluir sempre `seller_steam_id` e `buyer_steam_id` em `metadata` quando aplicável. |
| **Actor admin explícito** | Em todos os eventos `MARKET_LISTING_ADMIN_*`: `steam_id` = admin, `counterparty_steam_id` = seller; espelhar em `metadata.admin_steam_id`. |
| **Status antes/depois** | Adicionar `listing_status_before` / `listing_status_after` em metadata (ou colunas dedicadas) em transições. |
| **Request context** | Gravar `ip_address`, `user_agent`, `admin_session` em metadata para ações web admin (padrão `_audit_event`). |
| **Mensagem legível** | Campo derivado `summary_pt` em metadata para UI (ex.: “Admin X removeu anúncio #42 do vendedor Y — motivo: preço abusivo”). |
| **Espelhar CRITICAL** | Wire `mirror_critical_to_shop_audit` em: claim expirado sem reembolso, upload rejeitado, falha de entrega repetida, remoção admin. |

#### Novos tipos de evento propostos

| Evento | Quando |
|--------|--------|
| `MARKET_SELLER_COMMERCE_SUSPENDED` | Admin desabilita comércio do jogador |
| `MARKET_SELLER_COMMERCE_RESTORED` | Restauração |
| `MARKET_VITRINE_FROZEN` | Todos listings ACTIVE → PAUSED em lote |
| `MARKET_LISTING_ADMIN_UNFLAG` | Reversão de flag |
| `MARKET_LISTING_BULK_ADMIN_ACTION` | Resumo de ação em lote |
| `MARKET_TICKET_LINKED` | Ticket vinculado a listing/claim |
| `MARKET_STAFF_ALERT_ACK` | Staff marcou alerta como visto |
| `MARKET_CLAIM_DELIVERY_FAILED` | Plugin reportou erro de spawn (se ainda não granular) |

#### Filtros da API/UI

- `listing_id`, `claim_id`, `vault_id`, `blob_hash`
- `severity` (INFO, WARN, CRITICAL)
- `source` (web, plugin, system, admin)
- `event_type` com prefixo `MARKET_%` ou multi-select
- `date_from` / `date_to` (ISO UTC)
- `steam_id` com modo **any** (ator, contraparte, seller/buyer em metadata)
- `market_trace_id` (já existe)
- Busca textual `q` em `metadata_json`, `event_type`, IDs numéricos

#### Export

- CSV/JSON com **todas** as colunas + `metadata` parseado
- Export assíncrono para >10k linhas (job + download link) — Could
- Presets: “moderação últimos 30 dias”, “compras de jogador X”

### 3.2 Listagens (gestão admin)

| Melhoria | Descrição |
|----------|-----------|
| **Painel Listagens Admin** | Nova tab ou sub-seção: tabela paginada de **todos** os listings (não só ACTIVE nem só PENDING). |
| **Busca** | Por `listing_id`, `seller_steam_id`, `market_display_name`, `species_key`, `dino_display_name`, `custom_name`, status. |
| **Filtros rápidos** | ACTIVE, PAUSED, PENDING_CLASSIFICATION, SOLD, AWAITING_CLAIM, flagados (`metadata.admin_flagged`), removidos. |
| **Ordenação** | Preço, data, desvio % vs. sugerido, nível, mutations. |
| **Preview cryo** | Modal com: stats, imprint, mutations, breakdown economia, `blob_hash`, `parser_version`, link para vault (admin-only, sem expor blob). |
| **Bulk actions** | Selecionar N → flag, remove, pause, export CSV. |
| **Deep link** | URL `?page=market-admin&tab=listings&listing_id=123` abre detalhe. |

### 3.3 Moderação

| Ação | Estado atual | Melhoria proposta |
|------|--------------|-------------------|
| Flag | ✅ web + in-game; pausa opcional | Motivo **obrigatório** para staff; categorias (preço abusivo, espécie errada, spam, golpe); histórico de flags por vendedor |
| Remove | ✅ devolve cryo via claim SELLER | Confirmar modal com resumo do dino; opção “silencioso” (sem notificação) — só superadmin |
| Price fix | ✅ admin ignora teto | UI web para PATCH price (hoje só in-game ou API direta); registrar `price_before` em metadata |
| Unflag / restaurar | ❌ | Reativar listing PAUSED por flag |
| Ban seller | ❌ | `commerce_enabled=false` + pausar todos ACTIVE + auditoria + notificação |
| Freeze vitrine | ❌ | Pausar todos os anúncios de um `seller_steam_id` com um clique |
| Escalonamento | ❌ | Após N flags em 7 dias → alerta staff automático |

### 3.4 Suporte (tickets)

| Melhoria | Descrição |
|----------|-----------|
| **Vínculo estruturado** | Campos em `support_tickets`: `listing_id`, `claim_id`, `market_trace_id` (nullable, indexados). |
| **Criar ticket do listing** | Botão admin “Abrir ticket” pré-preenche categoria `mercado`, subject, links. |
| **Timeline unificada** | `GET /api/market/admin/listings/<id>/timeline` = listing + claims + transactions + `market_audit_events` + tickets relacionados + saldo Âmbar snapshot. |
| **Widget no ticket admin** | Se categoria `mercado`, painel lateral com card do listing e últimos 10 eventos. |
| **Jogador** | Ao abrir ticket categoria mercado, campo opcional “ID do anúncio” com validação. |
| **Playbooks embutidos** | Links para docs: claim expirado, duped, classificação pendente. |

### 3.5 Métricas e dashboard

**KPIs sugeridos (período configurável: 24h / 7d / 30d):**

| Métrica | Fonte |
|---------|-------|
| Volume de vendas (count + Âmbar) | `market_transactions` |
| Listings ativos / pausados / pendentes classificação | `market_listings` |
| Taxa de conversão browse → compra | eventos + listings |
| Claims pendentes / expirados / falhas entrega | `market_claims` |
| Ações de moderação (flag/remove/price) | `market_audit_events` |
| Top vendedores (volume, flags) | join listings + audit |
| Top espécies vendidas | transactions + species |
| Desvio médio preço vs. sugerido | listings ACTIVE |
| Tempo médio classificação PENDING → DRAFT | audit timestamps |

**Visualização:** cards no topo da aba Comércio Admin + gráfico simples (sparklines) — Could usar canvas/CSS sem lib pesada.

### 3.6 Alertas e notificações staff

| Alerta | Gatilho | Canal |
|--------|---------|-------|
| Novo listing PENDING alto valor | `computed_base_value` > threshold | Notificação in-app staff + Discord opcional |
| Preço acima do teto tentado | evento de rejeição / override admin | Staff |
| Claim expirando em <2h | job periódico | Staff + opcional jogador |
| Múltiplos flags mesmo vendedor | regra 3+ em 7d | Staff |
| Upload rejeitado repetido | mesmo `blob_hash` ou steam_id | Staff |
| Ticket mercado urgente | prioridade + categoria | Já existe parcialmente — reforçar fila |

**Implementação:** estender `notification_service` com tipos `market_staff_*` para `admin_steamids` + `support_steamids`; configurável em settings.

### 3.7 Paridade in-game + web

| Comando / UI | Web equivalente |
|--------------|-----------------|
| `/mercado_admin listar [steam\|flagged]` | GET admin listings filtrado |
| `/mercado_admin info <id>` | GET listing detail + últimos 3 audit |
| `/mercado_admin remover` | POST remove |
| `/mercado_admin preco` | PATCH price |
| `/mercado_admin flag` | POST flag |
| **Novo:** `/mercado_admin congelar <steam>` | POST freeze vitrine |
| Feedback in-game | Resumo legível (não só “OK listing #N”) |

---

## 4. Wireframes textuais e fluxos

### 4.1 Fluxo: Investigar disputa de compra (listing #1842)

```
[Jogador abre ticket categoria mercado, informa listing #1842]
        │
        ▼
[Suporte: Tickets Admin → #5678]
        │
        ├─► Painel lateral: Listing #1842 (Rex, L337, ACTIVE→SOLD)
        │       • Vendedor: VitrineAlpha (Steam …123)
        │       • Comprador: …456
        │       • Claim #901 PENDENTE (expira em 5h)
        │
        ├─► [Ver timeline completa] → modal ou página
        │       2026-07-01 MARKET_UPLOAD_CONFIRMED
        │       2026-07-01 MARKET_LISTING_CLASSIFIED (admin …789)
        │       2026-07-02 MARKET_LISTING_ACTIVATED
        │       2026-07-03 MARKET_PURCHASE_COMPLETED
        │       2026-07-03 MARKET_SELLER_LISTING_SOLD
        │       trace_id: mkt-abc-123 (clicável → filtra audit)
        │
        └─► Ações: [Reenviar claim] [Ajustar preço] [Abrir auditoria mercado filtrada]
```

### 4.2 Wireframe: Aba Auditoria Mercado (proposta)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Comércio Admin › Auditoria Mercado                    [Export CSV ▼] [↺]   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Busca: [____________________]  Tipo: [Todos ▼]  Sev: [▼]  De: [__] Até:[__]│
│ Steam: [___________] (ator/qualquer)  Listing: [____]  Trace: [_________] │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────┬─────────────────────────┬─────┬──────────┬─────────┬────────┐ │
│ │ Data     │ Evento (label PT)       │ Sev │ Listing  │ Ator    │ [🔍]   │ │
│ ├──────────┼─────────────────────────┼─────┼──────────┼─────────┼────────┤ │
│ │ 03/07 14 │ Compra concluída        │ INFO│ #1842 →  │ …456    │ [🔍]   │ │
│ │ 03/07 14 │ Venda (vitrine)         │ INFO│ #1842    │ …123    │ [🔍]   │ │
│ │ 03/07 10 │ Anúncio sinalizado      │ WARN│ #1842    │ admin…  │ [🔍]   │ │
│ └──────────┴─────────────────────────┴─────┴──────────┴─────────┴────────┘ │
│                    ◀ Pág. 2/15 (1.423 eventos) ▶                           │
└─────────────────────────────────────────────────────────────────────────────┘

Modal 🔍 Detalhe evento #99887
┌─────────────────────────────────────────────────────────────────────────────┐
│ MARKET_PURCHASE_COMPLETED · INFO · 2026-07-03T14:22:01Z                    │
│ trace: mkt-abc-123  [Copiar] [Filtrar por trace] [Ver listing #1842]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Comprador: …456    Vendedor: …123    Preço: 12.500 Âmbar                   │
│ Pontos: 50.000 → 37.500 (comprador)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ metadata JSON (tree view colapsável)                                        │
│ [Ver timeline do listing] [Criar ticket]                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Wireframe: Painel Listagens Admin (nova tab)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Tab: [Espécies] [Classificar] [Listagens] [Auditoria] [Métricas]           │
├─────────────────────────────────────────────────────────────────────────────┤
│ [🔍 busca…] Status:[Todos▼] Flagged:[☑]  Ordenar:[Mais recentes▼]          │
│ ☐ Selecionar todos   [Flag lote] [Pausar lote] [Exportar]                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ☐ #1842  Rex Tek  L337  ACTIVE  12.500 Âmbar  VitrineAlpha  ⚑ flagged      │
│      [Detalhe] [Flag] [Remover] [Preço] [Timeline] [Ticket]                │
│ ☐ #1840  Anky   L150  PAUSED   3.200 Âmbar  …                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Fluxo: Moderação in-game rápida

```
Admin digita: /mercado_admin listar flagged
        │
        ▼
Chat: 3 anúncios flagged — #1842 Rex 12500, #1830 Giga 999999, …
        │
        ▼
/mercado_admin info 1830
        │
        ▼
Chat: #1830 Giga L450 — preço 999999 (sugerido 85000, teto 170000) — flag: preço abusivo
        │
        ▼
/mercado_admin preco 1830 170000
        │
        ▼
Chat: Preço ajustado para 170.000 Âmbar (pausado: não)
```

---

## 5. Modelo de dados proposto

### 5.1 Evolução de `market_audit_events` (colunas novas — opcional fase 2)

| Coluna | Tipo | Notas |
|--------|------|-------|
| `listing_status_before` | VARCHAR(32) NULL | Desnormalização para queries |
| `listing_status_after` | VARCHAR(32) NULL | |
| `actor_steam_id` | VARCHAR(32) NULL INDEX | Alias explícito do ator (admin/mod) |
| `summary` | VARCHAR(512) NULL | Texto PT para listagens |
| `ticket_id` | INT NULL INDEX | Quando evento ligado a ticket |

*Alternativa mínima:* manter só `metadata_json` com chaves padronizadas — menos migração, queries mais lentas.

### 5.2 Metadados padronizados (`metadata_json`)

```json
{
  "summary_pt": "Compra do anúncio #1842 por 12.500 Âmbar",
  "seller_steam_id": "7656119…",
  "buyer_steam_id": "7656119…",
  "admin_steam_id": "7656119…",
  "reason": "preço abusivo",
  "reason_code": "PRICE_ABUSE",
  "listing_status_before": "ACTIVE",
  "listing_status_after": "PAUSED",
  "price_before": 999999,
  "price_after": 170000,
  "ip_address": "203.0.113.1",
  "user_agent": "Mozilla/5.0…"
}
```

### 5.3 `support_tickets` — extensão

| Coluna | Tipo |
|--------|------|
| `listing_id` | INT NULL INDEX |
| `claim_id` | INT NULL INDEX |
| `market_trace_id` | VARCHAR(64) NULL INDEX |

### 5.4 Nova tabela opcional: `market_staff_alerts`

| Coluna | Tipo |
|--------|------|
| `id` | PK |
| `alert_type` | VARCHAR(64) |
| `severity` | VARCHAR(16) |
| `listing_id` | INT NULL |
| `steam_id` | VARCHAR(32) NULL |
| `payload_json` | TEXT |
| `acknowledged_by` | VARCHAR(32) NULL |
| `acknowledged_at` | DATETIME NULL |
| `created_at` | DATETIME |

### 5.5 Nova tabela opcional: `market_seller_sanctions`

| Coluna | Tipo |
|--------|------|
| `id` | PK |
| `seller_steam_id` | VARCHAR(32) INDEX |
| `sanction_type` | ENUM freeze, suspend_commerce, warning |
| `reason` | TEXT |
| `admin_steam_id` | VARCHAR(32) |
| `expires_at` | DATETIME NULL |
| `created_at` | DATETIME |

### 5.6 Catálogo completo de `event_type` (target state)

**Existentes** — manter. **Novos** — adicionar conforme §3.1.

**Mapeamento UI (labels PT admin)** — espelhar padrão `_marketVitrineAuditLabel` do vendedor, mas superset:

| event_type | Label admin |
|------------|-------------|
| `MARKET_PURCHASE_COMPLETED` | Compra concluída |
| `MARKET_LISTING_ADMIN_FLAGGED` | Moderação: sinalizado |
| `MARKET_LISTING_ADMIN_REMOVED` | Moderação: removido |
| `MARKET_SELLER_LISTING_SOLD` | Venda (notificação vendedor) |
| … | (tabela completa na implementação) |

---

## 6. APIs necessárias

### 6.1 Auditoria (evolução)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/market/admin/audit` | **Estender:** `listing_id`, `claim_id`, `severity`, `source`, `date_from`, `date_to`, `q`, `steam_id_mode=any`, `total` + paginação |
| GET | `/api/market/admin/audit/<id>` | Detalhe de um evento |
| GET | `/api/market/admin/audit/export` | Colunas completas; `format=csv\|json`; cursor para >500 |
| GET | `/api/market/admin/audit/event-types` | Lista tipos + labels PT (para dropdown) |
| GET | `/api/market/admin/trace/<market_trace_id>/timeline` | Todos eventos do trace ordenados |

### 6.2 Listings admin

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/market/admin/listings` | Lista paginada com filtros avançados |
| GET | `/api/market/admin/listings/<id>` | Detalhe completo + metadata cryo resumida |
| GET | `/api/market/admin/listings/<id>/timeline` | Listing + claims + tx + audit + tickets |
| POST | `/api/market/admin/listings/bulk` | `{ action, listing_ids[], reason? }` |
| POST | `/api/market/admin/listings/<id>/unflag` | Reverter flag |

### 6.3 Vendedor / sanções

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/market/admin/sellers/<steam_id>` | Perfil comércio + stats + flags + listings |
| POST | `/api/market/admin/sellers/<steam_id>/suspend` | `commerce_enabled=false` + opcional freeze |
| POST | `/api/market/admin/sellers/<steam_id>/restore` | Reverter |
| POST | `/api/market/admin/sellers/<steam_id>/freeze-vitrine` | Pausar todos ACTIVE |

### 6.4 Métricas

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/market/admin/metrics` | `?period=7d` → KPIs §3.5 |
| GET | `/api/market/admin/metrics/moderation` | Série temporal flags/removes |

### 6.5 Alertas staff

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/market/admin/alerts` | Fila não reconhecida |
| POST | `/api/market/admin/alerts/<id>/ack` | Marcar visto |

### 6.6 Tickets (extensão)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/admin/tickets` | Aceitar `listing_id`, `claim_id`, `market_trace_id` |
| GET | `/api/admin/tickets/<id>/market-context` | Snapshot listing + timeline resumida |

### 6.7 Plugin (in-game)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/market/plugin/admin` | **Estender** `action`: `listar`, `info`, `congelar` |
| GET | `/api/market/plugin/admin/listings` | Opcional: query por `flagged`, `seller_steam_id` |

### 6.8 Consistência com auditoria loja

- Unificar gravação: ações admin mercado devem chamar **apenas** `market_audit_event()` com metadados completos; `audit_event()` shop opcional via `mirror_critical_to_shop_audit` para CRITICAL.
- Remover duplicata confusa na rota HTTP `market_admin_listing_remove` que chama `audit_event("MARKET_LISTING_ADMIN_REMOVED")` sem substituir o evento de mercado (hoje o evento correto vem de `market_listings.admin_remove_listing`).

---

## 7. UI: ASM (Server Manager) vs. Web Admin

### 7.1 Web Admin (`index.html`) — **canal principal**

Toda operação de moderação, auditoria, tickets e métricas deve viver na Web Store:

| Área | Mudanças |
|------|----------|
| `page-market-admin` | Novas tabs: **Listagens**, **Métricas**; auditoria reformulada |
| Auditoria mercado | Paridade com `page-audit`: paginação, modal detalhe, filtros |
| Listagens | Tabela + bulk + modal cryo preview |
| Tickets admin | Widget mercado quando `listing_id` presente |
| Jogadores admin | Link “Ver vitrine mercado” → `/api/market/admin/sellers/<steam_id>` |
| Browse mercado | Manter Flag/Remover; adicionar “Timeline” para admin |

### 7.2 ASM / TEK (`src/app_tek.py`, páginas TEK)

O Server Manager **não** deve duplicar toda a UI de mercado. Papéis sugeridos:

| Função | Onde |
|--------|------|
| Ops servidor, RCON, sync catálogo | ASM/TEK (já existe) |
| Link rápido “Abrir Comércio Admin na web” | ASM — botão com URL configurável |
| Métricas de saúde API mercado | ASM — opcional: ping `/api/health` + contagem claims pendentes |
| Auditoria forense completa | **Somente Web** |
| Moderação diária | **Web** + in-game |

**Could (fase tardia):** painel TEK “Resumo Mercado” read-only (KPIs via API) para quem já está no ASM sem abrir browser.

### 7.3 CustomShop (in-game)

- Estender `ShopMarket.cpp` com subcomandos §3.7.
- Mensagens de chat mais descritivas (limite de caracteres ARK).
- Não implementar auditoria completa in-game — apenas gatilhos que abrem URL na web (Could: `!mercado` link com token one-time).

---

## 8. Priorização MoSCoW

### Must (MVP operacional)

| # | Item |
|---|------|
| M1 | `GET /api/market/admin/audit` com paginação, `total`, filtros `listing_id`, `severity`, datas |
| M2 | `GET /api/market/admin/audit/<id>` + modal detalhe na UI |
| M3 | Labels PT e colunas úteis na tabela (ator, contraparte, resumo) |
| M4 | `GET /api/market/admin/listings/<id>/timeline` |
| M5 | Padronizar metadata (`seller_steam_id`, `summary_pt`, status before/after) em eventos novos e nos principais existentes |
| M6 | Painel admin listagens paginado com busca por ID/seller/status |
| M7 | Preview cryo no detalhe do listing (stats, breakdown, blob_hash) |
| M8 | Vínculo ticket ↔ listing (`listing_id` em `support_tickets` + UI widget) |
| M9 | Export CSV completo (metadata expandido, limite razoável 5k com aviso) |
| M10 | Corrigir consistência `audit_event` vs `market_audit_event` nas rotas admin |

### Should

| # | Item |
|---|------|
| S1 | Dashboard métricas básicas (§3.5) |
| S2 | Bulk flag/pause/remove |
| S3 | `unflag` + histórico flags por vendedor |
| S4 | Alertas staff in-app (PENDING alto valor, claim expirando) |
| S5 | `GET /api/market/admin/sellers/<steam_id>` |
| S6 | Busca `q` textual na auditoria |
| S7 | Wire `mirror_critical_to_shop_audit` |
| S8 | UI admin para PATCH price (hoje falta botão dedicado) |
| S9 | `/mercado_admin listar` e `info` |
| S10 | Deep links entre auditoria ↔ listing ↔ ticket |

### Could

| # | Item |
|---|------|
| C1 | Export assíncrono >10k eventos |
| C2 | Tabela `market_staff_alerts` dedicada |
| C3 | `market_seller_sanctions` com expiração |
| C4 | Gráficos tendência no dashboard |
| C5 | Painel read-only no ASM/TEK |
| C6 | Discord alerts mercado (separado de tickets) |
| C7 | Motivo obrigatório categorizado (enum) |
| C8 | Comparação blob_hash comprador vs. vault |

### Won't (esta iniciativa)

| # | Item | Motivo |
|---|------|--------|
| W1 | Substituir `market_audit_events` por só `audit_events` | Perda de campos de domínio |
| W2 | Replay / reversão automática de compras | Risco econômico; manual via admin |
| W3 | Editor de blob cryopod na web | Segurança e complexidade |
| W4 | Moderação ML automática de preços | Fora de escopo |
| W5 | App mobile dedicado | Web responsiva basta |

---

## 9. Fases de implementação

### Fase 1 — Fundação auditoria (1–2 sprints)

**Objetivo:** admin consegue investigar um caso ponta a ponta.

- APIs M1, M2, M4, M10
- UI auditoria: paginação, modal, filtros listing/trace/datas
- Metadata padronizada nos eventos de compra, moderação e claim
- Testes: `test_market_admin_audit.py` (filtros, detalhe, timeline)

**Critério de aceite:** dado `listing_id=1842`, admin abre timeline e vê ≥5 eventos ordenados com links.

### Fase 2 — Gestão de listagens e cryo preview (1 sprint)

- API listagens admin paginada (M6, M7)
- Tab Listagens na UI
- Bulk pause/flag (S2 parcial)
- Export CSV completo (M9)

**Critério de aceite:** buscar seller por SteamID retorna todos listings; modal mostra stats e breakdown.

### Fase 3 — Suporte integrado (1 sprint)

- Migração `support_tickets.listing_id`, `claim_id`, `market_trace_id`
- Widget ticket + botão “Criar ticket” no listing
- Campo listing_id no formulário jogador (categoria mercado)

**Critério de aceite:** ticket #N mostra card do listing sem sair da tela.

### Fase 4 — Moderação avançada e vendedor (1 sprint)

- Suspend/restore commerce, freeze vitrine (APIs §6.3)
- unflag, histórico flags (S3)
- `/mercado_admin listar|info` (S9)
- Alertas staff básicos (S4)

### Fase 5 — Métricas e polish (1 sprint)

- Dashboard KPIs (S1)
- `mirror_critical` (S7)
- Labels PT completos, deep links (S10)
- Documentação operacional (playbooks suporte)

**Estimativa total:** 5–6 sprints incrementais, entregando valor desde Fase 1.

---

## 10. Perguntas abertas para discussão

1. **Escopo de visibilidade:** moderadores veem auditoria mercado completa ou só eventos de moderação + listings flagados?
2. **Motivo obrigatório:** flag/remove exigem motivo texto livre, enum (`PRICE_ABUSE`, `WRONG_SPECIES`, …) ou ambos?
3. **Notificação ao vendedor:** toda ação admin gera notificação (como hoje) ou suspendemos em ajuste de preço silencioso?
4. **Ban de comércio:** `commerce_enabled=false` basta ou precisamos bloquear também `/enviar` no plugin com mensagem customizada?
5. **Freeze vitrine:** pausar ACTIVE apenas ou incluir DRAFT? Claims em andimento são afetados?
6. **Retenção de audit:** quanto tempo manter `market_audit_events` online vs. arquivo frio? (GDPR / tamanho DB)
7. **Export:** limite máximo por download e quem pode exportar (só superadmin vs. todo staff)?
8. **Tickets:** `listing_id` obrigatório para categoria `mercado` ou opcional?
9. **Paridade in-game:** quantos comandos `/mercado_admin` são aceitáveis antes de forçar web para ações complexas?
10. **Alertas Discord:** canal separado de tickets ou mesmo webhook?
11. **ASM/TEK:** investimos em painel read-only no desktop ou 100% web é suficiente?
12. **Unificação auditorias:** eventos mercado CRITICAL devem aparecer na aba Auditoria geral da loja por padrão?

---

## 11. Referência — v1.9.192 (seller notifications/audit)

Lançado em **2026-07-03** (`APP_VERSION = 1.9.192`). Mudanças relevantes como **baseline** para paridade admin:

| Entrega v1.9.192 | Implementação | Gap admin |
|------------------|---------------|-----------|
| Notificações in-app ao vendedor (venda, resgate, flag, remove) | `market_notify.py` + `notification_service` | Staff não recebe alertas simétricos |
| Registro vitrine em Minha Loja | `GET /api/market/my/audit` + `SELLER_VITRINE_EVENT_TYPES` | Admin não tem audit legível nem labels PT |
| Sininho abre Minha Loja | `link_type=market` em notificações | Admin sem deep link para listing/timeline |
| Eventos duplicados vitrine | `MARKET_SELLER_*` além de `MARKET_LISTING_*` / `MARKET_PURCHASE_*` | UI admin lista só `event_type` cru — não agrupa “mesma ação, duas visões” |
| Moderação web + `/mercado_admin` | v1.9.188 + notificações v1.9.192 | Falta histórico admin, motivo estruturado, busca por vendedor |

**Lição para o plano:** o trabalho de UX feito para o **vendedor** (labels, notificações, audit filtrado) deve ser **replicado e expandido** para o **staff**, com superset de dados e ferramentas de ação — não apenas a tabela técnica atual.

**Arquivos tocados em v1.9.192 (referência):**

- `plugin/arkshop_web/market_notify.py` (novo)
- `plugin/arkshop_web/market_listings.py` (integração notify + `list_seller_vitrine_audit_events`)
- `plugin/arkshop_web/market_routes.py` (`/api/market/my/audit`)
- `plugin/arkshop_web/static/index.html` (`_marketVitrineAuditLabel`, tabela vitrine)
- `plugin/arkshop_web/tests/test_market_listings.py` (cobertura audit vendedor)

---

## Apêndice A — Mapa rápido de arquivos a alterar (implementação futura)

| Fase | Arquivos prováveis |
|------|-------------------|
| 1 | `market_listings.py`, `market_routes.py`, `market_audit.py`, `index.html`, `tests/test_market_*` |
| 2 | `market_listings.py`, `market_routes.py`, `index.html` |
| 3 | `ticket_service.py`, `app.py` (modelo), `index.html` (tickets-admin) |
| 4 | `market_listings.py`, `ShopMarket.cpp`, `notification_service.py` |
| 5 | `market_routes.py` (metrics), `index.html`, `docs/` playbooks |

---

## Apêndice B — Relação com outros documentos

- `docs/PROJETO_MERCADO_CRYOPOD.md` — fluxo cryo, eventos de reclaim, economia
- `docs/PROJETO_SISTEMA_SUPORTE_TICKETS.md` — visão tickets (parcialmente implementada)
- `docs/UI_PATTERNS.md` — padrões visuais para novas tabs/modais

---

*Documento gerado para planejamento. Nenhuma alteração de código foi feita.*
