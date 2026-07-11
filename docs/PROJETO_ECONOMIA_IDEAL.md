# PROJETO ECONOMIA IDEAL — ARKLAND

> **Tipo:** Proposta de Design  
> **Status:** Rascunho para revisão administrativa  
> **Versão:** 1.0 — Jul 2026  
> **Base:** Dados reais de `market_species_defaults.json`, `species_root_ladder.json`, `blueprint_catalog_matrix.csv`  
> **Referência cruzada:** [`docs/ECONOMIA_ARKLAND.md`](./ECONOMIA_ARKLAND.md)  
> **Tabela completa de preços:** [**→ TABELA_PRECOS_DINOS.md**](./TABELA_PRECOS_DINOS.md) — 79 espécies com preços atuais vs propostos, mercado 254pts e encomenda máxima

---

## Resumo Executivo

Este documento propõe um projeto de economia **sustentável, progressiva e anti-inflação** para o ARKLAND. A economia atual está bem estruturada tecnicamente, mas apresenta lacunas em **controle de inflação, progressão clara e sustentabilidade de longo prazo**. O projeto ideal aborda essas lacunas sem quebrar a estrutura existente.

**Pilares do projeto ideal:**
1. Progressão clara de novato → veterano
2. Preços âncora bem calibrados por papel e tier
3. Taxas e sumidouros que drenam a moeda proporcionalmente ao volume
4. Ganhos balanceados para engajar sem desvalorizar o Âmbar
5. Migração faseada a partir do estado atual

---

## 1. Princípios de Design

### 1.1 Controle de Inflação

**Problema atual:** A taxa de emissão de Âmbar (tempo online) não tem contrapeso proporcional ao crescimento da base de jogadores. Em servidores maduros, acumulação supera os sumidouros.

**Princípios:**
- **Emissão controlada:** Bônus de tempo online calibrado para que um jogador casual (2h/dia) leve ~60 dias para comprar a primeira espécie relevante (Rex).
- **Sumidouros proportionais:** Toda transação de alto valor deve ter uma taxa (fee) que retira Âmbar permanentemente do sistema.
- **Teto de acumulação por jogador:** Implementar soft-cap psicológico via design de custo (compras sempre disponíveis para drenar excessos).

### 1.2 Progressão Horizontal e Vertical

```
Horizontal: C → B → A → S → S+  (meses de jogo)
Vertical:   L1 → breeding → linhagem 254pts → top market
```

- Um jogador novo deve conseguir um dino C/B em 1–2 semanas.
- Um dino S+ top-tier (Armaedron 254pts) deve representar 3–6 meses de dedicação.

### 1.3 Fairness P2P

- Vendedores devem ganhar Âmbar proporcional ao trabalho de breeding.
- Uma taxa de listagem/venda drena a economia sem prejudicar demais o vendedor.
- O valor sugerido deve ser *razoavelmente* seguido (sem distorções extremas).

---

## 2. Arquitetura de Ganhos (Earnings)

### 2.1 Proposta de Ganho por Tempo Online

Manter o modelo atual mas com ajuste de valores e diferenciação maior entre tiers:

| Grupo | Âmbar / 30min | Âmbar / hora | Âmbar / dia (2h) | Âmbar / mês (2h/dia) |
|-------|---------------|--------------|-----------------|----------------------|
| Default (sem licença) | **30** | 60 | 120 | 3.600 |
| Gamma (50k) | **60** | 120 | 240 | 7.200 |
| Beta (75k) | **90** | 180 | 360 | 10.800 |
| Alfa (100k) | **120** | 240 | 480 | 14.400 |

> Proposta: ajustar de 25/50/75/100 para **30/60/90/120** (+20%) — pequeno aumento que melhora a percepção de progressão sem inflação expressiva.

### 2.2 Multiplicadores de Evento (Proposta)

