# ARKBANK — Tesouraria do Cluster (especificação de planejamento)


| Campo | Valor |
| ----- | ----- |
| **Status** | MVP implementado (ledger + hooks + aba admin) — polish Fase 2 |
| **Versão do documento** | 0.4 |
| **Data** | 13 de julho de 2026 |
| **Escopo** | Visão de produto, modelo econômico, mapeamento de código, dados, UI, edge cases, redesign do sorteio, fases e perguntas abertas |
| **Fora de escopo (este doc)** | Soft transparency pública; patrocínio sorteio opção B; instrumentação catálogo in-game |
| **Moeda** | Âmbar (`players.points`) |
| **Fuso canônico** | America/Sao_Paulo (UTC−3) |
| **Changelog do doc** | **0.4** — MVP: arkbank_service, hooks web, casal→ARKBANK (opção A), outbox TimedPoints, aba admin; **0.3** — retenção catálogo **20**/reembolso **80**; **0.2** — doação R$ 1 = 1.000 Âmbar |

> **Ver também:** [`ECONOMIA_ARKLAND.md`](./ECONOMIA_ARKLAND.md), [`PROJETO_ECONOMIA_IDEAL.md`](./PROJETO_ECONOMIA_IDEAL.md), [`SORTEIO_DOACOES_SPEC.md`](./SORTEIO_DOACOES_SPEC.md), [`ENCOMENDA_DINO_SPEC.md`](./ENCOMENDA_DINO_SPEC.md), [`ambarmeter_spec.md`](./ambarmeter_spec.md), [`TRIBO_REPARTICAO_MERCADO.md`](./TRIBO_REPARTICAO_MERCADO.md).

---

## Sumário executivo

O **ARKBANK** é a **tesouraria simbólica do cluster**: um saldo único (pode ser **negativo**) que recebe o Âmbar que hoje “some” em sumidouros administrados — catálogo, fatia de casal do mercado e encomendas — **e também** uma fatia simbólica das **doações PIX/cartão confirmadas**, e **financia automaticamente** os ganhos por tempo online (`TimedPointsReward` + bônus de licença).

| Pergunta | Resposta (intenção de produto) |
| -------- | ------------------------------ |
| **O que é?** | Ledger + saldo da “casa” do ARKLAND — não é carteira de jogador |
| **Para que serve?** | Tornar transparente a saúde da economia; ligar gastos da loja **e doações** à emissão por tempo |
| **Entra (inflow)** | 100% do gasto no catálogo; na desistência/auto-cancel, **retenção 20%** permanece no banco (clawback 80%); 40% da venda em casal; 100% do pagamento de encomenda; **doação confirmada: R$ 1,00 → +1.000 Âmbar** |
| **Sai (outflow)** | Todo Âmbar creditado por tick de TimedPoints (base + licenças), **sem teto** |
| **Pode ficar negativo?** | **Sim** — outflows nunca são bloqueados por saldo do banco |
| **O que muda no sorteio?** | A fatia 40% do casal **deixa de alimentar** o pote; o sorteio precisa de novo funding (opções §7). **Doações continuam** a alimentar o pote como hoje (`prize_amber_from_donations`) |
| **O que muda na doação?** | **Nada** no pacote do jogador (Âmbares, números, VIPDoacao, etc.) — só há **crédito adicional paralelo** no ARKBANK |

**Tagline interna:** *“O que a loja e a doação recolhem, o tempo devolve — a tesouraria mostra o pulso do cluster.”*

**Princípio inegociável v1:** o jogador **sempre** recebe o TimedPoints configurado; o ARKBANK **nunca** é um soft-cap disfarçado.

---

## 1. Visão & narrativa

### 1.1 Para jogadores

Hoje, quando alguém gasta Âmbar no catálogo ou numa encomenda, a sensação é de **desaparecimento**: o saldo cai e ponto. No casal do mercado, 40% do valor pedido alimenta o sorteio — um destino nobre, mas opaco para quem só “vê sumir”.

O ARKBANK muda a história:

- O cluster passa a ter um **cofre coletivo visível** (mesmo que só para staff no MVP).
- Gastos na loja e na encomenda **sustentam** a emissão por tempo: jogar gera Âmbar porque a economia realimenta a tesouraria.
- **Doações confirmadas** (PIX ou cartão) também **injetam Âmbar na tesouraria** — além dos benefícios que o doador já recebe hoje. Esse Âmbar “da casa” **volta depois** como TimedPoints (ganhos por tempo) para quem está online.
- Saldo negativo não é “falência do servidor” — é um **sinal de saúde**: a emissão por tempo está a superar os sumidouros (ou vice-versa). Narrativa: *“a casa está a investir em quem joga”* vs *“a casa está a acumular”*.

Mensagem curta para UI futura (soft transparency):

> **Tesouraria ARKLAND** — Âmbar da loja, das encomendas e das doações volta como recompensa por tempo online.

### 1.2 Para admins / operação

O ARKBANK é um **painel de pulso econômico**:

| Sinal | Interpretação operacional |
| ----- | ------------------------- |
| Saldo ↑ sustentado | Sumidouros > emissão — possível excesso de sinks ou pouca população online |
| Saldo ↓ / negativo crescente | Emissão TimedPoints > inflows — típico em pico de online ou preços baixos |
| Pico de inflow sem outflow | Evento de compra / restock / promoção de catálogo |
| Outflow estável, inflow cai | Economia “parada” (poucas compras) com jogadores ainda online |

Não substitui o Âmbarômetro (`amber_ledger` / gross turnover): o Âmbarômetro mede **volume que passou**; o ARKBANK mede **estoque da casa** e **fluxo líquido casa ↔ jogadores**.

### 1.3 Metáfora de produto

