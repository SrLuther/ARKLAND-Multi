# Âmbarômetro — Painel de Movimentação Total de Âmbares (ARKLAND Web Store)

| Campo | Valor |
|-------|-------|
| **Status** | 📋 Planejamento — **sem implementação** |
| **Versão do documento** | 1.0 |
| **Data** | 2026-07-03 |
| **Escopo** | Contador público estilo [Impostômetro](https://impostometro.com.br/) para volume acumulado de Âmbares movimentados no ecossistema ARKLAND |
| **Fora de escopo** | Código, migrações SQL definitivas, deploy, alterações no CustomShop |

---

## Sumário executivo

O **Âmbarômetro** é um painel na tela principal da Web Store que exibe, em tempo quase real, o volume total de Âmbares (pontos da moeda simbólica do servidor) que **circularam** por todos os sistemas: doações PIX/cartão, resgates do catálogo web, mercado P2P de dinos, compras in-game via `/shop`, recompensas automáticas, transferências entre jogadores, ajustes administrativos e reembolsos.

Inspirado no Impostômetro brasileiro, o objetivo é **transparência e senso de escala da economia interna** — não exibir saldos individuais, apenas totais agregados e animados.

**Referências de código pesquisadas:**

| Componente | Caminho |
|------------|---------|
| Loja web, pedidos, doações, auditoria geral | `plugin/arkshop_web/app.py` |
| Mercado P2P (compra, reembolso) | `plugin/arkshop_web/market_listings.py` |
| Auditoria do mercado | `plugin/arkshop_web/market_audit.py` |
| Enquetes com recompensa | `plugin/arkshop_web/poll_service.py` |
| Home pública (sem contador hoje) | `GET /api/public/home` em `app.py` |
| Plugin in-game (compras, trade, timed points, RCON) | `plugin/CustomShop/src/` |
| Schema MySQL de referência | `setup_db.sql` |
| Import legado de pontos | `tools/import_legacy_points_additive.py` |

**Lacunas identificadas na pesquisa:** vários fluxos alteram `players.points` **sem** registrar evento em `audit_events`, `market_audit_events` ou `transactions` (ver §4 e §13). O Âmbarômetro completo exige um **ledger unificado** ou instrumentação adicional no CustomShop.

---

## 1. Visão e objetivo (impostômetro de âmbares)

### 1.1 O que é

Um widget fixo ou hero na home (`/`) da ARKLAND Web Store que mostra:

- **Total histórico** de Âmbares movimentados (número grande, animado).
- Opcionalmente: ritmo recente (hoje, últimos 7/30 dias) e breakdown por canal.
- Tom visual alinhado à identidade âmbar (`--amber: #e87820` em `static/index.html`).

### 1.2 Por que existe

| Motivação | Descrição |
|-----------|-----------|
| Transparência | Jogadores veem a escala da economia interna sem acessar admin |
| Engajamento | Número crescente reforça comunidade ativa (efeito “impostômetro”) |
| Confiança | Volume público de doações + circulação complementa a narrativa de “moeda simbólica” já presente em `amber_lore` na home |
| Operação | Base para métricas futuras (picos, sazonalidade, impacto de eventos) |

### 1.3 Princípios de produto

1. **Apenas agregados** — nunca SteamID, nickname ou saldo individual no painel público.
2. **Movimentação, não estoque** — soma o que **passou**, não o saldo total em `players.points`.
3. **Definição explícita** — gross vs net documentados (§2); o número exibido deve ter legenda clara.
4. **Resiliência** — contador não pode derrubar a home se o DB estiver lento; cache obrigatório (§10).

---

## 2. Definição: o que conta como “movimentação”

### 2.1 Métrica principal proposta: **Volume bruto (Gross Turnover)**

Para cada evento econômico, somar **`abs(valor_âmbar)`** ao contador, classificado por canal e data.

**Fórmula base:**

```
volume_bruto_total = Σ |delta_âmbar|  para cada evento no ledger
```

Onde `delta_âmbar` é a variação de saldo atribuível a uma ação identificada (compra, crédito, débito, transferência).

### 2.2 Regras por tipo de fluxo

| Tipo | Exemplo | Contagem gross | Notas |
|------|---------|------------------|-------|
| **Entrada (crédito)** | Doação PIX aprovada | `+points` do pacote | Uma perna |
| **Saída (débito)** | Resgate web de kit | `+points_spent` | Uma perna |
| **Transferência P2P** | Mercado: comprador paga vendedor | `+price` do comprador **e** `+price` do vendedor = **2× price** | Espelha “dinheiro que trocou de mãos” |
| **Trade in-game** | `Shop.Trade` | `+amount` (send) **e** `+amount` (recv) | Já logado em `transactions` como `trade_send` / `trade_recv` |
| **Reembolso** | Cancelamento de pedido | `+refund` (crédito de volta) | Conta como nova movimentação; não desfaz automaticamente o débito original no gross |
| **Ajuste admin** | `admin_player_points_add` | `+amount` (add) ou `+|delta|` (set) | Set usa `abs(after - before)` |
| **Emissão inicial** | `StartingPoints` no primeiro login | **Opcional** — ver §13 Q1 | Hoje não auditado |

### 2.3 Métrica alternativa: **Volume líquido por canal (Net)**

Útil para admin, não recomendado como número hero público:

```
volume_líquido_canal = Σ créditos_canal − Σ débitos_canal
```

Ex.: canal “loja_web” net ≈ 0 se todo resgate for reembolsado (improvável); canal “doações” net = total creditado.

### 2.4 Gross vs Net — qual exibir?

| Métrica | Público hero | Admin |
|---------|--------------|-------|
| **Gross turnover** | ✅ Recomendado (estilo Impostômetro — “tudo que passou”) | ✅ |
| **Net emissão** (soma saldos `players.points`) | ❌ Não — mistura estoque com histórico | ⚠️ Referência apenas |
| **Net por canal** | ❌ | ✅ Breakdown |

**Recomendação:** o Âmbarômetro público usa **gross**. Legenda: *“Total de Âmbares que circularam em transações no ARKLAND (compras, vendas, doações, trocas e ajustes).”*

### 2.5 Dupla contagem intencional vs acidental

| Cenário | Dupla contagem? | Tratamento |
|---------|-----------------|------------|
| Mercado: débito comprador + crédito vendedor | **Intencional** no gross | 2× `price_paid` |
| Resgate web + mesma entrega logada em `transactions.web_deliver_pending` | **Acidental** | Contar **apenas** o débito em `orders.points_spent` / `purchase_created`; ignorar log de entrega (sem movimento de pontos) |
| Reembolso após compra mercado | Comprador +refund, vendedor −parcial | Cada perna soma no gross; par líquido ≠ 0 |
| `Shop.Deliver` / reemissão admin | Sem débito | **Não contar** (entrega gratuita) |
| `admin_reissue` | Sem débito | **Não contar** |

---

## 3. Inventário completo de fontes de transação

Tabela derivada da varredura do repositório (`grep`/`codebase search` em `points`, `amber`, `point_payments`, `market_transactions`, `audit_events`, CustomShop).

| # | Origem / canal | Tabela / store DB | Evento / gatilho | Δ jogador | Instrumentado hoje? | Campo valor |
|---|----------------|-------------------|------------------|-----------|----------------------|-------------|
| 1 | **Doação PIX** | `point_payments` | Webhook MP → `_finalize_pix_payment` → `credited=true` | **+** `points` | ✅ `audit_events` (`pix_credited`, `amount`) | `points`, `amount_brl` |
| 2 | **Doação cartão** | `point_payments` | Mesmo fluxo (`payment_method='card'`) | **+** `points` | ✅ (`pix_credited` genérico) | idem |
| 3 | **Resgate catálogo web** | `orders` + `players` | `POST /api/player/purchase` — débito atômico | **−** `points_spent` | ✅ `audit_events` (`purchase_created`, `payload.price`) | `orders.points_spent` |
| 4 | **Resgate falhou** | `orders` | `purchase_failed` | 0 (rollback débito) | ✅ auditoria | — |
| 5 | **Cancelamento jogador** | `orders` | `POST .../cancel` — pedido PENDENTE | **+** refund | ✅ `order_cancelled` (`price=refund`) | `points_spent` ou catálogo |
| 6 | **Reembolso admin** | `orders` | `POST /api/admin/orders/.../refund` | **+** refund | ✅ `admin_refund` | `_order_refund_amount()` |
| 7 | **Reemissão admin** | `admin_reissues` | `admin_reissue` — **sem débito** | 0 | ✅ auditoria (sem pontos) | — |
| 8 | **Mercado — compra** | `market_transactions` | `purchase_listing()` | Comprador **−**, vendedor **+** `price_paid` | ✅ `market_audit_events` (`MARKET_PURCHASE_COMPLETED`, `points_delta`) | `price_paid`, `fee_amount` (=0 hoje) |
| 9 | **Mercado — claim expirado / reembolso** | `market_audit_events` | `_expire_buyer_claim()` | Comprador **+** refund; vendedor **−** até saldo | ✅ `MARKET_CLAIM_REFUNDED` | `metadata.seller_debited` |
| 10 | **Admin — ajuste saldo (painel jogador)** | `players` | `_admin_player_points_adjust` | **+/−/set** | ✅ `admin_player_points_*` (`delta` no payload) | `delta` |
| 11 | **Admin — API pontos** | `players` | `POST /api/admin/points` (`add`/`set`) | **+/set** | ✅ `admin_points_add` / `admin_points_set` | `amount` |
| 12 | **Enquete comunidade** | `community_poll_votes` + `players` | Voto com `reward_amber > 0` | **+** reward | ⚠️ Sem `audit_events` dedicado | `community_polls.reward_amber` |
| 13 | **Compra in-game `/shop`** | `players` | `ShopStore::BuyItem` / `BuyKit` → `SpendPoints` | **−** price | ❌ **Não** loga em `transactions` nem auditoria web | Preço no `config.json` |
| 14 | **Comando engramas** | `players` | `ShopEngrams` → `SpendPoints` | **−** `EngramasCommandPrice` | ❌ Não auditado | `config` |
| 15 | **Timed Points** | `players` | `TimedPoints.cpp` — tick periódico por grupo | **+** award | ❌ Não auditado | `TimedPointsReward` no config |
| 16 | **Trade in-game** | `transactions` | `Shop.Trade` | **−** sender, **+** receiver | ✅ `trade_send` / `trade_recv` | `amount` |
| 17 | **RCON AddPoints** | `players` | `Shop.AddPoints` | **+/−** delta | ❌ Não chama `LogTransaction` | delta no comando |
| 18 | **RCON SetPoints** | `players` | `Shop.SetPoints` | set absoluto | ❌ Não auditado | — |
| 19 | **Saldo inicial** | `players` | `EnsurePlayer` + `StartingPoints` (INSERT IGNORE) | **+** starting (1×) | ❌ Não auditado | `Settings.StartingPoints` |
| 20 | **Import legado** | `players` | `tools/import_legacy_points_additive.py` | **+** delta CSV | ❌ Script externo | CSV |
| 21 | **Entrega web in-game** | `transactions` | `HttpClient` pós-entrega | 0 pontos | ⚠️ Log `web_deliver_pending` (amount=0 movimento) | Não contar |
| 22 | **RCON Shop.Deliver / GiveKit** | `transactions` | Admin entrega sem cobrar | 0 | Log `web_deliver` / `give_kit` | Não contar |
| 23 | **Contestação** | `disputes` | `order_contested` | 0 até reembolso | ✅ flag apenas | — |
| 24 | **Tickets suporte** | `ticket_service` | Referencia `points_spent` do pedido | 0 direto | N/A | Contexto apenas |

**Cobertura da pesquisa:** todas as rotas e módulos listados no escopo foram inspecionados. **Não existe** contador de volume na home hoje — `GET /api/public/home` retorna `stats` apenas com contagens de catálogo (`items`, `dinos`, `kits`), pacotes, servidores e utilitários (`_catalog_public_stats`).

---

## 4. O que NÃO contar (evitar double count)

| Excluir | Motivo |
|---------|--------|
| `transactions.web_deliver*` / `give_kit` | Entrega física sem movimento de Âmbar |
| `admin_reissue` / novo pedido reemitido | Entrega sem novo débito |
| `purchase_failed` após rollback | Débito não persistiu |
| `point_payments` com `credited=false` | Doação não concluída |
| `orders` com `points_spent=0` e preço catálogo 0 | Resgate gratuito |
| Leitura de saldo (`GET points`, `Shop.GetPoints`) | Não é transação |
| `market_audit_events` **sem** `points_delta` (ex.: `MARKET_LISTING_ACTIVATED`) | Evento operacional, não financeiro |
| Contar **e** `orders.points_spent` **e** `purchase_created.price` no mesmo `order_id` | Mesmo evento — usar **uma** fonte (preferir ledger unificado com `idempotency_key=order_id`) |
| `players.points` SUM como proxy de volume | É estoque agregado, não turnover |
| Reembolso mercado **e** compra original no net | No gross ambos entram; documentar na legenda |

---

## 5. Métricas propostas

### 5.1 Públicas (hero + chips)

| Métrica | Chave API | Descrição |
|---------|-----------|-----------|
| Total histórico gross | `total_gross_all_time` | Soma desde epoch do ledger |
| Hoje (UTC-3) | `total_gross_today` | Reset meia-noite America/Sao_Paulo |
| Últimos 7 dias | `total_gross_7d` | Janela rolante |
| Últimos 30 dias | `total_gross_30d` | Janela rolante |
| Ritmo | `rate_per_hour_24h` | `total_gross_24h / 24` (opcional, animação) |

### 5.2 Por canal (breakdown)

| Canal `channel` | Fontes |
|-----------------|--------|
| `donation` | `point_payments` creditados |
| `shop_web` | Resgates + reembolsos loja web |
| `market` | `market_transactions` + reembolsos claim |
| `ingame_shop` | Compras `/shop` in-game |
| `ingame_other` | Trade, engramas, timed points |
| `admin` | Ajustes admin web + RCON não espelhado |
| `community` | Enquetes |
| `migration` | Import legado (one-shot) |

### 5.3 Derivadas (admin / futuro)

- Pico diário máximo histórico
- Média móvel 7d
- % do volume por canal no mês
- “Âmbares em circulação” (SUM `players.points`) — **separado**, não misturar no hero

---

## 6. Arquitetura

### 6.1 Opções avaliadas

| Abordagem | Prós | Contras |
|-----------|------|---------|
| **A. Sum queries ad-hoc** | Sem schema novo | Lento, lacunas históricas (in-game), dupla contagem frágil |
| **B. Ledger append-only** | Fonte única, idempotente, backfill controlado | Migração + hooks em todos os fluxos |
| **C. Híbrido: ledger + batch backfill** | MVP rápido com dados web; completa in-game depois | Duas fases de manutenção |

**Recomendação:** **C** — MVP com ledger alimentado pelos fluxos web já auditados; Fase 2 instrumenta CustomShop.

### 6.2 Tabela ledger proposta: `amber_ledger`

```sql
-- Referência de planejamento (não executar neste documento)
CREATE TABLE amber_ledger (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  occurred_at     DATETIME(3) NOT NULL,
  channel         VARCHAR(32) NOT NULL,
  event_type      VARCHAR(64) NOT NULL,
  gross_amount    INT NOT NULL,           -- sempre >= 0
  signed_delta    INT NOT NULL,           -- + crédito, − débito
  steam_id        VARCHAR(32) NULL,       -- não expor via API pública
  counterparty_id VARCHAR(32) NULL,
  source_table    VARCHAR(64) NULL,
  source_id       VARCHAR(128) NULL,      -- order_id, payment_id, listing_id…
  idempotency_key VARCHAR(128) NOT NULL,  -- UNIQUE — evita duplicata
  metadata_json   JSON NULL,
  INDEX idx_ledger_time (occurred_at),
  INDEX idx_ledger_channel_time (channel, occurred_at),
  UNIQUE KEY uq_ledger_idempotency (idempotency_key)
);
```

### 6.3 Tabela de agregados: `amber_stats_cache`

| Coluna | Uso |
|--------|-----|
| `stat_key` | ex. `total_gross_all_time` |
| `stat_value` | BIGINT |
| `computed_at` | timestamp |
| `period_start` / `period_end` | para janelas |

Atualização:

1. **Tempo real:** após cada `INSERT` no ledger, `UPDATE` incremental na cache (trigger ou app).
2. **Batch:** job noturno reconcilia soma(ledger) vs cache.

### 6.4 Pontos de instrumentação (hooks)

| Onde | Quando gravar |
|------|---------------|
| `app.py` — `_finalize_pix_payment` (crédito) | `donation` +`gross_amount=points` |
| `app.py` — purchase debit commit | `shop_web` − |
| `app.py` — `_credit_order_refund_tx` | `shop_web` + |
| `market_listings.purchase_listing` | 2 linhas: buyer −, seller + (mesmo `source_id`, idempotency distinta) |
| `market_listings._expire_buyer_claim` | reembolso buyer +, seller − |
| `app.py` — `_admin_player_points_adjust` | `admin` |
| `poll_service` — `_credit_points` após voto | `community` |
| CustomShop — `SpendPoints` / `AddPoints` | `ingame_*` (Fase 2) |

### 6.5 Backfill histórico (MVP)

Ordem sugerida:

1. `point_payments` WHERE `credited=1`
2. `audit_events` WHERE `event_type IN ('purchase_created','order_cancelled','admin_refund','admin_player_points_add',...)`
3. `market_transactions` (+ reembolsos via `market_audit_events` com `MARKET_CLAIM_REFUNDED`)
4. `transactions` WHERE `type IN ('trade_send','trade_recv')`
5. Estimar in-game shop **não** backfillável sem logs — exibir disclaimer ou subcontador “desde vX.X”

---

## 7. UI na home (wireframe textual)

### 7.1 Posicionamento

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logo ARKLAND]                              [Login Steam]       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  🔶 ÂMBARÔMETRO                                         │   │
│   │                                                         │   │
│   │     128.456.789                                         │   │
│   │     Âmbares movimentados desde o início                 │   │
│   │                                                         │   │
│   │  [Hoje: 45.230]  [7 dias: 892.100]  [30 dias: 3,2 mi]   │   │
│   │                                                         │   │
│   │  ▓▓▓▓▓▓▓░░░ Doações 42%  Loja 28%  Mercado 22% …       │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   [Servidores]  [Catálogo]  [Pacotes PIX]  …                    │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Comportamento visual

