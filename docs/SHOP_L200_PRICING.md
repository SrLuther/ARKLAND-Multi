# Preços L200 na loja CustomShop

## Regras aprovadas (Jul/2026 — opção A)

| Símbolo | Significado |
|--------|-------------|
| `P₁` / `R` | `Price` L1 = `root_value` da espécie em `market_species_defaults.json` |
| `B` | `premium_budget` da espécie |
| `V254` | Valor de mercado full-254 (Q=1): `min(R + B, market_absolute_max)` |
| `market_absolute_max` | Teto global (`_floor_quality`, default **150 000**) |
| `ratio` | Fração de V254 para L200 — constante **`0.40`** (`L200_OF_V254_RATIO`) |

**Fórmula:**

```text
V254 = min(R + B, market_absolute_max)
P200 = round(0.40 × V254)
```

Se `P200 ≤ P1` → **não listar** L200 dessa espécie (entrada `*_l200` removida/omitida; raro com os dados atuais).

Um dino nível 200 na loja **não** tem stats de breeding (Q≪1); daí o preço ser ~40% do valor de mercado full-254, não um markup sobre o L1.

### Exemplos

| Espécie | R | B | V254 | P200 | Nota |
|---------|---|---|------|------|------|
| Indominus | 28000 | 122000 | **150000** | **60000** | bate no teto global |
| R=18000, B=50000 | 18000 | 50000 | 68000 | **27200** | sem cap |
| R=10000, B=0 | 10000 | 0 | 10000 | — | skip (`P200=4000 ≤ P1`) |

## Catálogo

- IDs: `{id_l1}_l200` (ex.: `rex_femea_l200`) — o sufixo `_femea` no ID é histórico do L1; **não** implica sexo fixo no L200
- Mesmo blueprint / ForceTame do L1; `Dinos[0].Level = 200`
- **Sexo = aleatório**: campo `Gender` omitido (plugin só força sexo se `male`/`female`; vazio = spawn random)
- Name/Description sem «Fêmea» (não sugerir sexo fixo)
- Sync de R/B via `build_catalog_economy_map()` → `root_value` / `premium_budget`
- L1 alinhado a R: `python tools/sync_shop_l1_prices_from_root.py` (também recalcula kits `*_pack10` a 25% off)

## Web Store

- Aba **🦕 Dinos** → só nível 1
- Aba **🦖 Dinos 200** → só nível 200 (`data-catalog-tab="dinos200"`)

## Apply idempotente

```bash
python tools/sync_shop_l1_prices_from_root.py
python tools/apply_shop_l200_prices.py
python tools/apply_shop_l200_prices.py --dry-run -v
```

Grava `plugin/CustomShop/configs/config.json` e `bin/config.json`.

## Testes

```bash
python -m pytest plugin/arkshop_web/tests/test_l200_pricing.py -q
```