```
┌──────────────────────────────────────────────────────────────────┐
│                     JOGADORES (carteiras)                         │
│   TimedPoints ──► +Âmbar     Catálogo / Encomenda / Casal ──► −Âmbar │
│   Doação PIX/cartão ──► +Âmbar (pacote do doador; modelo atual)   │
└──────────────▲─────────────────────────────┬─────────────────────┘
               │ outflow                     │ inflow (destinos “casa”)
               │ (sempre honrado)            │  + doação → +1.000 Âmbar/R$
┌──────────────┴─────────────────────────────▼─────────────────────┐
│                         ARKBANK (tesouraria)                       │
│   balance ∈ ℤ  (pode ser < 0)                                      │
│   ledger append-only · audit admin · painéis                       │
└────────────────────────────────────────────────────────────────────┘
```

Narrativa da doação: o real doado **já** compra benefícios ao jogador (pacote de Âmbares, números do sorteio, etc.). Em paralelo, a tesouraria recebe **1.000 Âmbar por real** — stock simbólico que o TimedPoints devolverá ao cluster ao longo do tempo.

---

## 2. Modelo econômico

### 2.1 Equações do ledger

Definimos:

- \(B_t\) — saldo ARKBANK no instante \(t\) (inteiro, pode ser negativo)
- \(I\) — inflows no período
- \(O\) — outflows no período

```
B_{t+1} = B_t + I − O
```

**Inflows (v1 — intenção):**

| Código proposto | Evento | Valor creditado no ARKBANK |
| --------------- | ------ | -------------------------- |
| `catalog_spend` | Compra no catálogo (web e, idealmente, in-game `/shop`) | \(+\text{price}\) integral |
| `market_pair_share` | Venda em casal concluída (checkout) | \(+\texttt{pair_prize_contribution}(P1,P2)\) = \(round(0{,}40 \times S)\) |
| `dino_order_pay` | Checkout de encomenda | \(+\text{total}\) integral |
| `donation_brl` | Doação PIX/cartão **confirmada** (`PointPayment` → `APROVADO` + `credited`) | \(+\texttt{round}(\text{amount\_brl} \times 1000)\) — **R$ 1,00 = 1.000 Âmbar** |

**Outflows (v1 — intenção):**

| Código proposto | Evento | Valor debitado do ARKBANK |
| --------------- | ------ | ------------------------- |
| `timed_reward` | Tick TimedPoints (por jogador, por mapa) | \(-\text{award}\) exatamente o creditado em `players.points` |

**Reversões / correções (mesma magnitude, sinal oposto, tipo distinto):**

| Código | Quando |
| ------ | ------ |
| `catalog_refund_clawback` | Desistência/auto-cancel catálogo — clawback **80%** do `catalog_spend` (retenção **20%** fica no ARKBANK; ver §6.1) |
| `dino_order_refund_clawback` | Rejeição/cancelamento de encomenda com reembolso integral |
| `donation_brl_clawback` | Estorno/chargeback MP (`ESTORNADO`) após crédito ARKBANK — ver §6.10 |
| `market_pair_no_clawback` | Desistência de claim de casal — **hoje o pote não estorna**; proposta: ARKBANK também **não estorna** o 40% (alinhar ao comportamento atual do sorteio) |
| `admin_adjust` | Top-up / correção manual com trilha de auditoria |

### 2.2 Relação com carteiras de jogador

O ARKBANK **não** é uma conta Steam nem linha em `players.points` de um “bot”. É um **saldo de sistema** em tabela própria. Movimentos de jogador continuam a alterar `players.points` como hoje; o ARKBANK é um **espelho contábil** dos fluxos “casa”.

Invariant desejável (não enforçado como hard lock no MVP):

```
ΔB ≈ Σ inflows_casa − Σ timed_rewards
```

(ajustado por refunds/admin).

### 2.3 Pode ser negativo — por design

**Regra:** se \(O > B + I\) no tick, \(B\) fica negativo. **Nenhum** TimedPoints é cortado, atrasado ou parcial por causa do banco.

Implicações de produto:

- UI admin deve normalizar o negativo (cor âmbar/alerta, não “erro vermelho de falha de sistema”).
- Alertas opcionais: “tesouraria < −X por Y dias” → revisar preços / TimedPoints / população.
- Copy: *“Saldo negativo significa que o cluster está a emitir mais Âmbar por tempo do que a recolher na loja — intencional e permitido.”*

### 2.4 Relação com o Sorteio (estado atual → estado ARKBANK)

**Hoje (produção):**

- Casal: comprador paga \(Y = round(0{,}60 \times S)\); vendedor recebe \(Y\); sistema credita \(round(0{,}40 \times S)\) em `lottery_campaigns.prize_amber_from_market` via `contribute_market_pair_to_prize`.
- Desistência/expiração de claim: reembolso \(round(0{,}60 \times Y)\) ao comprador; **pote sem estorno**.
- Prêmio do sorteio também acumula: base, rollover, compras de números em Âmbar, doações (`prize_amber_from_donations`).

**Com ARKBANK:**

- O crédito \(0{,}40 \times S\) **muda de destino**: `prize_amber_from_market` → **ARKBANK** (ou deixa de incrementar o pote e passa a incrementar o banco).
- O sorteio **perde uma fonte recorrente** ligada ao volume de casais no mercado.
- Fontes restantes do pote (sem redesign): base admin, rollover, compra/reserva de números, contribuições de doação PIX.

**Impacto esperado:** campanhas com poucos números comprados e sem doações grandes ficam **mais magras** se não houver redesign (§7).

### 2.5 O que *não* entra no ARKBANK (v1)

Para evitar ambiguidade com o Âmbarômetro e com P2P puro:

| Fluxo | Entra no ARKBANK? | Motivo |
| ----- | ----------------- | ------ |
| Mercado solteiro (P2P integral) | Não | Transferência jogador↔jogador |
| Split de tribo sobre \(Y\) | Não | Redistribuição entre jogadores |
| Compra de números do sorteio | Não (v1) | Continua a alimentar o pote / ledger lottery |
| Prêmio do sorteio pago ao vencedor | Não como inflow; outflow do *pote*, não do ARKBANK (salvo opção B §7) |
| Enquetes (`record_poll_reward`) | Não (v1) | Emissão promocional separada |
| Âmbares do **pacote** creditados ao doador (`payment.points`) | Não como inflow ARKBANK | Monetização → carteira do doador (inalterado) |
| Contribuição doação → pote (`prize_amber_from_donations`, R$ 1 = +100 Âmbar) | Não | Continua no sorteio; **paralelo** ao `donation_brl` do banco |
| Admin `Shop.AddPoints` / adjust | Não automático | Só via `admin_adjust` explícito no ARKBANK |

### 2.6 Doação confirmada → ARKBANK (aprovado)

**Conversão canónica (v1):**

```
arkbank_credit = round(amount_brl × 1000)   # R$ 1,00 doado = 1.000 Âmbar
```

Base: `PointPayment.amount_brl` no momento em que o pagamento fica **APROVADO** e `credited=True` — **não** usar `payment.points` (pacote do jogador tem bônus e não é linear com o real).

**O que *não* muda** (modelo de doação atual intacto):

| Benefício atual | Continua? |
| --------------- | --------- |
| Crédito de Âmbares do pacote ao jogador (`_add_player_points_tx` / `payment.points`) | Sim |
| Âmbarômetro `record_donation(..., points=payment.points)` | Sim |
| Sorteio `on_donation_credited` — números (R$ 5 = 1) + pote (R$ 1 = +100 Âmbar) | Sim |
| Qualquer VIPDoacao / perks / UI de pacotes | Sim |

**Exemplo (pacote R$ 5 → 10.000 Âmbares ao jogador):**

| Destino | Valor |
| ------- | ----- |
| Carteira do doador | +10.000 Âmbar (pacote) |
| Pote do sorteio (se campanha ativa) | +500 Âmbar (`5 × 100`) |
| **ARKBANK** | **+5.000 Âmbar** (`5 × 1000`) |

Três destinos **independentes**; o crédito ao banco **não** reduz o pacote nem o pote.

## 3. Pontos de entrada mapeados ao código existente

### 3.1 Ledger / observabilidade atual

| Artefato | Papel |
| -------- | ----- |
| `plugin/arkshop_web/amber_ledger.py` | Ledger de **gross turnover** (Âmbarômetro): `record_movement`, `record_shop_debit`, `record_shop_refund`, `record_market_purchase`, `record_lottery_market_pair_contribution`, etc. |
| `ensure_amber_schema` | Cria `amber_ledger` + `amber_stats_cache` |
| `docs/ambarmeter_spec.md` | Spec do contador público |

**Nota de arquitetura:** o ARKBANK pode (a) **reutilizar** `amber_ledger` com `channel='arkbank'` e um saldo derivado, ou (b) ter tabelas próprias `arkbank_balance` + `arkbank_transactions` e **espelhar** eventos no Âmbarômetro. Recomendação de planejamento: **(b) saldo próprio + espelho opcional no amber_ledger** para não misturar “estoque da casa” com “volume bruto”.

### 3.2 Catálogo — gasto integral → ARKBANK

| Camada | Arquivo / função | O que acontece hoje |
| ------ | ---------------- | ------------------- |
| Web Store compra | `plugin/arkshop_web/app.py` — fluxo de criação de pedido (~`_create_order` / purchase path ~7744+) | Debita jogador; `record_shop_debit(...)` |
| Desistência **80%** | `app.py` — `_ORDER_DESIST_REFUND_FACTOR = 0.80`, `_order_desist_refund_amount`, cancel paths ~7928 / ~9169 | Credita **80%** ao jogador; `record_shop_refund`; retenção **20%** |
| Auto-cancel 48h | `app.py` ~9032+ / `expire_stale_pending_orders` | Mesma política **80%** |
| In-game `/shop` | `plugin/CustomShop/src/` (`ShopStore.cpp`, `ShopPoints.cpp`) | Debita `players.points` **sem** passar pelo Flask; **lacuna** para ARKBANK se só instrumentarmos a web |
| Regulamento | `docs/REGULAMENTO_SERVIDOR.md` §8.4.2; `static/regulamento_v1_3.html`; copy em `index.html` | Norma jogador |

**Hook proposto (web — compra):** imediatamente após débito bem-sucedido e `record_shop_debit`, chamar `arkbank.credit(catalog_spend, amount=points_spent, ...)`.

**Hook proposto (web — desistência/auto-cancel):** após crédito 80% ao jogador, `arkbank.debit(catalog_refund_clawback, amount=refunded)` — restam **20%** de \(P\) no banco. **Ledger ARKBANK ainda não existe** — a taxa 20% já está em produção no reembolso ao jogador; o crédito/clawback no banco fica para a Fase 1.

**Hook proposto (in-game):** endpoint ou fila (RCON/HTTP bridge) notificando gasto de catálogo — **fase 2**, se o volume in-game for material; MVP pode documentar “só web” se a maioria das compras premium for web.

### 3.3 Mercado casal — 40% → ARKBANK (em vez do pote)

| Camada | Arquivo / função | Hoje |
| ------ | ---------------- | ---- |
| Constantes | `plugin/arkshop_web/market_pair.py` — `PAIR_PRIZE_FACTOR = 0.40`, `pair_prize_contribution` | Calcula pote |
| Checkout | `market_listings.py` — `purchase_listing` (~1224+); calcula `prize_contrib` (~1281) | |
| Crédito ao sorteio | `lottery_service.contribute_market_pair_to_prize` (~1383) | `UPDATE prize_amber_from_market += amt` + `record_lottery_market_pair_contribution` |
| Claim refund 60% | `pair_claim_refund`, `_expire_buyer_claim` / desistência | Pote **sem** estorno |
| Testes | `plugin/arkshop_web/tests/test_market_pair.py` | Asserts em `prize_amber_from_market` |