- **Contador principal:** animação de contagem (odômetro / `requestAnimationFrame`) ao carregar e quando polling detecta aumento.
- **Formato numérico:** separador de milhar `.` (padrão PT-BR já usado em `admin_points` response).
- **Ícone:** reutilizar `_AMBER_ICON_URL` / `amber_lore.image_url`.
- **Mobile:** chips empilhados; número em `clamp(2rem, 8vw, 4rem)`.
- **Acessibilidade:** `aria-live="polite"` no valor; texto estático para leitores de tela.
- **Estado degradado:** se API falhar, ocultar widget ou mostrar “—” sem quebrar restante da home.

### 7.3 Integração com home existente

- Novo bloco renderizado após tagline/descrição, antes de servidores.
- Dados via `fetch('/api/public/amber-stats')` ou campo embutido em `/api/public/home` (`amber_meter: { ... }`) — ver §8.

---

## 8. APIs

### 8.1 Endpoint público recomendado

```
GET /api/public/amber-stats
```

**Resposta 200:**

```json
{
  "ok": true,
  "currency": {
    "singular": "Âmbar",
    "plural": "Âmbares",
    "image_url": "https://…"
  },
  "updated_at": "2026-07-03T22:00:00-03:00",
  "coverage_note": "Inclui doações, loja web e mercado desde 2026-01-01. Compras in-game em breve.",
  "total_gross_all_time": 128456789,
  "total_gross_today": 45230,
  "total_gross_7d": 892100,
  "total_gross_30d": 3200000,
  "channels": {
    "donation": 54000000,
    "shop_web": 36000000,
    "market": 28000000,
    "ingame_shop": null,
    "community": 120000
  },
  "display": {
    "label": "Âmbares movimentados",
    "sublabel": "Todas as transações do cluster ARKLAND"
  }
}
```

