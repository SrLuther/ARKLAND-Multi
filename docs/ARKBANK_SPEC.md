# ARKBANK — Tesouraria do Cluster (especificação de planejamento)


| Campo | Valor |
| ----- | ----- |
| **Status** | MVP implementado (ledger + hooks + aba admin) — polish Fase 2 |
| **Versão do documento** | 0.5.11 |
| **Data** | 15 de julho de 2026 |
| **Escopo** | Visão de produto, modelo econômico, mapeamento de código, dados, UI, edge cases, redesign do sorteio, fases, perguntas abertas; **design** Season Pass + Meta coletiva (§15) |
| **Fora de escopo (este doc)** | Soft transparency pública; patrocínio sorteio opção B; instrumentação catálogo in-game; binding SKUs completos §15.6 (kits/dinos placeholders) |
| **Moeda** | Âmbar (`players.points`) |
| **Fuso canônico** | America/Sao_Paulo (UTC−3) |
| **Changelog do doc** | **0.5.11** — curva XP locked B=3 (+25%/Δ): Free L28=6.192 ≤ budget 7.500 (30d×5h); L30=9.682; L1=B (supersede L1=500); **0.5.10** — curva B=500 (substituída); **0.5.9** — curva B=2 (substituída); **0.5.8** — checklist ops readiness §15.12; TimedPoints outbox→Pass XP; **0.5.7** — claim pós-season; Premium só Âmbar; XP multi-mapa; meta festiva; next season manual; L29=30d; freeze @ L30; Regulamento; **0.5.6** — preços Premium; **0.5.5** — Free×4 + Premium Delta; **0.5.4** — XP linear; **0.5.3** — 30 dias; **0.5.2** — seasons = tiers; **0.5.1** — Free×4 / Premium 1–30; **0.5** — Pass + Meta; **0.4** — MVP arkbank; **0.3** — 20/80; **0.2** — doação R$ 1 = 1.000 Â |

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
| Pass XP | XP individual do Season Pass (= Âmbar do tick TimedPoints; **todos** os mapas) |
| Meta coletiva | Progresso de temporada ligado à receita / cofre ARKBANK; **não** define o calendário (season = **30 dias** fixos); ao completar → **admin agenda** data do evento |
| Season Pass Premium | Compra **só em Âmbar** (sem PIX/cartão); valor integral → cofre; desbloqueia track Premium |
| Season (nome) | Branding = tier de licença: Delta → Gamma → Beta → Alfa → Omega → Transcendente |
| Duração da season | **30 dias** de calendário; **fim automático**; **início** da seguinte = **só admin manual** |
| Claim pós-season | Recompensas não resgatadas **continuam claimáveis** até o admin **iniciar** a season seguinte; depois → **perdidas** |
| Cap XP Pass | Ao atingir L30 (9.682 XP), TimedPoints continua a dar Â; **Pass XP já não sobe** |

---

## 15. Season Pass + Meta coletiva (design)

> **Status:** regras de produto **fechadas**; **motor MVP live** em `arkshop_web` (`season_pass_service` + rotas + UI SeasonLand): calendário admin (inactive → active → claim_window), XP TimedPoints multi-mapa com freeze @ 9.682 (curva +25%/Δ, B=3), Premium Â→ARKBANK, claims Free/Premium com entrega (Â / fila PENDENTE / entitlement + escolha licença↔Â). SKUs kit/item/dino ainda precisam de IDs na config admin (senão claim bloqueia com `sku_pending`). Checklist ops **§15.12**. Texto jogador-facing: **§15.11** e [`docs/REGULAMENTO_SEASON_PASS.md`](REGULAMENTO_SEASON_PASS.md) (também §8.13 do regulamento do servidor).
> **Princípio:** dois progressos distintos — **Pass individual** (XP por jogador) ≠ **Meta coletiva** (cofre / receita ARKBANK).

### 15.1 Visão em uma frase

O jogador sobe um **Pass pessoal** jogando online (XP = TimedPoints em **qualquer mapa**) ao longo de uma season **fixa de 30 dias** (nomeada por tier), enquanto o cluster enche juntos um **cofre de temporada**; ao completar a meta, a **admin agenda** um evento numa data conveniente — **sem** alongar o calendário nem disparar o evento automaticamente.

### 15.2 Decisões fechadas (locked)