**Mudança planejada (conceitual):**

```
# hoje
contribute_market_pair_to_prize(db, amount=prize_contrib, ...)

# ARKBANK
arkbank.credit(market_pair_share, amount=prize_contrib, ref_id=tx_id, ...)
# contribute_market_pair_to_prize → no-op / removido / feature-flag off
```

Renomear semanticamente `PAIR_PRIZE_FACTOR` → `PAIR_BANK_FACTOR` (ou manter o nome e mudar só o destino) — decisão de implementação.

### 3.4 Encomenda de dino — pagamento integral → ARKBANK

| Camada | Arquivo / função | Hoje |
| ------ | ---------------- | ---- |
| Checkout | `dino_order_service.checkout` (~606) | `_debit_fn(db, steam_id, total)` + insert `orders` com `points_spent=total` |
| Rejeição | `reject_order` (~729) | `_credit_fn` reembolso integral = `points_spent` |
| Rotas | `dino_order_routes.py` | HTTP |
| Spec | `docs/ENCOMENDA_DINO_SPEC.md` | Produto |

**Hook:** após débito em `checkout` → `arkbank.credit(dino_order_pay, ...)`. Em `reject_order` (e quaisquer cancelamentos com refund) → `arkbank.debit` clawback do mesmo valor.

### 3.5 TimedPoints — outflow automático (nunca bloqueado)

| Camada | Arquivo / função | Hoje |
| ------ | ---------------- | ---- |
| Config | `TimedPointsReward` em `plugin/CustomShop/configs/config.json` | `Enabled`, `Interval`, `Groups.*.Amount`, `StackRewards` |
| Tick | `plugin/CustomShop/src/TimedPoints.cpp` — `Tick()` | Soma grupos (ou best), `ShopPoints::AddPoints(sid, award)`, chat notify |
| Sync web→plugin | `src/shop_integration.py`, `src/catalog_sync.py` | Propaga `TimedPointsReward` |
| Bônus licença (docs) | `app.py` — `LICENSE_TIMED_BONUS`; entitlements/VIP no plugin | Empilhados nos grupos do config |

**Lacuna crítica:** o tick vive **só no processo do mapa (DLL)**. A Web Store **não vê** cada award hoje. Para debitar o ARKBANK é preciso um destes desenhos:

| Opção | Descrição | Prós | Contras |
| ----- | --------- | ---- | ------- |
| **A — HTTP fire-and-forget** | Após `AddPoints` bem-sucedido, POST para Web Store `/api/internal/arkbank/timed` | Tempo real | Rede, auth, falha = desync |
| **B — Tabela outbox no MySQL** | Plugin INSERT `arkbank_timed_outbox`; worker Flask consome | Idempotente, resiliente | Atraso curto; schema no DB do shop |
| **C — Agregação por ciclo** | Plugin grava total por mapa/ciclo; worker aplica 1 linha | Menos linhas | Menos auditoria por jogador |

**Recomendação de planejamento:** **B (outbox)** — alinhado a multi-mapa, idempotência e ao facto de TimedPoints já usar o mesmo MySQL de pontos.

**Regra multi-mapa:** cada mapa com CustomShop corre o próprio `Tick()`. Um jogador em dois mapas (improvável simultâneo, mas possível em cluster) gera **dois awards** → dois débitos ARKBANK. Isso é **correto** face à emissão real.

### 3.6 Sorteio — o que permanece

| Artefato | Notas |
| -------- | ----- |
| `lottery_service.py` | Campanhas, compra de números, doação→prêmio, draw, rollover |
| `lottery_routes.py` | APIs |
| `prize_amber_from_market` | Coluna fica **congelada** ou só histórica após cutover; novas vendas não incrementam |
| `on_donation_credited` | **Mantém-se** — pote e números **não** são substituídos pelo ARKBANK |
| `docs/SORTEIO_DOACOES_SPEC.md` | Atualizar na fase de implementação (addendum); notar inflow paralelo ao banco |

### 3.7 Doação PIX / cartão confirmada → ARKBANK

Ponto único de confirmação de pagamento (PIX **e** cartão): `_finalize_pix_payment` em `plugin/arkshop_web/app.py` (~8071). Apesar do nome, serve ambos os métodos (`payment_method` ∈ `{pix, card}`).

| Camada | Arquivo / função | Hoje |
| ------ | ---------------- | ---- |
| Pacotes BRL→Âmbar (jogador) | `app.py` — `_DEFAULT_POINT_PACKAGES` (~388+) | Ex.: R$ 5 → 10.000 pts; R$ 75 → 170.000 — **inalterado** |
| Checkout PIX | `POST /api/player/pix/checkout` → `create_pix_payment` | Cria `PointPayment` PENDENTE |
| Checkout cartão | checkout card (~8515+) | Idem; `payment_method=card` |
| **Confirmação (webhook)** | `POST /api/payments/webhook` (~8655) → `fetch_payment` → **`_finalize_pix_payment(..., source="webhook")`** | Caminho principal em produção |
| **Confirmação (poll)** | `GET /api/player/pix/<payment_id>/status` (~8539) → poll MP / retry → **`_finalize_pix_payment`** | Fallback UI enquanto o modal está aberto |
| Crédito ao jogador | Dentro de `_finalize_pix_payment` quando `mapped == "APROVADO"` e `not credited` | `_add_player_points_tx(db, steam_id, payment.points)` |
| Âmbarômetro | `amber_ledger.record_donation(payment_id, steam_id, points=payment.points)` | Volume bruto do pacote |
| Sorteio | `lottery_service.on_donation_credited(..., amount_brl=payment.amount_brl)` | Pote R$ 1 = +100; números R$ 5 = 1 |
| Estorno | `mapped == "ESTORNADO"` → `revoke_lottery_numbers_for_payment` | Números revogados; **hoje não** debita automaticamente o pacote do jogador |