### 8.2 Alternativa: estender `/api/public/home`

Adicionar chave `amber_meter` no JSON existente para um único round-trip. Cache compartilhado com endpoint dedicado.

### 8.3 Admin (opcional)

```
GET /api/admin/amber-stats/breakdown?from=&to=&channel=
GET /api/admin/amber-stats/reconcile   -- compara ledger vs fontes
POST /api/admin/amber-stats/rebuild    -- rebuild cache (superadmin)
```

Proteção: `@admin_required`, rate limit, audit log da consulta.

### 8.4 Polling

- Público: `Cache-Control: public, max-age=60`
- Front: refresh a cada 60–120s; animar apenas delta positivo.

---

## 9. Admin breakdown (opcional)

Painel em **Configurações → Economia** ou **Admin → Métricas**:

| Widget | Conteúdo |
|--------|----------|
| Gráfico barras | Volume por canal (7d / 30d) |
| Tabela | Top `event_type` por volume |
| Saúde | Último backfill, drift cache vs ledger |
| Alertas | Pico > 3σ da média; falha de hook |

Reutilizar padrão visual das abas de auditoria (`/api/admin/audit`, mercado).

---

## 10. Performance e cache

| Camada | TTL | Notas |
|--------|-----|-------|
| `amber_stats_cache` | atualização incremental | O(1) leitura pública |
| Redis / memória (opcional) | 60s | Se múltiplas instâncias web |
| CDN | não cachear HTML dinâmico | Apenas API |
| Índices | `(occurred_at)`, `(channel, occurred_at)` | Particionar ledger por ano se > 50M linhas |