| Tipo de Evento | Multiplicador | Duração sugerida |
|----------------|--------------|-----------------|
| Fim de semana padrão | 1.5× | Sáb-Dom |
| Evento temático (feriado) | 2× | 3–7 dias |
| Wipe/reset de temporada | 3× | Primeiros 7 dias |
| Maratona de breeding | 1.5× | 24h |

**Implementação sugerida:** Campo `active_event_multiplier` no settings da Web Store, aplicado no cálculo de `timed_bonus`.

### 2.3 Ganhos por Participação (Proposta)

| Atividade | Recompensa sugerida |
|-----------|---------------------|
| Primeiro login do dia | 50 Â bônus |
| Completar boss evento | 200–500 Â |
| Referência de novo jogador | 1.000 Â (único) |
| Vitória em torneio PvP | 500–2.000 Â |

---

## 3. Estrutura de Preços — Catálogo Ideal

### 3.1 Filosofia de Precificação L1

O preço L1 (R = `root_value`) deve representar o custo de **adquirir uma base de breeding** para a espécie. A fórmula ideal:

```
R_ideal = (horas_necessárias_para_adquirir) × (ganho_médio_por_hora_Default)
R_ideal = horas × 60 Â/h
```

| Horas-alvo | R resultante (@ 60 Â/h) | Tier/Papel adequado |
|-----------|------------------------|---------------------|
| 5h | 300 | C utilitario |
| 10h | 600 | C utilitario |
| 15h | 900 | C ataque |
| 25h | 1.500 | B utilitario |
| 50h | 3.000 | B ataque |
| 100h | 6.000 | A locomocao |
| 150h | 9.000 | A ataque |
| 300h | 18.000 | S ataque (Rex) |
| 416h | 25.000 | S+ raid (Carcha) |
| 466h | 28.000 | S+ boss (Indominus) — **v2** |
| 550h | 33.000 | S+ boss cluster (Dread/Ancient/IndoRaptor) — **v2** |
| 583h | **35.000** | **S+ boss apex (Armaedron) — v2** ~~1.500h/90k~~ |

> **v2 Jul/2026:** Armaedron recalibrado de 90.000+ para **35.000**. Ao ritmo base de 50Â/h (sem licença), isso representa ~700h = ~350 dias jogando 2h/dia. Com Alfa (200Â/h, 4h/dia) = ~44 dias. Ver `docs/TABELA_PRECOS_DINOS.md` §Rationale.

> **Rex a 300h** com jogador casual (2h/dia) = **150 dias**. Rex com Licença Alfa (4h/dia) = ~37 dias. Esse spread é saudável.

### 3.2 Tabela de Preços Ideais por Espécie

Comparação **atual vs proposto** baseada nas âncoras e `mercado_254_targets`:

> **v2 Jul/2026:** S+ boss cluster e S tier topo recalibrados. Hierarquia preservada: Armaedron > Indominus > Carcha > Rex.