**Hook proposto (único, idempotente):** no mesmo bloco em que `credited` passa a `True` (após `_add_player_points_tx` bem-sucedido), **além** de `record_donation` e `on_donation_credited`:

```
# conceptual — não implementar neste entregável
arkbank.credit(
    donation_brl,
    amount=round(payment.amount_brl * 1000),
    steam_id=payment.steam_id,
    ref_id=payment.payment_id,
    idempotency_key=f"arkbank:donation:{payment.payment_id}",
    metadata={"amount_brl": payment.amount_brl, "payment_method": pm},
)
```

**Não** instrumentar checkout (PENDENTE) — só o momento de **aprovação creditada**. Webhook e poll já convergem em `_finalize_pix_payment`; um único hook cobre os dois.

**Constante sugerida (espelho do padrão do sorteio):**

```
# lottery_service: DONATION_AMBER_PER_REAL = 100   # pote
ARKBANK_DONATION_AMBER_PER_REAL = 1000            # tesouraria
```

---

## 4. Modelo de dados (proposta)

### 4.1 Saldo singleton

```sql
-- Conceitual (não é migração pronta)
CREATE TABLE arkbank_state (
  id TINYINT PRIMARY KEY DEFAULT 1,  -- singleton
  balance BIGINT NOT NULL DEFAULT 0, -- pode ser negativo
  updated_at DATETIME(3) NOT NULL,
  version BIGINT NOT NULL DEFAULT 0  -- optimistic concurrency
);
```

Atualização atómica sugerida:

```sql
UPDATE arkbank_state
SET balance = balance + :delta, version = version + 1, updated_at = :now
WHERE id = 1;
INSERT INTO arkbank_transactions (...);
```

### 4.2 Transações (append-only)

```sql
CREATE TABLE arkbank_transactions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME(3) NOT NULL,
  tx_type VARCHAR(64) NOT NULL,      -- catalog_spend, market_pair_share, ...
  amount BIGINT NOT NULL,            -- sinalizado: +inflow / −outflow
  balance_after BIGINT NOT NULL,     -- snapshot pós-movimento
  steam_id VARCHAR(32) NULL,        -- jogador relacionado (se houver)
  ref_table VARCHAR(64) NULL,       -- orders, market_transactions, ...
  ref_id VARCHAR(128) NULL,
  map_id VARCHAR(64) NULL,          -- TimedPoints multi-mapa
  idempotency_key VARCHAR(128) NOT NULL,
  metadata_json JSON NULL,
  created_by_admin VARCHAR(32) NULL, -- só admin_adjust
  UNIQUE KEY uq_arkbank_idem (idempotency_key),
  INDEX idx_arkbank_time (created_at),
  INDEX idx_arkbank_type_time (tx_type, created_at),
  INDEX idx_arkbank_steam (steam_id, created_at)
);
```

### 4.3 Outbox TimedPoints (opção B)

```sql
CREATE TABLE arkbank_timed_outbox (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  created_at DATETIME(3) NOT NULL,
  steam_id VARCHAR(32) NOT NULL,
  amount INT NOT NULL,
  map_id VARCHAR(64) NOT NULL,
  cycle_key VARCHAR(64) NOT NULL,  -- ex. epoch_bucket ou uuid do tick
  processed_at DATETIME(3) NULL,
  UNIQUE KEY uq_timed (steam_id, map_id, cycle_key, amount)
);
```

### 4.4 Auditoria admin

Reutilizar padrão de `audit_events` / market audit:

| Evento | Payload |
| ------ | ------- |
| `arkbank_admin_topup` | amount, reason, admin_steam_id, balance_before/after |
| `arkbank_admin_correction` | idem |
| `arkbank_cutover` | migration notes, opening balance |

Toda mutação manual **obrigatoriamente** gera linha em `arkbank_transactions` + audit.

### 4.5 Idempotência (chaves sugeridas)

| Tipo | Chave |
| ---- | ----- |
| Catálogo compra | `arkbank:catalog:{order_id}` |
| Catálogo refund clawback | `arkbank:catalog_refund:{order_id}:{event}` |
| Casal | `arkbank:pair:{tx_id}` ou `arkbank:pair:{listing_id}:{sold_at}` |
| Encomenda | `arkbank:dino_order:{order_id}` |
| Encomenda refund | `arkbank:dino_order_refund:{order_id}` |
| Doação confirmada | `arkbank:donation:{payment_id}` |
| Doação estorno | `arkbank:donation_clawback:{payment_id}` |
| Timed | `arkbank:timed:{map_id}:{steam_id}:{cycle_key}` |

---

## 5. UI

### 5.1 Admin dashboard (MVP+)

Local sugerido: área Admin da Web Store (junto a Comércio / Sorteios / Âmbarômetro).

**Blocos:**

1. **Hero do saldo** — número grande `B`, badge “saudável / deficitário”, Δ 24h / 7d.
2. **Gráfico in/out** — série temporal diária: barras inflow vs outflow (ou área empilhada por `tx_type`).
3. **Breakdown** — pizza/tabela: catálogo / casal / encomenda / **doação** / timed / admin / refunds.
4. **Transações recentes** — tabela com tipo, valor, steam (link Minha Área/admin player), ref, mapa, data.
5. **Ações** — Top-up / correção com motivo obrigatório (modal + confirmação).
6. **Saúde vs sorteio** — card secundário: “pote ativo atual” vs “contribuição casal desviada (acumulado desde cutover)” para calibrar §7.

Wireframe textual:

```
┌─ Admin › ARKBANK ─────────────────────────────────────────────┐
│  Tesouraria          −1.240.500 ᐃ     Δ24h  −85.000           │
│  [████ inflows ████] [░░░░ outflows ░░░░]   7 dias            │
│  Catálogo 62% · Casal 18% · Encomenda 20%   Timed 100% out    │
│ ───────────────────────────────────────────────────────────── │
│  Recentes                                                     │
│  23:41  timed_reward     −100   7656…  TheIsland              │
│  23:40  catalog_spend  +12000   7656…  order_ab12             │
│  ...                                                          │
│  [ Top-up ]  [ Export CSV ]                                   │
└───────────────────────────────────────────────────────────────┘
```

### 5.2 Transparência pública (opcional, fase 3)

| Nível | O que mostra | Risco |
| ----- | ------------ | ----- |
| **Off** (default MVP) | Nada | — |
| **Soft** | Saldo arredondado + sparkline 7d + frase narrativa | Speculação / memes de “banco falido” |
| **Full** | Breakdown agregado sem SteamIDs | Mais confiança; mais pressão política |

Recomendação: **Off no MVP**; Soft só se o saldo negativo for culturalmente aceito na comunidade (copy forte).

### 5.3 Relação com Âmbarômetro

- Âmbarômetro: *“quantos Âmbares já circularam”* (gross).
- ARKBANK: *“quanto a casa tem / deve”* (net treasury).

Não fundir os widgets; podem viver lado a lado na home admin.

---

## 6. Edge cases

### 6.1 Reembolsos — catálogo 80% (retenção 20% → ARKBANK) — **aprovado**

**Produção (já em vigor no código / regulamento):** jogador recebe \(0{,}80 \times P\); retenção \(0{,}20 \times P\).

Constante: `_ORDER_DESIST_REFUND_FACTOR = 0.80` em `app.py` (desistência manual e auto-cancel 48h).

**Política ARKBANK (R1 — aprovada):**

| Momento | Movimento ARKBANK |
| ------- | ----------------- |
| Compra | `catalog_spend` \(+P\) |
| Desistência / auto-cancel | `catalog_refund_clawback` \(-0{,}80P\) |
| Resultado líquido | \(+0{,}20P\) permanece na tesouraria |

Contestação com reembolso admin **100%:** clawback adicional dos 20% restantes (zerar o efeito da compra no banco), quando o ledger existir.

**Nota de faseamento:** até existir `arkbank_service`, a retenção 20% já é aplicada na carteira do jogador; o destino “tesouraria” é contabilizado só na Fase 1.

### 6.2 Reembolsos — casal 60% do Y (claim)

Hoje: pote **não** estorna o 40%.

**Recomendação:** ARKBANK **não** estorna `market_pair_share` na desistência/expiração — o 40% já foi “taxa de sistema” no momento da venda. O reembolso 60% de Y é só entre casa? Não — é crédito ao comprador e estorno do crédito do vendedor (já implementado). O banco não participa desse unwind.

### 6.3 Encomenda cancelada / rejeitada

`reject_order` devolve 100% → clawback 100% do ARKBANK (`dino_order_refund_clawback`). Idempotente pela `order_id`.

Pedidos `PENDENTE` já pagos que falham na entrega: seguir a política de refund já existente no serviço; qualquer crédito ao jogador implica clawback simétrico no banco.

### 6.4 Race conditions

| Cenário | Mitigação |
| ------- | --------- |
| Dois workers processam o mesmo outbox | `UNIQUE idempotency` + `processed_at` |
| Compra + refund quase simultâneos | Ordenar por evento de domínio; chaves distintas |
| Optimistic lock do saldo | `version` em `arkbank_state` ou single-row `UPDATE ... balance = balance + :d` |
| Compra casal sem campanha ativa | Hoje contribuição ao pote é 0 (`no_active_campaign`); com ARKBANK o crédito **não depende** de campanha — **melhoria** face ao deferral atual |

### 6.5 Multi-mapa TimedPoints

- Cada mapa escreve outbox com `map_id` distinto.
- Déficit do banco escala com \(N_{\text{mapas}} \times\) população online.
- Staff Moderação com TimedPoints alto (`Amount` elevado no config) pode dominar o outflow — **esperado**; monitorar no dashboard.

### 6.6 Mensagens com saldo negativo

| Audiência | Tom |
| --------- | --- |
| Admin | Neutro-analítico: “Deficitário · emissão > recolha” |
| Público (se Soft) | Positivo: “O cluster está a recompensar o tempo de jogo” |
| Nunca | “Falência”, “sem fundos”, “TimedPoints pausado” |

### 6.7 Migração de gastos históricos (opcional)

| Abordagem | Descrição |
| --------- | --------- |
| **M0 — Abrir a zero** | `balance=0` no cutover; só eventos futuros | Simples; recomendado MVP |
| **M1 — Backfill ledger** | Somar `orders.points_spent` + contribuições casal históricas − estimativa TimedPoints | Complexo; TimedPoints histórico **não** está no ledger |
| **M2 — Saldo de abertura admin** | Admin escolhe opening balance simbólico após M0 | Bom compromisso |

**Recomendação:** **M0**, com opção **M2** na UI de cutover.

### 6.8 Compras in-game vs web

Se MVP só instrumentar web: documentar gap e métrica “% catálogo web vs plugin”. Fase 2 fecha o gap via CustomShop.

### 6.9 Licenças e kits no catálogo

São `catalog_spend` como qualquer item — **entram** no ARKBANK. TimedPoints bonus da licença **sai** do ARKBANK depois — loop virtuoso/intencional: quem compra licença alimenta o banco que depois paga o bônus. Licenças **não** têm desistência (irrevogáveis) — sem clawback de retenção.

### 6.10 Doação estornada / chargeback (`ESTORNADO`)