**Meta:** `GET /api/public/amber-stats` < 50ms p95 com cache quente.

**Carga de escrita:** estimar picos — mercado + resgates em evento sazonal; batch insert em backfill off-peak.

---

## 11. Privacidade

| Permitido publicamente | Proibido |
|------------------------|----------|
| Totais agregados | SteamID, nomes, saldos individuais |
| % por canal | Ranking de “maiores doadores” sem opt-in |
| Data da última atualização | Histórico de transação identificável |
| Nota de cobertura parcial | Export CSV com PII |

Alinhar à narrativa de doação voluntária e moeda simbólica já presente na home (`tagline`, `description`).

LGPD: dados agregados irreversíveis em geral não são dados pessoais; evitar granularidade que permita reidentificação (ex.: único doador do dia).

---

## 12. Fases MVP vs completo

### Fase MVP (2–3 sprints)

- [ ] Tabela `amber_ledger` + `amber_stats_cache`
- [ ] Hooks: doações, resgates web, reembolsos, mercado (compra + claim refund), admin web
- [ ] Backfill de `point_payments`, `orders`, `market_transactions`, `audit_events` elegíveis
- [ ] `GET /api/public/amber-stats` + widget home com contador animado
- [ ] Legenda de cobertura (“não inclui compras in-game ainda”)

