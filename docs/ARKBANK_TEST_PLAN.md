# ARKBANK — Plano de testes (QA)

| Campo | Valor |
| ----- | ----- |
| **Escopo** | Smoke manual da aba admin exclusiva + checklist de regressão dos hooks |
| **Automatizado** | `plugin/arkshop_web/tests/test_arkbank_edge_cases.py` (+ `test_market_pair`, `test_order_cancel_policy`) |
| **Spec** | [`ARKBANK_SPEC.md`](./ARKBANK_SPEC.md) v0.3 |
| **Data** | 13 jul 2026 |

---

## 1. Pré-requisitos

- Web Store a correr com DB migrado (`arkbank_state` + `arkbank_transactions`).
- SteamID presente em `admin_steamids.json` (ou equivalente).
- Conta **não-admin** para verificar exclusividade da aba.
- Feature flag / cutover de casal documentado (pote vs ARKBANK).

---

## 2. Smoke — aba admin exclusiva (MVP)

Ordem sugerida (~10 min):

1. **Login jogador comum** → abrir Admin / navegação lateral.
   - Esperado: **sem** entrada “ARKBANK” / “Tesouraria”.
2. **Login admin** → mesma navegação.
   - Esperado: aba **ARKBANK** (ou “Tesouraria”) visível **só** para admin.
3. Abrir a aba com saldo inicial **0** (cutover M0).
   - Hero do saldo legível; se negativo, tom “deficitário” (não “falência”).
4. **Top-up admin** (ex. +10.000) com motivo obrigatório.
   - Saldo sobe; aparece linha `admin_adjust` nas txs recentes.
5. Sem motivo → API/UI rejeita (400 / mensagem clara).
6. Recarregar a página → saldo e últimas txs persistem.
7. Jogador comum a chamar diretamente `GET/POST /api/admin/arkbank*` (se existir).
   - Esperado: **403** / redirect auth — nunca dados do banco.

---

## 3. Smoke — fluxos económicos (quando hooks ligados)

| # | Ação | Esperado no ARKBANK | Não esperado |
| - | ---- | ------------------- | ------------ |
| A | Compra catálogo web (preço \(P\)) | `catalog_spend` \(+P\) | — |
| B | Desistência após 24h | `catalog_refund_clawback` \(−0{,}80P\); saldo líquido \(+0{,}20P\) | Reembolso 100% ao jogador |
| C | Venda casal checkout (\(S\)) | `market_pair_share` \(+round(0{,}40S)\) | Novo crédito em `prize_amber_from_market` (cutover seco) |
| D | Desistência claim casal | Saldo ARKBANK **inalterado** (sem clawback do 40%) | Estorno do 40% |
| E | Doação PIX/cartão **APROVADO** (R$ \(X\)) | `donation_brl` \(+round(X\times 1000)\) | Alteração do pacote do jogador / pote doação |
| F | Webhook/poll duplicado mesmo `payment_id` | **Uma** linha no ledger | Saldo duplicado |
| G | TimedPoints (outbox) com saldo 0 | `timed_reward` negativo; jogador **ainda** recebe pontos | Bloqueio / award parcial |

---

## 4. Checklist de regressão automatizada

```bash
cd plugin/arkshop_web
python -m pytest tests/test_arkbank_edge_cases.py tests/test_market_pair.py tests/test_order_cancel_policy.py -q
```

Cobertura edge-case (ficheiro `test_arkbank_edge_cases.py`):

- Saldo negativo permitido (timed reward / débitos sucessivos).
- Crédito idempotente (mesma `idempotency_key` / `order_id` / `payment_id`).
- Compra + desistência → retenção 20%.
- Doação BRL → Âmbar 1:1000 (`donation_amber_from_brl`).
- Corrida concurrent-ish no mesmo `payment_id`.
- Contribuição casal 40% no ledger; sem clawback de claim.
- Hooks de produção: **skip com motivo** até wiring em `app.py` / `market_listings.py`.

---

## 5. Gaps conhecidos (estado QA 13 jul 2026)

- [x] `contribute_market_pair_to_prize` → `credit_market_pair_share` (pote `prize_amber_from_market` congelado).
- [x] Compra / cancel / auto-cancel catálogo → `credit_catalog_spend` / `debit_catalog_refund_clawback`.
- [x] `_finalize_pix_payment` → `credit_donation_brl` (+ clawback `ESTORNADO`).
- [x] Worker TimedPoints outbox (`process_timed_outbox` no scheduler).
- [x] Rotas admin: `GET /api/admin/arkbank`, `GET .../transactions`, `POST .../adjust`.
- [ ] Aba UI exclusiva no `index.html` (smoke da secção 2 pendente).

---

*Documento de QA — não é release notes. Atualizar checkboxes quando a UI admin passar a verde.*