| Espécie | Tier | Papel | R atual | R proposto | Δ | Justificativa |
|---------|------|-------|---------|-----------|---|---------------|
| Armaedron | S+ | boss | 95.000 | **35.000** | ↓ | **Recalibrado v2** — apex premium mas atingível (~350h default) |
| Dread Wyvern | S+ | boss | 91.464 | **33.000** | ↓ | **Recalibrado v2** — cluster abaixo Armaedron |
| Ancient Wyvern | S+ | boss | 90.757 | **32.000** | ↓ | **Recalibrado v2** — prestige_rank 88 |
| IndoRaptor | S+ | boss | 90.404 | **32.000** | ↓ | **Recalibrado v2** — prestige_rank 87 |
| Indominus Rex | S+ | boss | 70.000 | **28.000** | ↓ | **Recalibrado v2** — âncora boss S+; acima do Carcha |
| Small Hydra | S | boss | 52.121 | **24.000** | ↓ | **Recalibrado v2** — boss S único; escala com tier S |
| Giganotossauro Tek | S+ | ataque | 46.464 | **22.000** | ↓ | **Recalibrado v2** — S+ ataque; abaixo de Indominus boss |
| Rex Tek | S+ | ataque | 45.959 | **21.000** | ↓ | **Recalibrado v2** — S+ ataque; ligeiro abaixo do Giga Tek |
| Shadowmane | S | raid | 35.555 | **22.000** | ↓ | **Recalibrado v2** — raid S alinhado ao tier |
| Tek Strider | S+ | boss | 35.000 | **26.000** | ↓ | **Recalibrado v2** — catalog_only; acima do Carcha |
| Carcharodontosaurus | S+ | raid | 25.000 | **25.000** | = | Âncora raid — manter |
| Giganotosaurus | S | ataque | 22.636 | **22.500** | ≈ | Aceitável |
| Acrocantossauro | S | ataque | 22.373 | **22.000** | ≈ | Aceitável |
| Rex | S | ataque | 18.000 | **18.000** | = | Âncora ataque — manter |
| Reaper | A | raid | 16.121 | **16.000** | ≈ | Aceitável |
| Deinonychus | A | ataque | 9.525 | **9.500** | ≈ | Aceitável |
| Astrodelphis | A | locomocao | 6.868 | **7.000** | ↑ | Escassez de voo — justifica leve aumento |
| Desmodus | A | locomocao | 6.787 | **7.000** | ↑ | Mesmo motivo |
| Diru-Ya-Ku | C | ataque | 1.311 | **1.500** | ↑ | C entry — mínimo 1.500 ideal |
| Abyss C utilitario | C | utilitario | 585–696 | **800** | ↑ | Floor mínimo C = 800 |

> **Regra proposta:** Nenhum R abaixo de **500 Âmbar**. Mínimo C = 500–1.000. Isso evita dinos "sem valor" que poluem o mercado.

---

## 4. Orçamento de Prêmio B — Alvos de Mercado 254pts

O B ideal resulta do alvo `mercado_254_targets` da ladder:

| Papel | Tier C | Tier B | Tier A | Tier S | Tier S+ |
|-------|--------|--------|--------|--------|---------|
| utilitario | 8.000 | 15.000 | 28.000 | — | — |
| locomocao | 12.000 | — | 42.000 | 60.000 | — |
| ataque | 15.000 | 35.000 | 75.000 | 108.000 | 150.000 |
| raid | 18.000 | 45.000 | 90.000 | 130.000 | 150.000 |
| boss | — | 25.000 | 120.000 | 150.000 | 150.000 |

```
B_ideal = mercado_254_target - R
```

Exemplo: Rex (S, ataque) → B = 108.000 − 18.000 = 90.000 ✓ (já calibrado)

---

## 5. Taxas e Fees (Proposta)

### 5.1 Taxa de Listagem no Mercado P2P

**Estado atual:** Zero fees. Vendedor recebe 100% do preço.

**Proposta:**

| Faixa de preço | Taxa de listagem | Destinação |
|----------------|-----------------|-----------|
| 0 – 10.000 | 2% | Sink (destruído) |
| 10.001 – 50.000 | 3% | Sink |
| 50.001 – 150.000 | 5% | Sink |

**Racional:** Uma fee de 3–5% drena ~4.000–7.500 Âmbar por transação de dino S/S+, controlando a oferta monetária sem prejudicar o vendedor.

**Implementação:** Campo `market_listing_fee_pct` no settings da Web Store. Debitar ao confirmar venda.

### 5.2 Taxa de Serviço na Encomenda

**Estado atual:** α=0.25 + β=0.35 → custo adicional de ~60% sobre o valor de mercado.

**Proposta (ajuste):**

| Parâmetro | Atual | Proposto | Impacto |
|-----------|-------|----------|---------|
| α (base) | 0.25 | **0.20** | Redução taxa base |
| β (serviço) | 0.35 | **0.30** | Redução taxa variável |
| auto_approve_max | 200.000 | **175.000** | Mais pedidos revisados |
| encomenda_absolute_max | 275.000 | **275.000** | Manter |