### Fase Completa

- [ ] CustomShop: `LogTransaction` em BuyItem/BuyKit, TimedPoints, Engramas, AddPoints/SetPoints
- [ ] Canal `ingame_shop` no breakdown
- [ ] Reconciliador noturno + alertas admin
- [ ] Embutir em `/api/public/home`
- [ ] Opcional: webhook interno para animação SSE

### Fase Stretch

- Comparativo mês a mês; evento sazonal overlay; export público anual “Relatório de circulação”.

---

## 13. Perguntas abertas para discussão

1. **StartingPoints conta no Âmbarômetro?** Emissão ao criar jogador infla o número sem “transação” real. Contar como `migration/emission` ou excluir?

2. **Gross 2× no mercado/trade** está alinhado com a expectativa da comunidade (estilo Impostômetro) ou preferem contar só `price_paid` uma vez?

3. **Reembolsos somam no gross** (compra + reembolso = 2× valor) ou implementar **par líquido** (`net_gross` separado)?

4. **Data epoch:** contador desde sempre (com backfill parcial) ou desde data de lançamento do feature (número menor, mais honesto)?

5. **Compras in-game sem histórico:** exibir subtotal “web only” até Fase 2 ou estimar via diff de saldos (impreciso)?

6. **Import legado** (`import_legacy_points_additive`) entra uma vez como `migration` ou fica fora do narrativo público?

