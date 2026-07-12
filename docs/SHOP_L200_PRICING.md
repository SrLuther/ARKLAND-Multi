# Preços L200 na loja CustomShop

## Regras aprovadas (Jul/2026)

| Símbolo | Significado |
|--------|-------------|
| `P₁` | `Price` do item L1 (`Type:dino`, `Level: 1`) |
| `M` | `root_value` da espécie em `market_species_defaults.json` (opção A) |
| `k` | Markup L1→L200 — constante **`1.40`** (`L200_MARKUP_K` em `market_economy.py`, configurável) |
| Teto | `P₂₀₀ ≤ 0,75 × M` (`L200_CAP_RATIO`) |

**Fórmula:**

```text
P200 = round(clamp(P1 × 1.40, P1+1, 0.75×M))
```

Se `0.75×M ≤ P1` → **não listar** L200 dessa espécie (entrada `*_l200` removida/omitida).

### Exemplos

| P1 | M | Cap 0.75×M | P200 | Nota |
|----|---|------------|------|------|
| 18000 | 40000 | 30000 | **25200** | markup 1.40 |
| 20000 | 30000 | 22500 | **22500** | bate no teto |
| 18000 | 18000 | 13500 | — | skip (`cap ≤ P1`) |

## Catálogo

- IDs: `{id_l1}_l200` (ex.: `rex_femea_l200`)
- Mesmo blueprint / ForceTame / Gender do L1; `Dinos[0].Level = 200`
- Sync de `M` via `build_catalog_economy_map()` → `root_value`

## Web Store

- Aba **🦕 Dinos** → só nível 1
- Aba **🦖 Dinos 200** → só nível 200 (`data-catalog-tab="dinos200"`)

## Apply idempotente

```bash
python tools/apply_shop_l200_prices.py
python tools/apply_shop_l200_prices.py --dry-run -v
```

Grava `plugin/CustomShop/configs/config.json` e `bin/config.json`.

## Testes

```bash
python -m pytest plugin/arkshop_web/tests/test_l200_pricing.py -q
```