Redução modesta das taxas de encomenda para incentivar uso e compensar a nova taxa de listagem.

### 5.3 Taxa de Renovação de Licença

**Estado atual:** Renovação ao preço cheio (50k/75k/100k).

**Proposta:** Desconto de fidelidade na renovação:
- Renovação na vigência: 80% do preço cheio
- Renovação expirada (até 7 dias após): 90%

### 5.4 Kit — Filosofia de Preço

Os kits devem ser um **canal de entrada de breeding**, acessível para jogadores que querem começar uma linhagem sem esperar pelo mercado. Proposta de cálculo:

```
Kit_10x_price = 10 × R × 0.50  (50% de desconto vs 10 individuais no catálogo)
```

Exemplo Rex: 10 × 18.000 × 0.50 = **90.000 Âmbar**

Isso representa uma atualização dos preços de kit que estão atualmente defasados das âncoras revisadas. A tabela completa de kits revisados resultaria de aplicar essa fórmula.

---

## 6. Licenças — Tiers Ideais

### 6.1 Proposta de 4 Tiers com ROI Claro

| Tier | Nome sugerido | Preço | Ganho extra /30min | ROI @ 2h/dia | Benefícios adicionais |
|------|--------------|-------|-------------------|--------------|-----------------------|
| Default | — | 0 | 0 | — | Acesso básico |
| Gamma | Licença Gamma | 50.000 | +30 | ~14 meses¹ | Badge cosmético |
| Beta | Licença Beta | 75.000 | +60 | ~10 meses¹ | Badge + slot extra |
| Alfa | Licença Alfa | 100.000 | +90 | ~9 meses¹ | Badge + slot extra + acesso antecipado eventos |

¹ _Com ganho proposto de 30 Â/30min base. O ROI monetário puro é longo — valor está no status e benefícios._

### 6.2 Licença Nuvem — Manter Preço

Licença Nuvem (5.000 Â / 30 dias) está bem posicionada. É um sumidouro de baixo custo e alto impacto para jogadores ativos.

---

## 7. Sumidouros Recomendados

### 7.1 Sumidouros Existentes (OK)

- Compra de licenças
- Compra de kits
- Encomendas (taxa de serviço)

### 7.2 Novos Sumidouros Propostos

| Sumidouro | Volume estimado /mês | Prioridade |
|-----------|---------------------|-----------|
| Taxa de listagem P2P (3–5%) | Alto (depende volume) | **Alta** |
| Estética/cosméticos (emotes, skin) | Médio | Alta |
| Fast-track de encomenda (+500 Â) | Baixo | Média |
| Renomeação de dino (+100 Â) | Médio | Média |
| Slot extra de encomenda (+1k Â) | Médio | Média |
| Torneio entry fee (reembolsável) | Médio | Baixa |

### 7.3 Análise de Equilíbrio

Com 100 jogadores ativos, 2h/dia (sem licença):
- **Emissão:** 100 × 120 Â/dia × 30 = 360.000 Â/mês
- **Taxa P2P estimada (20 transações/mês @ 30k médio @ 4%):** 20 × 1.200 = 24.000 Â/mês
- **Deficit de drenagem:** ~94% da emissão ainda circula

**Conclusão:** Mesmo com taxa P2P, a principal drenagem deve vir de **cosméticos e serviços** acessíveis e recorrentes.

---

## 8. Parâmetros Globais Propostos

| Parâmetro | Valor atual | Proposto | Arquivo |
|-----------|-------------|----------|---------|
| gamma (Q decay) | 0.82 | **0.80** | `_floor_quality.gamma` |
| market_absolute_max | 150.000 | **150.000** | Manter |
| encomenda_absolute_max | 275.000 | **275.000** | Manter |
| encomenda_alpha | 0.25 | **0.20** | `_floor_quality.encomenda_alpha` |
| encomenda_beta | 0.35 | **0.30** | `_floor_quality.encomenda_beta` |
| pts_reference | 254 | **254** | Manter |
| rate_limit_orders | 3/7dias | **3/7dias** | Manter |
| auto_approve_max | 200.000 | **175.000** | `dino_order_service.py` |
| price_ceiling enabled | false | **true** | Habilitar para S+ extremos |