7. **Visibilidade do breakdown por canal** na home pública — transparência total ou só o número hero (breakdown só admin)?

8. **Animação agressiva** (contador sempre subindo) vs atualização discreta — risco de parecer “gamificação” em contexto de doação?

9. **`admin_player_points_set`** pode gerar `delta=0` — ignorar ou registrar evento com gross 0?

10. **Multi-servidor / cluster:** um único Âmbarômetro global (DB `arkland_shop` já centralizado) ou por `server_id` no futuro?

11. **Sincronização com Impostômetro real** — deseja-se copy textual/humor ou tom só técnico ARKLAND?

12. **fee_amount** no mercado hoje é sempre 0 — planejar canal `market_fee` para taxa futura?

---

## 14. Exemplo de números e fórmula

### 14.1 Cenário ilustrativo (24h)

| Evento | Valor | Gross contribuição |
|--------|-------|-------------------|
| Doação PIX 10.000 Âmbares | +10.000 | 10.000 |
| Resgate kit web 2.500 | −2.500 | 2.500 |
| Mercado: venda 50.000 | −50.000 comprador, +50.000 vendedor | 100.000 |
| Trade in-game 1.000 | −1.000 / +1.000 | 2.000 |
| Reembolso pedido 2.500 | +2.500 | 2.500 |
| Enquete 100 jogadores × 50 | +5.000 | 5.000 |
| **Total gross do dia** | | **122.000** |