Hoje (`_finalize_pix_payment`): em `ESTORNADO` só revoga números do sorteio (`revoke_lottery_numbers_for_payment`); **não** há débito automático dos Âmbares do pacote ao jogador.

**Proposta ARKBANK:** se `donation_brl` já foi creditado, aplicar `donation_brl_clawback` com a mesma magnitude (`round(amount_brl × 1000)`), idempotente por `payment_id`. Clawback da carteira do jogador / pote do sorteio permanece política operacional existente (fora do escopo desta spec salvo nota).

---

## 7. Redesign do Sorteio — opções criativas

Com a fatia 40% do casal a ir para o ARKBANK, o pote perde uma alavanca pró-cíclica com o mercado.

### Opção A — Sorteio autossuficiente (mínimo)

**Ideia:** pote = base admin + rollover + 100% compras/reservas de números + doações (já v1.7). Sem casal.

| Prós | Contras |
| ---- | ------- |
| Menos acoplamento mercado↔sorteio | Prêmios menores em campanhas “frias” |
| Implementação trivial (só desligar `contribute_market_pair_to_prize`) | Pode reduzir FOMO se a comunidade associava casal→pote |

**Quando escolher:** se doações + compra de números já sustentam prêmios aceitáveis.

### Opção B — Sorteios patrocinados pelo ARKBANK

**Ideia:** periodicamente (ou no `auto-chain`), o sistema **transfere** \(X\) Âmbar do ARKBANK → `prize_amber_base` / nova coluna `prize_amber_from_arkbank`, com teto e só se \(B > threshold\) (ou mesmo se negativo, com flag — **não recomendado**).

| Prós | Contras |
| ---- | ------- |
| Mantém prêmios generosos | Compete com TimedPoints pelo mesmo stock |
| Narrativa unificada “tesouraria financia a festa” | Precisa de política clara para não esvaziar o banco |

**Parâmetros sugeridos:** `%` do inflow semanal de casal histórico, ou valor fixo por campanha configurável no admin.

### Opção C — Funding explícito separado (admin + eventos)

**Ideia:** botão admin “Abastecer pote” + eventos (“Boss Week: +50k ao sorteio”) + opcionalmente % de **promoções de catálogo** (não o 100% do ARKBANK).

| Prós | Contras |
| ---- | ------- |
| Controlo fino | Depende de disciplina operacional |
| Clareza contábil (pote ≠ tesouraria) | Menos automático |

### Opção D — “Imposto de casal” dividido (híbrida)

**Ideia:** dos 40%: \(p\%\) ARKBANK + \((1-p)\%\) pote (ex. 25/15 ou 30/10).

| Prós | Contras |
| ---- | ------- |
| Compromisso político | Complica a narrativa “integral para o banco” face ao pedido do utilizador |

O requisito do utilizador aponta para **100% dos 40% no ARKBANK** → D só se houver pushback da comunidade.

### Recomendação

1. **Cutover imediato:** Opção **A** (desviar 40% para ARKBANK; pote vive do que já tem).
2. **Fase observabilidade (2–4 semanas):** medir queda do `prize_amber_total` médio.
3. Se prêmios caírem > limiar acordado: adotar **B com teto** (patrocínio só quando \(B > 0\) e capped), senão **C** para campanhas especiais.

Assim o ARKBANK cumpre a visão económica sem hipotecar o TimedPoints.

---

## 8. Implementação faseada

### Fase 0 — Spec & alinhamento (este documento)

- [x] Spec de planejamento
- [x] Inflow doação PIX/cartão (R$ 1 = 1.000 Âmbar) — aprovado
- [x] Retenção catálogo 20% / reembolso 80% (R1) — aprovado; fator em código; ledger ARKBANK ligado
- [ ] Respostas restantes às perguntas abertas (§9)
- [x] Decisão sorteio A (cutover) + caminho B com teto depois
- [x] Decisão TimedPoints outbox B (MySQL)

### Fase 1 — MVP (só backend + admin mínimo)

1. Tabelas `arkbank_state` + `arkbank_transactions` (+ outbox se B). ✅
2. Serviço `arkbank_service.py` (credit/debit idempotente). ✅
3. Hooks: catálogo web (compra + clawback 80% na desistência), casal (`purchase_listing`), encomenda (`checkout` / `reject_order`), **doação** (`_finalize_pix_payment` → `donation_brl`). ✅
4. Desligar crédito a `prize_amber_from_market` (feature flag). ✅ cutover seco → ARKBANK
5. Consumidor TimedPoints (outbox → debit). ✅ plugin INSERT + worker Flask
6. Admin API: GET saldo, GET txs, POST adjust. ✅ + aba **ARKBANK** admin-only
7. Testes espelhando `test_market_pair.py` / dino_order / shop debit / finalize PIX. ✅
8. Cutover M0 (saldo zero). ✅

**Critério de pronto:** TimedPoints nunca falha por saldo; idempotência verde; casal deixa de incrementar pote; doação confirmada credita banco sem alterar pacote do jogador.

### Fase 2 — Observabilidade

1. Dashboard admin (gráfico + breakdown).
2. Alertas (Discord/admin) se \(B < −T\) por \(N\) dias.
3. Espelho seletivo no `amber_ledger` (`channel=arkbank`).
4. Métricas: inflow/outflow diário, ratio, contribuição casal desviada.
5. Instrumentação in-game catálogo (se gap material).

### Fase 3 — Player-facing (opcional)

1. Soft transparency na home / `#/economia`.
2. Copy no regulamento (§ economia / mercado casal).
3. Tutorial mercado: “40% vai para a Tesouraria ARKLAND” (em vez de “pote do sorteio”).
4. Addendum em `SORTEIO_DOACOES_SPEC.md` + `ECONOMIA_ARKLAND.md`.

### Fase 4 — Polimento sorteio (se necessário)

- Implementar opção B ou C conforme dados da Fase 2.

---

## 9. Perguntas abertas (para o utilizador)