### Proposta para price_ceiling (reativar):

```json
{
  "enabled": true,
  "global_multiplier": 8.0,
  "tier_multipliers": { "S+": 10.0, "S": 8.0, "A": 6.0, "B": 5.0, "C": 4.0 },
  "absolute_max": 500000
}
```

Isso impede preços de anúncio absurdos sem restringir o mercado justo.

---

## 9. Plano de Migração — Faseado

### Fase 1 — Sinalização (Sem custo, imediato)

1. Publicar `ECONOMIA_ARKLAND.md` internamente
2. Comunicar jogadores sobre mudanças futuras de preço
3. Criar canal de feedback (#economia no Discord)

### Fase 2 — Ajustes de Parâmetro (1–2 semanas)

1. Ajustar `encomenda_alpha` 0.25→0.20 e `encomenda_beta` 0.35→0.30
2. Habilitar `price_ceiling` com valores propostos
3. Ajustar timed_bonus: 25→30 base, 50→60 Gamma, 75→90 Beta, 100→120 Alfa

### Fase 3 — Revisão de Preços (2–4 semanas)

1. Executar `recalibrate_market_economy.py` com novos R propostos
2. Revisar CSV gerado com equipe
3. Rodar `sync_market_species_to_shop_catalog.py` para atualizar `config.json`
4. Anunciar nova tabela de preços com 7 dias de antecedência

### Fase 4 — Novos Sumidouros (1–2 meses)

1. Implementar taxa de listagem P2P (3–5%)
2. Adicionar cosméticos na loja
3. Sistema de eventos com multiplicador

### Fase 5 — Monitoramento Contínuo

1. Dashboard de economia (emissão vs drenagem)
2. Relatório mensal de transações
3. Ajuste de parâmetros conforme dados reais

---

## 10. Tabela Completa de Espécies — Estado Atual vs Proposto

Dados de `tools/blueprint_catalog_matrix.csv` com propostas:

| Espécie | Tier | Papel | R atual | Mercado 254 atual | R proposto | Mercado 254 proposto |
|---------|------|-------|---------|--------------------|-----------|----------------------|
| Armaedron | S+ | boss | 95.000 | 150.000 | **35.000** | 150.000 |
| Dread Wyvern | S+ | boss | 91.464 | 150.000 | **33.000** | 150.000 |
| Ancient Wyvern | S+ | boss | 90.757 | 150.000 | **32.000** | 150.000 |
| IndoRaptor | S+ | boss | 90.404 | 150.000 | **32.000** | 150.000 |
| Indominus Rex | S+ | boss | 70.000 | 150.000 | **28.000** | 150.000 |
| Small Hydra | S | boss | 52.121 | 150.000 | **24.000** | 150.000 |
| Giganotossauro Tek | S+ | ataque | 46.464 | 150.000 | **22.000** | 150.000 |
| Rex Tek | S+ | ataque | 45.959 | 150.000 | **21.000** | 150.000 |
| Shadowmane | S | raid | 35.555 | 130.000 | **22.000** | 130.000 |
| Tek Strider | S+ | boss | 35.000 | 150.000 | **26.000** | 150.000 |
| Volcano Small Dragon | A | boss | 25.757 | 120.000 | 26.000 | 120.000 |
| Small Dragon | A | boss | 25.454 | 120.000 | 25.500 | 120.000 |
| Fire Elemental | A | boss | 25.151 | 120.000 | 25.000 | 120.000 |
| Carcharodontosaurus | S+ | raid | 25.000 | 150.000 | 25.000 | 150.000 |
| Crystal Wyvern Queen | A | boss | 25.000 | 120.000 | 25.000 | 120.000 |
| Small Desert Titan | A | boss | 25.000 | 120.000 | 25.000 | 120.000 |
| Small Dodoreaper | A | boss | 24.848 | 120.000 | 25.000 | 120.000 |
| Small DodoRex | A | boss | 24.848 | 120.000 | 25.000 | 120.000 |
| Small Manticore | A | boss | 24.696 | 120.000 | 24.500 | 120.000 |
| Small Megapithecus | A | boss | 24.545 | 120.000 | 24.500 | 120.000 |
| Small Cyclops | A | boss | 24.242 | 120.000 | 24.000 | 120.000 |
| Giganotosaurus | S | ataque | 22.636 | 108.000 | 22.500 | 108.000 |
| Acrocantossauro | S | ataque | 22.373 | 108.000 | 22.000 | 108.000 |
| Rex | S | ataque | 18.000 | 108.000 | 18.000 | 108.000 |
| Rex Abissal | A | raid | 16.606 | 90.000 | 16.500 | 90.000 |
| Reaper Abissal | A | raid | 16.363 | 90.000 | 16.000 | 90.000 |
| Reaper Gen2 | A | raid | 16.242 | 90.000 | 16.000 | 90.000 |
| Reaper | A | raid | 16.121 | 90.000 | 16.000 | 90.000 |
| Small Drake Fogo | A | raid | 15.515 | 90.000 | 15.500 | 90.000 |
| Crystal Wyvern Blood | A | raid | 15.151 | 90.000 | 15.000 | 90.000 |
| Crystal Wyvern Ember | A | raid | 15.151 | 90.000 | 15.000 | 90.000 |
| Crystal Wyvern Tropical | B | ataque | 3.484 | 35.000 | 3.500 | 35.000 |
| Yutyrannus Abissal | A | ataque | 9.737 | 75.000 | 10.000 | 75.000 |
| Volcano Rex | A | ataque | 9.595 | 75.000 | 9.500 | 75.000 |
| Deinonychus | A | ataque | 9.525 | 75.000 | 9.500 | 75.000 |
| Puretotokage | A | ataque | 9.525 | 75.000 | 9.500 | 75.000 |
| Shimosaur | A | ataque | 9.454 | 75.000 | 9.500 | 75.000 |
| Megalosaurus Aberrante | A | ataque | 9.454 | 75.000 | 9.500 | 75.000 |
| Megalosaurus | A | ataque | 9.313 | 75.000 | 9.000 | 75.000 |
| Astrodelphis | A | locomocao | 6.868 | 42.000 | 7.000 | 42.000 |
| Desmodus | A | locomocao | 6.787 | 42.000 | 7.000 | 42.000 |
| Wyvern Aquática | A | locomocao | 6.464 | 42.000 | 6.500 | 42.000 |
| Small Hippocampus | A | locomocao | 6.303 | 42.000 | 6.500 | 42.000 |
| Small Dodowyvern | B | raid | 5.878 | 45.000 | 6.000 | 45.000 |
| Small Moeder | B | boss | 5.000 | 25.000 | 5.000 | 25.000 |
| Dakosaurus | B | ataque | 3.545 | 35.000 | 3.500 | 35.000 |
| Deinosuchus | B | ataque | 3.484 | 35.000 | 3.500 | 35.000 |
| Xiphactinus | B | ataque | 3.484 | 35.000 | 3.500 | 35.000 |
| Vulcanita | B | ataque | 3.484 | 35.000 | 3.500 | 35.000 |
| Thylacoleo Abissal | B | ataque | 3.424 | 35.000 | 3.500 | 35.000 |
| Concavenator | B | ataque | 3.424 | 35.000 | 3.500 | 35.000 |
| Rift Crawler | B | ataque | 3.424 | 35.000 | 3.500 | 35.000 |
| Cryolophosaurus | B | ataque | 3.333 | 35.000 | 3.500 | 35.000 |
| Kutsu-Ya-Ku | B | ataque | 3.333 | 35.000 | 3.500 | 35.000 |
| Brachiosaurus | B | utilitario | 2.318 | 15.000 | 2.500 | 15.000 |
| Therizinosaur Abissal | B | utilitario | 2.272 | 15.000 | 2.500 | 15.000 |
| Archelon | B | utilitario | 2.212 | 15.000 | 2.500 | 15.000 |
| Diru-Ya-Ku | C | ataque | 1.311 | 15.000 | 1.500 | 15.000 |
| Camarão-mantis | C | ataque | 1.244 | 15.000 | 1.500 | 15.000 |
| Onchopristis | C | ataque | 1.222 | 15.000 | 1.200 | 15.000 |
| Marlim (Istiophorus) | C | locomocao | 1.005 | 12.000 | 1.000 | 12.000 |
| Stegossauro Abissal | C | utilitario | 696 | 8.000 | 800 | 8.000 |
| Stereolepis | C | utilitario | 686 | 8.000 | 800 | 8.000 |
| Tiktaalik | C | utilitario | 671 | 8.000 | 800 | 8.000 |
| Tridacna | C | utilitario | 671 | 8.000 | 800 | 8.000 |
| Atum (Thunnus) | C | utilitario | 656 | 8.000 | 700 | 8.000 |
| Anquilossauro Abissal | C | utilitario | 646 | 8.000 | 700 | 8.000 |
| Qarmoutus | C | utilitario | 636 | 8.000 | 700 | 8.000 |
| Ocepechelon | C | utilitario | 636 | 8.000 | 700 | 8.000 |
| Malleocephalus | C | utilitario | 636 | 8.000 | 700 | 8.000 |
| Kathreptis | C | utilitario | 636 | 8.000 | 700 | 8.000 |
| Lagosta (Homarus) | C | utilitario | 636 | 8.000 | 700 | 8.000 |
| Baiacu (Takifugu) | C | utilitario | 621 | 8.000 | 700 | 8.000 |
| Mudpuppy | C | utilitario | 606 | 8.000 | **650** | 8.000 |
| Cavalo-marinho | C | utilitario | 595 | 8.000 | **650** | 8.000 |
| Narval (Monodon) | C | utilitario | 585 | 8.000 | **600** | 8.000 |
| Moschops Abissal | C | utilitario | 585 | 8.000 | **600** | 8.000 |

> **Nota geral:** A maioria das espécies está bem calibrada. Os principais ajustes são:
> - S+ boss (Dread/Ancient/IndoRaptor): leve redução para escalar com prestige_rank
> - C/B tier: leve aumento nos pisos mínimos
> - Astrodelphis/Desmodus: pequeno aumento por demanda de flyers raros

---

## 11. Estrutura de Taxas — Resumo Final

| Transação | Taxa atual | Taxa proposta | Destinação |
|-----------|-----------|---------------|-----------|
| Compra no catálogo | 0% | 0% | — |
| Venda no Mercado P2P | 0% | **3–5%** | Sink |
| Encomenda (α) | 25% sobre R | **20% sobre R** | Sink |
| Encomenda (β) | 35% sobre VM | **30% sobre VM** | Sink |
| Renovação licença (fidelidade) | 100% | **80%** | — |
| Listagem cosmética | — | **100–500 Â fixo** | Sink |

---

## 12. Indicadores de Saúde Econômica (KPIs Propostos)

| KPI | Fórmula | Alvo |
|-----|---------|------|
| Emissão mensal | Σ timed_bonus de todos jogadores | Monitorar |
| Drenagem mensal | Σ gastos em loja + fees | ≥ 60% emissão |
| Circulação P2P | Volume de transações mercado/mês | Crescente |
| Tempo médio para Rex | Dias até primeiro Rex de jogador novo | 45–90 dias |
| Concentração de riqueza | Top 10% hold de % total | < 60% |

---

*Proposta de Jul/2026 — sujeita a revisão e aprovação da equipe admin.*  
*Baseada em dados reais do sistema — sem invenção de números.*