### 14.2 Fórmula implementável (pseudocódigo)

```text
function record_movement(channel, event_type, signed_delta, idempotency_key, ...):
    if exists idempotency_key: return
    gross = abs(signed_delta)
    if gross == 0: return
    INSERT amber_ledger (..., gross_amount=gross, signed_delta=signed_delta)
    UPDATE amber_stats_cache SET stat_value = stat_value + gross
      WHERE stat_key IN ('total_gross_all_time', 'total_gross_today', ...)

function public_total():
    return cache['total_gross_all_time']  -- fallback: SUM(gross_amount) FROM amber_ledger
```

### 14.3 Exemplo de resposta visual

> **127.384.920** Âmbares movimentados  
> *Hoje: +122.000 · 7d: 4,1 mi · Doações 44% · Loja 30% · Mercado 24%*

---

## Apêndice A — Mapa de `event_type` úteis para backfill

### `audit_events` (loja web)

| event_type | Movimento |
|------------|-----------|
| `pix_credited` | +`amount` |
| `purchase_created` | −`price` (payload) |
| `order_cancelled` | +`price` |
| `admin_refund` | +`refunded` |
| `admin_player_points_add` | +`delta` |
| `admin_player_points_subtract` | −`delta` → gross abs |
| `admin_player_points_set` | abs(`delta`) |
| `admin_points_add` | +`amount` |
| `admin_points_set` | abs delta implícito |

### `market_audit_events`

| event_type | Movimento |
|------------|-----------|
| `MARKET_PURCHASE_COMPLETED` | `points_delta` (comprador, negativo) + linha espelho vendedor |
| `MARKET_CLAIM_REFUNDED` | +refund comprador; −`seller_debited` |

### `transactions` (CustomShop)

| type | Movimento |
|------|-----------|
| `trade_send` | gross `amount` |
| `trade_recv` | gross `amount` |

---

## Apêndice B — Resultado da varredura do codebase

| Área pesquisada | Status |
|-----------------|--------|
| `plugin/arkshop_web` — orders, point_payments, audit | ✅ Mapeado |
| `market_listings` / `market_transactions` | ✅ Mapeado |
| `poll_service` — reward_amber | ✅ Mapeado |
| `ticket_service` | ✅ Sem fluxo de pontos próprio |
| `GET /api/public/home` | ✅ Sem contador de volume hoje |
| `CustomShop` — shop, timed points, trade, RCON | ✅ Mapeado; lacunas de log |
| `setup_db.sql` — players, transactions, market | ✅ Mapeado |
| `tools/import_legacy_points_additive.py` | ✅ Mapeado |
| `stat_points_asb.py` | ℹ️ Pontos de **stats de dino** (breeding), não moeda — fora do escopo |
| `artifacts/store`, `artifacts/api-server` | ℹ️ Legado/artefato; produção usa `arkshop_web` |

**Conclusão:** todas as fontes de transação **conhecidas no codebase atual** foram inventariadas. Fluxos **sem telemetria** (compras in-game, timed points, RCON Add/Set, starting points) estão documentados como lacunas para Fase 2.

---

*Documento de planejamento — nenhuma alteração de código foi realizada.*