| # | Regra |
| - | ----- |
| 1 | **Pass XP = Âmbar exacto** creditado em cada tick de TimedPoints (ex.: 25 sem licença, 100 com Alfa, etc. — mesmos montantes que o tick concede hoje). |
| 1b | **Multi-mapa — locked:** XP conta em **todos** os mapas do cluster. Sempre que o jogador recebe Â num tick TimedPoints (em qualquer mapa), **o mesmo montante** credita Pass XP (até ao cap L30 — regra #14). |
| 2 | Compra do **Season Pass Premium** (preço \(X\) Âmbar por season — tabela §15.2.2): o jogador gasta \(X\) Â → **100% de \(X\) creditado no cofre ARKBANK**. Compra **somente** na área UI **SeasonLand**. |
| 2b | **Premium = só Âmbar — locked:** **sem** PIX, cartão ou outro canal de dinheiro real. Moeda do Pass = `players.points` (Âmbar). |
| 3 | **Meta coletiva (cofre) ≠ Pass XP individual.** Barras / progressos separados: Pass na UI **SeasonLand**; cofre / tesouraria no **ARKBANK** (admin). |
| 4 | **Duração da season = 30 dias fixos** de calendário por season/tier. O relógio **não** depende da meta coletiva. **Fim = automático** ao completar os 30 dias. |
| 4b | **Próxima season — locked:** **só começa** quando um **admin inicia manualmente** (buffer operacional entre seasons). Não há auto-start imediato no dia 30. |
| 5 | **Meta coletiva:** ligada à receita / progresso do cofre ARKBANK. Ao atingir a meta (durante ou após a season) → **admin agenda** a data do evento para caber à maioria dos jogadores — **não** dispara evento instantâneo automático. A season **termina no dia 30** na mesma (relógio independente). |
| 6 | **Pass individual:** thresholds de XP **fixos**; XP cumulativo por jogador; **30 níveis**; curva progressiva `delta(n)=max(1,round(B×1.25**(n-1)))`, `XP(L)=Σ delta(1..L)` com **B=3** (§15.5). **L1 = B = 3 XP** (pequeno — pacing Free prioriza sobre L1=500, superseded); Free L28 = **6.192 XP**; L30 = **9.682 XP**. Ritmo alvo **250 XP/dia** (5 h sem licença) fecha **todo o Free** numa season de 30 dias; Premium L29–30 ficam além do budget Free por design. |
| 7 | **Cadência de recompensas (tracks) — locked:** ver §15.6. **Premium** em **todo** nível 1–30; **Free** só em **múltiplos de 4** (4…28). Assinante Premium recebe **ambos** quando aplicável. Exemplo: **Season Pass — Delta** (§15.6.1–15.6.2). |
| 8 | **Nome da season = tier de licença** — §15.2.1. Título UI: **Season Pass — {Tier}**. |
| 9 | **Entitlement Premium** vale **apenas** durante a **season actual** (os 30 dias daquele tier). Não arrasta para a season seguinte; há que comprar de novo na próxima. |
| 10 | **Claim manual obrigatório:** **todas** as recompensas (Free e Premium) são resgatadas pelo jogador (click / resgatar). **Sem** auto-grant ao subir de nível. |
| 11 | **Catch-up retroactivo — locked:** comprar Premium a meio da season já no nível \(N\) → pode **resgatar** Premium **1..N** e Free já desbloqueadas ainda não claimadas. |
| 12 | **Não-resgatadas / unclaimed — locked (obrigatório no Regulamento Season Pass):** no **fim dos 30 dias** as recompensas **não são perdidas de imediato**. O jogador **pode continuar a resgatar** caixas claimáveis da season encerrada **até o admin iniciar a season seguinte**. Quando a admin **abre** a próxima season → claims da season anterior ficam **desactivados** → recompensas não resgatadas estão **perdidas**. |
| 13 | **Licença de fim de Pass (ex. Premium L29 Delta) — locked:** duração = **licença normal de catálogo de 30 dias** do tier da season (Delta na season Delta; Gamma na Gamma; …). **Não** é trial de 15 dias. No claim, a recompensa aparece como **disponível**; se o jogador **já tem licença de tier superior**, no momento do resgate **escolhe**: (a) receber a licença do Pass **ou** (b) receber o **valor de catálogo em Âmbar** dessa licença. |
| 14 | **XP freeze @ L30 — locked:** ao atingir o XP máximo do Pass (**9.682** / nível 30 = `XP_cum(30)`), ticks TimedPoints **continuam** a creditar Âmbar normalmente; **deixam de** adicionar Pass XP (cap). |
| 15 | **Preços Premium** §15.2.2 + claim manual + catch-up — **mantidos** (consistentes com 0.5.6). |

### 15.3 Dois progressos (não misturar)

```
┌─ SeasonLand (UI jogador / Season Pass) ─┐   ┌─ ARKBANK (UI admin / cofre) ────┐
│  [A] PASS INDIVIDUAL                │   │  [B] META COLETIVA / LEDGER     │
│      XP += award_TimedPoints        │   │      Progresso ← inflows season │
│      (todos os mapas; cap @ L30)    │   │      Meta → admin AGENDA evento │
│      Free @ ×4 · Premium @ 1–30     │   │      NÃO controla o calendário  │
│      Premium unlock → Free+Premium  │   │                                │
│      Relógio: 30 dias; fim auto;    │   │                                │
│      next season = start MANUAL     │   │                                │
└─────────────────────────────────────┘   └────────────────────────────────┘
```

| | Pass individual | Meta coletiva |
| - | --------------- | ------------- |
| **Unidade** | XP (= Â do tick; multi-mapa) | Âmbar no cofre / progresso de receita da season |
| **Quem avança** | Só aquele jogador (online + ticks em qualquer mapa) | Todo o cluster (gastos + Premium + outros inflows) |
| **Fim da season** | Partilha o relógio de **30 dias** (fim automático); claims ainda abertos até start da seguinte (§15.2 #12) | **Não** encerra a season; admin **agenda** evento |
| **Premium** | Desbloqueia track Premium (e mantém Free nos ×4); entitlement = **esta** season; compra **só Âmbar** | Compra alimenta o cofre (100% de \(X\); §15.2.2) |
| **UI** | Área dedicada **SeasonLand** (compra + claim manual aqui) | Tab **ARKBANK** (admin) + barra de cofre se/quando pública |

### 15.2.1 Nomes das seasons (= tiers de licença)

Os nomes públicos das seasons **reutilizam exactamente** os grupos de licença do CustomShop (`TimedPointsReward.Groups` / `Permissions` / catálogo):

| Ordem (progressão no tempo) | Nome da season (tier) | Título UI |
| --------------------------- | --------------------- | --------- |
| 1 (primeira) | **Delta** | Season Pass — Delta |
| 2 | **Gamma** | Season Pass — Gamma |
| 3 | **Beta** | Season Pass — Beta |
| 4 | **Alfa** | Season Pass — Alfa |
| 5 | **Omega** | Season Pass — Omega |
| 6 | **Transcendente** | Season Pass — Transcendente |

- Ordem = hierarquia existente das licenças (menor → maior bónus TimedPoints: Delta 5 → … → Transcendente 105).
- **Primeira season:** **Delta** (**30 dias** de calendário; **fim automático**).
- Cada season seguinte na tabela = próximo bloco de **30 dias**, mas **só arranca** quando admin **inicia manualmente** (buffer entre seasons — §15.2 #4b).
- Ciclos futuros (após Transcendente): **TBD** (repetir a sequência, variante, etc.) — fora de escopo v1.
- O nome da season **não** exige que o jogador tenha a licença homónima; é só branding alinhado aos tiers do projeto.

### 15.2.2 Preço Premium por season (locked)

| Season (tier) | Premium (Â) | Destino |
| ------------- | ----------- | ------- |
| **Delta** | **15.000** | **100%** → cofre ARKBANK |
| **Gamma** | **18.000** | **100%** → cofre ARKBANK |
| **Beta** | **22.000** | **100%** → cofre ARKBANK |
| **Alfa** | **28.000** | **100%** → cofre ARKBANK |
| **Omega** | **35.000** | **100%** → cofre ARKBANK |
| **Transcendente** | **45.000** | **100%** → cofre ARKBANK |

- \(X\) = valor da linha da season activa; ledger `season_pass_premium` creditado com \(+X\) (§15.7).
- Compra **só** na UI **SeasonLand**; pagamento **apenas em Âmbar** (sem PIX/cartão); entitlement = **esta** season de 30 dias.

### 15.4 Premissas de calibração (TimedPoints)

Lidas de `TimedPointsReward` em `plugin/CustomShop/configs/config.json` (bin espelha):

| Parâmetro | Valor assumido | Fonte |
| --------- | -------------- | ----- |
| `Interval` | **30 minutos** | config atual |
| Award base (sem licença) | **25 Â / tick** (`Groups.Default.Amount`) | config atual |
| Stack de licenças | `StackRewards: true` — **todos** os Amounts de grupos activos somam (ex. Default+Alfa+Delta: 25+75+5 = **105 Â/tick**); `false` = só o maior | config + copy das licenças |

**Ritmo alvo “5 h/dia” (baseline sem licença) — locked para pacing Free:**

\[
5\,\text{h/dia} = 300\,\text{min} \Rightarrow \frac{300}{30} = \mathbf{10\ ticks/dia}
\]

\[
\text{XP/dia base} = 10 \times 25 = \mathbf{250\ XP/dia}
\]

\[
\text{Budget season} = 30 \times 250 = \mathbf{7\,500\ XP}
\]

**Intencional:** quem tem licença (mais Â/tick ⇒ mais XP/tick) **avança o Pass mais depressa**. A curva ancora no baseline **sem licença @ 5 h/dia** para que **todo o track Free (até L28)** seja concluível na season; L29–30 (Premium) ficam além desse budget por design.

**Multi-mapa (locked):** ticks TimedPoints em **qualquer mapa** do cluster geram Pass XP 1:1 com o Âmbar do tick (até ao freeze §15.2 #14).

**Duração da season (locked):** **exactamente 30 dias** de calendário por season/tier; **fim automático**. Independente da meta coletiva. **Início** da season seguinte = **manual admin**.

**Capacidade de ritmo** (relógio / XP gerado):

| Janela / ritmo | XP gerado |
| -------------- | --------- |
| **30 dias @ 250 XP/dia** (5 h sem licença) | **7.500** |
| **30 dias @ ~1.000 XP/dia** (5 h com Alfa, 100 Â/tick) | **~30.000** |

**Calibração do Pass (locked, Free-first):** B=3 (+25%/Δ) → Free L28 = **6.192 XP** (≤ 7.500; margem ~5 dias); L30 = **9.682 XP**. B=4 rejeitado (`XP_cum(28)=8.257` > 7.500). @ 250 XP/dia ≈ **~24,8 dias** até L28 Free; L30 ≈ **~38,7 dias** (Premium além do season budget Free). Após L30, Âmbar por tick **continua**; **Pass XP congela** (§15.2 #14).

### 15.5 Tabela cumulativa de XP (30 níveis)

**Design da curva (locked):** progressiva — cada nível custa **25% mais Δ** que o anterior; base **B=3**. **L1 = B = 3 XP** (pequeno por design — meta Free L28 no budget 7.500 **supersede** a âncora antiga L1=500).

\[
\delta(n)=\max\bigl(1,\ \mathrm{round}(B \times 1{,}25^{n-1})\bigr),\quad B=3
\]

\[
\mathrm{XP}(L)=\sum_{n=1}^{L}\delta(n),\quad \delta(1)=3
\]

Implementação: `season_pass_config.build_xp_thresholds()` / `xp_delta()`; freeze = `MAX_XP = XP_cum(30) = 9.682`.

**Âncoras Free (só %4==0 — L30 é Premium-only):**

| Nível Free | XP acumulado | Dias @ 250 XP/dia (5 h) | Dias @ Alfa ~1.000 XP/dia |
| ---------- | ------------ | ----------------------- | ------------------------- |
| 4 | **18** | ~0,1 | ~0,0 |
| 8 | **59** | ~0,2 | ~0,1 |
| 12 | **162** | ~0,6 | ~0,2 |
| 16 | **414** | ~1,7 | ~0,4 |
| 20 | **1.029** | ~4,1 | ~1,0 |
| 24 | **2.529** | ~10,1 | ~2,5 |
| 28 | **6.192** | **~24,8** | ~6,2 |

| Nível | XP acumulado | Δ vs. nível anterior | Dias @ 250 XP/dia (5 h) | Dias @ Alfa ~1.000 XP/dia | Track Free |
| ----- | ------------ | -------------------- | ----------------------- | ------------------------- | ---------- |
| 1 | 3 | 3 | ~0,0 | ~0,0 | — |
| 2 | 7 | 4 | ~0,0 | ~0,0 | — |
| 3 | 12 | 5 | ~0,0 | ~0,0 | — |
| 4 | **18** | 6 | ~0,1 | ~0,0 | **Free** |
| 5 | 25 | 7 | ~0,1 | ~0,0 | — |
| 6 | 34 | 9 | ~0,1 | ~0,0 | — |
| 7 | 45 | 11 | ~0,2 | ~0,0 | — |
| 8 | **59** | 14 | ~0,2 | ~0,1 | **Free** |
| 9 | 77 | 18 | ~0,3 | ~0,1 | — |
| 10 | 99 | 22 | ~0,4 | ~0,1 | — |
| 11 | 127 | 28 | ~0,5 | ~0,1 | — |
| 12 | **162** | 35 | ~0,6 | ~0,2 | **Free** |
| 13 | 206 | 44 | ~0,8 | ~0,2 | — |
| 14 | 261 | 55 | ~1,0 | ~0,3 | — |
| 15 | 329 | 68 | ~1,3 | ~0,3 | — |
| 16 | **414** | 85 | ~1,7 | ~0,4 | **Free** |
| 17 | 521 | 107 | ~2,1 | ~0,5 | — |
| 18 | 654 | 133 | ~2,6 | ~0,7 | — |
| 19 | 821 | 167 | ~3,3 | ~0,8 | — |
| 20 | **1.029** | 208 | ~4,1 | ~1,0 | **Free** |
| 21 | 1.289 | 260 | ~5,2 | ~1,3 | — |
| 22 | 1.614 | 325 | ~6,5 | ~1,6 | — |
| 23 | 2.021 | 407 | ~8,1 | ~2,0 | — |
| 24 | **2.529** | 508 | ~10,1 | ~2,5 | **Free** |
| 25 | 3.164 | 635 | ~12,7 | ~3,2 | — |
| 26 | 3.958 | 794 | ~15,8 | ~4,0 | — |
| 27 | 4.951 | 993 | ~19,8 | ~5,0 | — |
| 28 | **6.192** | 1.241 | **~24,8** | ~6,2 | **Free** |
| 29 | 7.743 | 1.551 | ~31,0 | ~7,7 | — |
| 30 | **9.682** | 1.939 | **~38,7** | **~9,7** | Premium-only |

**Checagem rápida (pacing Free @ 5 h sem licença):**

\[
6\,192 \div 250 \approx 24{,}8\ \text{dias} \le 30\ \text{(margem ~1.308 XP / ~5,2 dias)}
\]

\[
9\,682 \div 250 \approx 38{,}7\ \text{dias @ 5 h/dia sem licença (L30 além do budget Free)}
\]

Numa season de **30 dias**, @ 250 XP/dia o jogador gera **7.500 XP** → fecha **todo o Free (L28 = 6.192)** com folga; Premium L29–30 pedem XP além desse budget. B=4 (`XP_cum(28)=8.257`) ultrapassaria 7.500 e **não** seria fiável a fechar Free na season.

*Tuning:* B=3 / growth=1.25 estão **locked** nesta versão; alterar só via decisão de produto explícita — **sem** mudar Free=%4==0, Premium=1–30, XP = Â do tick **nem** a duração de 30 dias.

### 15.6 Tracks Free vs Premium (cadência + exemplo Delta)

| Track | Slot de recompensa | Quem recebe |
| ----- | ------------------ | ----------- |
| **Premium** | **Todo** nível **1–30** (30 recompensas) | Só quem comprou Season Pass Premium |
| **Free** | Só níveis **múltiplos de 4**: **4, 8, 12, 16, 20, 24, 28** (7 recompensas) | Todos os jogadores com Pass XP nesse nível |
| **Nível 30** | **Só Premium** (30 ≠ múltiplo de 4) — sem slot Free de “finale” | — |

**Quem leva o quê** (assinante Premium recebe **ambas** as tracks):

| Jogador | Nos níveis ×4 (4…28) | Noutros níveis (1–3, 5–7, …, 29–30) |
| ------- | -------------------- | ----------------------------------- |
| **Free-only** | Só a recompensa **Free** | *Nada* (sobe XP/nível, sem caixa) |
| **Premium** | **Free + Premium** (ambos) | Só **Premium** |

Nos milestones Free (×4), a caixa Premium **continua a existir** — tipicamente Â leve + item distintivo pequeno, para o assinante sentir Free+Premium sem duplicar o jackpot Free.

Outras regras de produto (**locked**):

- Tracks **paralelas** na UI (coluna Free | coluna Premium); Free só renderiza slots nos ×4.
- **Claim manual:** o jogador **resgata** cada caixa (click). Subir de nível **não** auto-entrega itens/Â.
- **Catch-up retroactivo:** comprar Premium com nível \(N\) já atingido → Premium 1..N fica **claimável** (manual); Free ×4 já desbloqueados e não claimados continuam claimáveis.
- **Unclaimed pós-season:** claimável até o admin **iniciar** a season seguinte; depois **perdido** (§15.2 #12 / Regulamento Season Pass).
- Preço \(X\): **locked** por season — tabela §15.2.2 (100% → cofre); pagamento **só Âmbar**.
- Catálogo concreto (Blueprint / SKU loja) e motor de grant: **fora de escopo** desta fase — tabelas abaixo são **linha-exemplo de produto** para **Season Pass — Delta**.

#### 15.6.1 Free — milestones ×4 (Season Pass — Delta)

| Nível | Recompensa (label) | Notas |
| ----- | ------------------ | ----- |
| **4** | **500 Â** | Early cash |
| **8** | **Kit consumíveis / stock** | Valor loja ~1–2k Â |
| **12** | **1.500 Â** | — |
| **16** | **Cryo + 1 dino L1 comum** | Não apex |
| **20** | **3.000 Â** | — |
| **24** | **Kit selas vanilla / item utilitário** | Qualidade alta; **sem** ItensAlfa |
| **28** | **5.000 Â** | Primário. *Alternativa ops:* ticket desconto **20%** loja (7 dias) |

#### 15.6.2 Premium — níveis 1–30 (Season Pass — Delta)

Linha-exemplo completa (placeholders concretos; SKUs TBD na implementação):

| Nível | Recompensa Premium (label) |
| ----- | -------------------------- |
| **1** | 250 Â |
| **2** | 500 Â |
| **3** | 750 Â |
| **4** | 400 Â + tag / cosmetic menor |
| **5** | 1.000 Â |
| **6** | Cosmetic menor (placeholder) |
| **7** | 1.000 Â |
| **8** | 500 Â + consumível leve |
| **9** | 2.000 Â |
| **10** | Kit L1 comum (pack pequeno) |
| **11** | 2.000 Â |
| **12** | 750 Â + item utilitário leve |
| **13** | Dino L1 mid |
| **14** | 2.500 Â |
| **15** | Boost curto (**ou** 2.500 Â se boost indisponível) |
| **16** | 1.000 Â + consumível / item leve |
| **17** | 3.000 Â |
| **18** | Item ItensAlfa **Delta** (se existir no catálogo) **ou** 3.500 Â |
| **19** | 4.000 Â |
| **20** | 1.200 Â + cosmetic / title leve |
| **21** | Pack10 comum barato **ou** 5.000 Â equivalente |
| **22** | 5.500 Â |
| **23** | Pack10 comum / kit gear barato **ou** 6.000 Â |
| **24** | 1.500 Â + sela vanilla leve |
| **25** | Kit selas / gear (vanilla ou equivalente) |
| **26** | Renovação parcial licença (**Delta**, ex. +3–5 dias) **ou** 7.500 Â |
| **27** | Kit gear / utilitário mid **ou** 8.000 Â |
| **28** | 2.000 Â + item distintivo pequeno |
| **29** | **Licença Delta 30 dias** (duração normal de catálogo). No claim: se o jogador **já tem licença de tier superior**, **escolhe** licença **ou** valor de catálogo em Â |
| **30** | **20.000 Â** (jackpot) |

#### 15.6.3 Escalação Gamma → Transcendente

O exemplo §15.6.1–15.6.2 é a **baseline Delta** (1.ª season). Seasons seguintes **escalam peso** (Â, raridade de kit/dino, licença **30 dias** do tier da season, exclusivos ItensAlfa do tier):

| Season | Peso relativo (orientação) |
| ------ | -------------------------- |
| **Delta** | Baseline (tabelas acima); licença L29 = **Delta 30 dias** |
| **Gamma** | ~+15–25% valor Â / upgrades de kit; licença L29 = **Gamma 30 dias** |
| **Beta** | ~+30–50% vs Delta; mais mid-tier; licença L29 = **Beta 30 dias** |
| **Alfa** | ~+60–80%; ItensAlfa / packs mais relevantes; licença L29 = **Alfa 30 dias** |
| **Omega** | ~2× Delta nos jackpots; licença L29 = **Omega 30 dias** |
| **Transcendente** | Top da curva; exclusivos + Â finais mais altos; licença L29 = **Transcendente 30 dias** |

Calibração exacta por season: **ops / balance** na implementação — manter a **mesma cadência** Free×4 / Premium 1–30. Em todas as seasons, a licença de fim de Pass é **30 dias** (nunca trial 15d); regra de escolha licença↔Â (§15.2 #13) aplica-se.

### 15.7 Premium → cofre (ledger)

Novo tipo de inflow proposto (quando implementar):

| Código | Evento | Valor no ARKBANK |
| ------ | ------ | ---------------- |
| `season_pass_premium` | Compra Season Pass Premium (UI SeasonLand) | \(+X\) integral (§15.2.2); jogador −\(X\) em `players.points` |

Não confundir com `catalog_spend` genérico se o Premium for SKU especial — preferir tipo dedicado para dashboards da meta / season.

### 15.8 Meta coletiva — evento (não controla o calendário)

| Aspecto | Desenho |
| ------- | ------- |
| **O que mede** | Progresso agregando inflows ARKBANK da season (ou subset configurável) — sempre **cofre / receita**, nunca Pass XP |
| **Target** | Valor configurável por season (admin). Hint: calibrar para ser **atingível dentro dos 30 dias** com actividade típica do cluster |
| **Relógio da season** | **30 dias fixos** — independente da meta; **fim automático**; **next season = start manual admin** |
| **Meta completa (durante ou após a season)** | **Admin agenda** data do evento (caber à maioria dos jogadores) — **não** dispara evento instantâneo automático. A season **continua** até ao dia 30 se ainda activa |
| **Meta incompleta no dia 30** | Season fecha na mesma; evento pode ser cancelado, adiado, ou recompensado parcialmente — **TBD ops** |
| **Recompensa da meta** | **Não** é caixa automática: **evento organizado / agendado por admins** |
| **UI** | Barra colectiva “Cofre da temporada” + % (se/quando pública); distinta do XP do Pass |

### 15.9 UI

- **Pass individual:** área dedicada **SeasonLand** (aba da Web Store). Título da season no painel: **Season Pass — {Tier}** (ex. *Season Pass — Delta*). Copy de duração: **30 dias**; fim automático; próxima season só quando admin abrir.
- Conteúdo Pass: status + dias restantes, nível / XP / próximo threshold (com **freeze** após L30), dual track Free (só ×4) | Premium (1–30), **CTA Compra Premium** (só Âmbar; preço §15.2.2), botões **Resgatar** por nó claimável, nota XP=Â TimedPoints multi-mapa ≠ meta do cofre.
- Compra Premium **não** ocorre noutro ecrã nem via PIX/cartão — só neste painel, em Âmbar.
- Copy: Premium só vale **esta** season; claim é **manual**; buy mid-season desbloqueia catch-up 1..N; **unclaimed** após dia 30 ainda resgatáveis **até** a próxima season arrancar.
- Link / bloco **Regulamento Season Pass** (§15.11 / `REGULAMENTO_SEASON_PASS.md`) — para UI export futura.
- **Cofre / meta + extrato:** tab **ARKBANK** (admin). Barra colectiva jogador-facing — fase futura.
- Copy: ticks sobem o Pass (até L30); gastos / Premium enchem o cofre; **meta não alonga** a season; evento = **data agendada**.

### 15.10 Fora de escopo / perguntas abertas (Pass + Meta)

**Fora de escopo nesta spec / nesta fase:**

- Binding completo de SKUs / Blueprints a todos os labels §15.6 (engine de grant existe; IDs TBD na config admin).
- Conteúdo concreto do evento de meta (ops admin) — só a regra de **agendamento** está locked.
- ~~Motor de grant / XP persistente~~ — **MVP implementado** (jul/2026).
- Soft transparency pública do saldo ARKBANK (já fora noutros §).
- Capar TimedPoints ou XP por saldo do banco (**proibido** — §10). TimedPoints Â **nunca** é cortado; só Pass XP congela @ L30.
- Ciclo de naming após a 6.ª season (Transcendente).

**Perguntas abertas:**

1. ~~Preço exacto \(X\) do Premium~~ — **fechado** §15.2.2.
2. Meta colectiva conta **todos** os inflows ARKBANK da season ou um subset (ex. excluir `donation_brl` / excluir `admin_adjust`)?
3. ~~Tracks Free vs Premium~~ — **fechado** §15.6.
4. ~~Premium a meio da season: claim retroactivo~~ — **fechado** (sim; claim manual) §15.2 #11 / §15.6.
5. ~~Pass XP / rewards não reclamados no fecho dos 30 dias~~ — **fechado** §15.2 #12 (claim até next season start; depois perdido).
6. ~~Duração meta-driven~~ — **fechado:** **30 dias** fixos; meta só agenda evento.
7. Staff / Moderação: XP de Pass conta igual (provável **sim**, XP=Â) ou exclusão?
8. ~~Tabela exemplo Free/Premium Delta~~ — **fechado** §15.6.1–15.6.2 (labels; SKUs TBD); licença L29 = **30 dias**.
9. ~~Canal de compra Premium / duração do entitlement / auto-claim~~ — **fechado** §15.2 #2, #2b, #9, #10.
10. ~~Multi-mapa / XP freeze / next season manual / licença↔Â~~ — **fechado** §15.2 #1b, #4b, #13, #14.

### 15.11 Regulamento Season Pass (texto jogador-facing)

Documento dedicado (pode ser exportado como link na UI SeasonLand): [`docs/REGULAMENTO_SEASON_PASS.md`](REGULAMENTO_SEASON_PASS.md). Espelho normativo no regulamento do servidor: **§8.13**.

Resumo normativo (obrigatório incluir **unclaimed**):

1. **Duração:** cada season dura **30 dias**; o **fim é automático**. A **próxima** season só começa quando a **administração iniciar** manualmente.
2. **XP:** jogar online em **qualquer mapa** — cada Âmbar recebido por TimedPoints sobe o Pass XP na **mesma** quantidade, até ao **nível 30**. Depois disso, os Âmbares do tick **continuam**, mas o XP do Pass **não sobe mais**.
3. **Premium:** compra **apenas com Âmbar** na área SeasonLand (sem PIX/cartão). Vale **só** a season actual. Resgates são **sempre manuais**; comprar a meio desbloqueia catch-up das caixas já desbloqueadas.
4. **Recompensas não resgatadas:** no fim dos 30 dias **não** se perdem de imediato. Ainda podes resgatar **até a administração abrir a próxima season**. Quando a próxima season começa, o resgate da season anterior **fecha** e o que não foi resgatado **é perdido**.
5. **Licença (ex. Delta 30 dias no Premium L29):** duração normal de catálogo (**30 dias**). Tiers pagos distintos **ilimitados**; renovar o mesmo tier empilha **+30 dias**. Se já tiveres tier **superior**, no resgate **escolhes** a licença do Pass **ou** o valor de catálogo em Âmbar.
6. **Meta colectiva:** ao completar, a administração **marca uma data** de evento para a maioria poder participar — **não** é um evento automático no instante em que a barra enche.

### 15.12 Checklist ops — SeasonLand readiness (jul/2026)

Estado do motor vs o que ainda falta para abrir a 1.ª season em produção.

#### DONE (código + docs)

| # | Item | Onde |
| - | ---- | ---- |
| A | Calendário admin inactive → active → claim_window; start 1.ª / próxima (avança tier; fecha claims) | `season_pass_service.start_season` + `POST /api/admin/season-pass/start` + UI SeasonLand admin |
| B | Config admin: duração, preço Premium por tier, grants tipados Free×4 / Premium 1–30 | `season_pass_config` + painel admin |
| C | TimedPoints → Pass XP no **caminho produção** webstore: CustomShop enfileira `arkbank_timed_outbox`; scheduler Flask chama `process_timed_outbox` → `add_timed_xp` (multi-mapa, idempotente, freeze @ 9.682) | `TimedPoints.cpp` + `arkbank_service.process_timed_outbox` + worker em `app.py` |
| D | Schema auto no boot (`season_pass_*`, `arkbank_*`) | `ensure_season_pass_schema` / `ensure_arkbank_schema` |
| E | Premium só Âmbar → cofre ARKBANK (`season_pass_premium`); UI SeasonLand jogador | `credit_season_pass_premium` + rotas/UI |
| F | Claims manuais Free/Premium: Â imediato; kit/item/dino → fila PENDENTE; licença → entitlement; escolha licença↔Â se tier superior | `claim_reward` + hooks app |
| G | Regulação jogador-facing + espelho servidor | §15.11 / `REGULAMENTO_SEASON_PASS.md` / regulamento §8.13 |
| H | Rename UI SeasonLand + home info + logo | `static/index.html` |

#### REMAINING (bloqueia go-live completo ou polish)

| # | Item | Notas |
| - | ---- | ----- |
| R1 | **Binding SKUs** kit/item/dino nos grants admin (§15.6 labels) | Sem `id` → claim `sku_pending`. Âmbar/licença já entregam. |
| R2 | **Activar season em prod** | Admin SeasonLand → «Iniciar season» (após redeploy). Ver passos abaixo. |
| R3 | Conteúdo / data do **evento de meta** colectiva | Regra locked; ops agenda quando a barra encher. |
| R4 | Soft transparency pública do saldo ARKBANK | Fora de escopo desta fase. |
| R5 | Perguntas abertas §15.10 #2 (subset inflows meta) e #7 (staff XP) | Não bloqueiam MVP Pass. |
| R6 | Ciclo de naming pós-Transcendente | Design TBD. |

#### Deploy / activação (ops)

1. **Deploy código** webstore (`plugin/arkshop_web`) — scheduler tem de estar a correr (mesmo processo Flask / serviço).
2. **Boot** cria/atualiza tabelas (`arkbank_*`, `season_pass_*`) — sem SQL manual se `ensure_*_schema` corre no arranque.
3. **CustomShop** nos mapas com TimedPoints a escrever na outbox (`INSERT … arkbank_timed_outbox`) — DLL ≥ outbox ARKBANK; reiniciar mapas / `Shop.Reload` após update do plugin.
4. **Redeploy / restart webstore** para aplicar worker `process_timed_outbox` (intervalo `ARKSHOP_RETRY_INTERVAL`, default ~60s). Não há processo separado: o consumer é o scheduler embutido.
5. **Preencher grants** no admin SeasonLand (IDs de catálogo) e **Guardar config**.
6. **«Iniciar season»** no admin (1.ª vez). Só então XP TimedPoints aplica Pass XP.
7. Smoke: jogador online 1 ciclo → linha outbox `processed_at` preenchida → XP sobe no painel SeasonLand; logs `arkbank_timed_outbox_processed` com `season_pass_xp` > 0.

---

*MVP ARKBANK v0.5.11 — Jul 2026: Season Pass locked + curva XP +25%/Δ (B=3, Free L28=6.192, L30=9.682) + motor MVP live + checklist ops §15.12. TimedPoints outbox → Pass XP; sorteio opção A.*