1. **Âmbito do catálogo:** ARKBANK recebe só compras **Web Store**, ou também **`/shop` in-game** (CustomShop) na v1?
2. ~~**Refund catálogo:**~~ **Decidido — R1 com 80%/20%** (retenção 20% fica no ARKBANK; fator `_ORDER_DESIST_REFUND_FACTOR = 0.80` já em código).
3. **Casal / claim:** confirmar **sem estorno** do 40% no ARKBANK (igual ao pote hoje)?
4. **Sorteio:** preferência **A** (autossuficiente), **B** (patrocínio ARKBANK com teto), **C** (top-up admin), ou híbrida?
5. **TimedPoints → banco:** OK com **outbox MySQL (B)** e atraso de segundos, ou exigem tempo real (HTTP)?
6. **Saldo de abertura:** zero (M0) ou top-up simbólico no cutover (M2)?
7. **Transparência pública:** Off / Soft / Full na v1?
8. **Enquetes e outros créditos promocionais:** continuam **fora** do ARKBANK?
9. **Licenças/kits:** confirmar que entram como `catalog_spend` (sim na proposta)?
10. **Feature flag / rollback:** durante quantos dias manter dual-write (pote + banco) para comparação, ou cutover seco?
11. **Staff TimedPoints alto (Moderação):** algum teto especial no *débito ao banco* (não no crédito ao jogador), ou tratar igual?
12. **Nome público:** “ARKBANK”, “Tesouraria ARKLAND”, ou outro?
13. **Doação ESTORNADO:** clawback ARKBANK automático (§6.10) — confirmar? Clawback da carteira do jogador continua fora / caso a caso?

---

## 10. Não-objetivos (v1)

- Não implementar carteira Steam / saque em dinheiro real.
- Não usar ARKBANK para **capar** ou **atrasar** TimedPoints.
- Não migrar histórico completo de TimedPoints (impossível sem logs).
- Não fundir ARKBANK com Âmbarômetro num único número público.
- Não alterar preços de catálogo, fórmulas de encomenda ou \(Y/S\) do casal (só o **destino** do 40%).
- Não redesenhar RNG / regulamento legal do sorteio além do funding.
- Não debitar ARKBANK por prémios de sorteio, poll rewards ou `Shop.AddPoints` admin (salvo adjust explícito).
- Não criar “empréstimo” jogador↔ARKBANK nem juros.
- Não expor SteamIDs no painel público.
- Não implementar UI/player features antes do MVP backend estável.

---

## 11. Riscos e mitigações

| Risco | Impacto | Mitigação |
| ----- | ------- | --------- |
| Desync TimedPoints ↔ ARKBANK | Contabilidade errada | Outbox + idempotência + reconciliação diária (Σ awards plugin logs vs txs) |
| Pote do sorteio “morre” | Menos engajamento doação | Opções §7 + monitor 2–4 semanas |
| Narrativa de falência com \(B<0\) | Drama em Discord | Copy + Soft transparency adiada |
| Gap in-game shop | Banco subalimentado | Fase 2 plugin hook |
| Carga de writes multi-mapa | Pressão MySQL | Batch outbox; índices; TTL archive |

---

## 12. Critérios de sucesso (pós-MVP)

| Métrica | Alvo qualitativo |
| ------- | ---------------- |
| TimedPoints delivery | 100% dos awards configurados continuam a creditar jogadores |
| Integridade | 0 duplicados de idempotency em 30 dias |
| Casal | 0 novos créditos a `prize_amber_from_market` após cutover |
| Observabilidade | Admin vê saldo + 50 txs recentes em &lt; 2 s |
| Economia | Ratio inflow/outflow semanal documentado para calibrar preços |

---

## 13. Apêndice — mapa rápido de ficheiros

```
plugin/arkshop_web/
  amber_ledger.py              # Âmbarômetro (não confundir com ARKBANK)
  market_pair.py               # 0.40 / 0.60 / claim refund
  market_listings.py           # purchase_listing → contribute_market_pair_to_prize
  lottery_service.py           # contribute_market_pair_to_prize, on_donation_credited, prize pool
  dino_order_service.py        # checkout / reject_order
  app.py                       # catálogo web, desistência 80%, _finalize_pix_payment (PIX/cartão)
  pix_payments.py              # Mercado Pago create/fetch/map status
  poll_service.py              # fora do ARKBANK v1

plugin/CustomShop/src/
  TimedPoints.cpp              # emissão por tempo (outflow)
  ShopPoints.cpp               # AddPoints
  ShopStore.cpp                # compras in-game (gap potencial)

docs/
  ECONOMIA_ARKLAND.md
  SORTEIO_DOACOES_SPEC.md
  ENCOMENDA_DINO_SPEC.md
  ambarmeter_spec.md
  REGULAMENTO_SERVIDOR.md      # §8.4.2 desistência 80%/retenção 20%
  ARKBANK_SPEC.md              # este documento
```

---

## 14. Glossário rápido

| Termo | Significado |
| ----- | ----------- |
| \(S\) | Soma dos asking do casal \(P1+P2\) |
| \(Y\) | Checkout casal \(round(0{,}60\times S)\) |
| \(P\) | Valor pago no catálogo (`points_spent`) |
| Pote | `prize_amber_total` da campanha de sorteio |
| Tesouraria / ARKBANK | Saldo sistema \(B\) deste spec |
| TimedPoints | Recompensa periódica online no CustomShop |
| Clawback | Débito no ARKBANK que anula (parcial/total) um inflow após refund |
| `donation_brl` | Inflow ARKBANK: \(round(\text{amount\_brl}\times 1000)\) por doação confirmada |

---

*MVP ARKBANK v0.4 — Jul 2026: ledger + hooks web + aba admin. TimedPoints via outbox MySQL; sorteio opção A (casal → tesouraria).*
