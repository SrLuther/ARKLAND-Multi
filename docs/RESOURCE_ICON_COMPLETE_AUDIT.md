# Auditoria completa — ícones de recursos (wiki × catálogo × refs)

> Gerado em **2026-07-09** — escopo ampliado: página [Aquatica](https://ark.wiki.gg/wiki/Aquatica) **inteira**, todos os `rec_*` (43), todos os `abyss_*` vendidos, kit recursos e `refs/resource_icons/`.

Substitui o escopo limitado de `docs/AQUATICA_RESOURCE_GAPS.md` (que olhava só 7 recursos + 3 sementes).

---

## Resumo executivo (números reais)

| Métrica | Valor |
|---------|-------|
| **Itens na wiki Aquatica (página inteira)** | **143** |
| — Resources | 7 |
| — Seeds | 3 |
| — Consumables | 37 |
| — Trophies and Tributes | 12 |
| — Weapons, Armor, and Tools | 17 |
| — Structures | 48 |
| — Saddles | 8 |
| — Cosmetics | 2 |
| — Other (fogos) | 3 |
| — Artifacts | 3 |
| — Abyssal Pearls | 3 |
| **Itens Aquatica vendidos no catálogo** | **13** |
| **Pacotes `rec_*` no catálogo** | **43** |
| **`abyss_*` Category=Recursos** | **9** |
| **Outros Category=Recursos (ex. `daco_sushi`)** | **1** |
| **`abyss_*` Type=item (incl. veículos, Mn)** | **12** |
| **Total itens resource-like vendidos** | **56** |
| **PNGs em `refs/resource_icons/`** | **54** (2 refs compartilhadas) |
| **Catálogo COM ref interna** | **56 / 56 (100%)** |
| **Catálogo SEM ref** | **0** |
| **Itens no Kit Recursos Emergencial** | **29** (`Kits.recursos`) |
| **`rec_*` com imagem DodoDex** | **41 / 43** |
| **`rec_*` só ref usuário/wiki (sem DodoDex)** | **2** (`rec_HardenedSteelIngot`, `rec_manganese`) |
| **Wiki Aquatica NÃO no catálogo** | **130** |
| **Catálogo vanilla NÃO na wiki Aquatica** | **43** (`rec_*` base game) |

### O que mudou nesta execução

Baixados da wiki via `tools/fetch_wiki_aquatica_resource_refs.py`:

| Chave catálogo | Arquivo ref | Status |
|----------------|-------------|--------|
| `daco_sushi` | `daco_sushi.png` | **baixado** |
| `abyss_hover_sail` | `abyss_hover_sail.png` | **baixado** |
| `abyss_hover_skiff` | `abyss_hover_skiff.png` | **baixado** |

Já existiam (execuções anteriores): 7 recursos Abyss, 3 sementes. Ignorados (ref do usuário, não sobrescritos): `rec_HardenedSteelIngot.png`, `rec_manganese.png`.

---

## 1. Wiki Aquatica — página inteira

Fonte: https://ark.wiki.gg/wiki/Aquatica (seção **Items** e subseções, jul/2025 DLC).

### Resources (7) — todos no catálogo ✅

| Wiki | Chave catálogo | Ref |
|------|----------------|-----|
| Aqualyrium | `abyss_aqualyrium` | `rec_aqualyrium.png` |
| Barnacle | `abyss_barnacle` | `rec_barnacle.png` |
| Crystallized Wood | `abyss_crystallized_wood` | `rec_crystallizedWood.png` |
| Fish Scale | `abyss_fish_scale` | `rec_fishScale.png` |
| Hardened Steel Ingot | `abyss_hardened_steel` / `rec_HardenedSteelIngot` | `rec_HardenedSteelIngot.png` |
| Manganese | `abyss_manganese` / `rec_manganese` | `rec_manganese.png` |
| Seaweed | `abyss_seaweed` | `rec_seaweed.png` |

### Seeds (3) — todos no catálogo ✅

| Wiki | Chave catálogo | Ref |
|------|----------------|-----|
| Cucumis Seed | `abyss_seed_cucumis` | `abyss_seed_cucumis.png` |
| Oryraise Seed | `abyss_seed_rice` | `abyss_seed_rice.png` |
| Plant Species W Seed | `abyss_seed_plantspeciesw` | `abyss_seed_plantspeciesw.png` |

### Consumables (37) — 1 no catálogo

| No catálogo | Ref | Fora do catálogo (36) |
|-------------|-----|------------------------|
| Daco Sushi → `daco_sushi` | `daco_sushi.png` | Air Bladder, Air Jar, Broth of Atlan, Cooked Supreme Fish Meat, Cucumis, Dried Seaweed, Earthworms, Filled Dipping Net, Fish Jerky, Gilly Feast, Homarus Egg, Infected Barnacle/Blubber/Fin/Liver/Meat/Scale/Stomach/Tooth, Kathreptis Egg, Kibble Mash, Mantis Shrimp Egg, Mudpuppy Egg, Ocepechelon Egg, Oceans Bounty, Oryraise, Oryraise Ball, Plant Species W Fruit, Prime Fish Jerky, Raw Supreme Fish Meat, Sea Dragon Soup, Takifugu Egg, Tiktaalik Egg, Vulcanite Egg, Water Wyvern Egg, Worm Gum |

### Veículos Abyss vendidos (wiki: Structures)

| Wiki | Chave catálogo | Ref |
|------|----------------|-----|
| Tek Thalassian Hoversail | `abyss_hover_sail` | `abyss_hover_sail.png` |
| Unassembled TEK Thalassian Hover Skiff | `abyss_hover_skiff` | `abyss_hover_skiff.png` |

### Restante da wiki (130 itens) — NÃO no catálogo

- **Trophies and Tributes** (12): Alpha Water Talon, Cymathoa/Fractalis/Pygocentrus/Vulcanithys flags & trophies, Monodon Horn, Onchopristis Blade, Water Talon
- **Weapons, Armor, and Tools** (17): Pearl armor set, Thalassian weapons, Tek Trident, Dipping Net, etc.
- **Structures** (46 restantes): Pearl building set, Hydrosphere, Infectarium, Rift Generator, Stinger Ship, Tek Ocean Platform, Underwater Crop Plot, etc.
- **Saddles** (8): Dakosaurus, Homarus, Malleocephalus, Monodon, Ocepechelon, Onchopristis, Seahorse
- **Cosmetics** (2): Tribal Canoe/Raft Costume
- **Other** (3): Anniversary Fireworks
- **Artifacts** (3): Fallen, Mighty, Seeking
- **Pearls** (3): Blue/Green/Red Abyssal Pearl

---

## 2. Catálogo — todos os resource-like

### `rec_*` — 43 pacotes bulk

Todos com `refs/resource_icons/rec_{key}.png`. Fonte: DodoDex (41) ou usuário (2 Abyss).

<details>
<summary>Lista completa (43)</summary>

`rec_HardenedSteelIngot`, `rec_bolo`, `rec_cement`, `rec_charcoal`, `rec_chitin`, `rec_cookedmeat`, `rec_crystal`, `rec_electronics`, `rec_element`, `rec_elementore`, `rec_fiber`, `rec_flint`, `rec_gasoline`, `rec_gemblue`, `rec_gemgreen`, `rec_gemred`, `rec_gunpowder`, `rec_hide`, `rec_honey`, `rec_keratin`, `rec_manganese`, `rec_medicalbrew`, `rec_metal`, `rec_metalingot`, `rec_mutagel`, `rec_narcotic`, `rec_obsidian`, `rec_oil`, `rec_organicpolymer`, `rec_pnegra`, `rec_polymer`, `rec_propellant`, `rec_rareflower`, `rec_raremushroom`, `rec_sand`, `rec_sap`, `rec_silicon`, `rec_sparkpowder`, `rec_stimulant`, `rec_stone`, `rec_thatch`, `rec_wood`, `rec_wyvernmilk`

</details>

### `abyss_*` vendidos como item — 12

| Chave | Categoria | Ref | Fonte ref |
|-------|-----------|-----|-----------|
| `abyss_aqualyrium` | Recursos | `rec_aqualyrium.png` | wiki |
| `abyss_barnacle` | Recursos | `rec_barnacle.png` | wiki |
| `abyss_crystallized_wood` | Recursos | `rec_crystallizedWood.png` | wiki |
| `abyss_fish_scale` | Recursos | `rec_fishScale.png` | wiki |
| `abyss_hardened_steel` | Recursos | `rec_HardenedSteelIngot.png` | usuário |
| `abyss_seaweed` | Recursos | `rec_seaweed.png` | wiki |
| `abyss_seed_cucumis` | Recursos | `abyss_seed_cucumis.png` | wiki |
| `abyss_seed_plantspeciesw` | Recursos | `abyss_seed_plantspeciesw.png` | wiki |
| `abyss_seed_rice` | Recursos | `abyss_seed_rice.png` | wiki |
| `abyss_manganese` | Geral | `rec_manganese.png` | usuário (compartilha com `rec_manganese`) |
| `abyss_hover_sail` | Veículos | `abyss_hover_sail.png` | wiki (2026-07-09) |
| `abyss_hover_skiff` | Veículos | `abyss_hover_skiff.png` | wiki (2026-07-09) |

### Outros

| Chave | Categoria | Ref |
|-------|-----------|-----|
| `daco_sushi` | Recursos | `daco_sushi.png` (wiki, 2026-07-09) |

### Kit Recursos Emergencial — 29 linhas

`Kits.recursos` em `plugin/CustomShop/configs/config.json`. Todos os blueprints do kit têm entrada `rec_*` correspondente com ref.

Conteúdo (via `tools/update_catalog_resources.py` → `KIT_RECURSOS_CONTENTS`):

`rec_stone`, `rec_wood`, `rec_thatch`, `rec_flint`, `rec_fiber`, `rec_hide`, `rec_cookedmeat`, `rec_charcoal`, `rec_metal`, `rec_metalingot`, `rec_obsidian`, `rec_crystal`, `rec_chitin`, `rec_keratin`, `rec_silicon`, `rec_cement`, `rec_polymer`, `rec_electronics`, `rec_oil`, `rec_sparkpowder`, `rec_gunpowder`, `rec_narcotic`, `rec_medicalbrew`, `rec_stimulant`, `rec_pnegra`, `rec_gasoline`, `rec_element`, `rec_mutagel`, `rec_elementore`

**Nota:** kit não inclui recursos Abyss (Aqualyrium, Mn bulk avulso, etc.) — só vanilla/Aberration/Genesis2.

---

## 3. `refs/resource_icons/` — inventário

| Métrica | Valor |
|---------|-------|
| PNGs no disco | **54** |
| Arquivos únicos esperados | 54 (2 pares compartilham ref) |
| Refs compartilhadas | `abyss_hardened_steel` ↔ `rec_HardenedSteelIngot`; `abyss_manganese` ↔ `rec_manganese` |
| Refs órfãs (sem chave catálogo) | **0** |

### Por fonte

| Fonte | Qtd aprox. | Itens |
|-------|------------|-------|
| DodoDex | 41 | `rec_*` vanilla (exc. 2 Abyss) |
| Wiki ark.wiki.gg | 13 | 7 recursos + 3 sementes + daco + 2 veículos |
| Usuário | 2 | `rec_HardenedSteelIngot`, `rec_manganese` |

---

## 4. Gaps — lista completa

### ❌ Recursos no catálogo SEM ref

**Nenhum.** 56/56 cobertos.

### ❌ Recursos na wiki Aquatica NÃO no catálogo

**130 itens** — ver seção 1 (trophies, armas, estruturas, selas, consumíveis restantes, artefatos, pérolas). Não são vendidos na loja hoje.

Prioridade se expandir loja Aquatica:
1. Consumíveis craftáveis (Broth of Atlan, Dried Seaweed, Oryraise Ball…)
2. Infected augments (Barnacle, Blubber, Fin…)
3. Pearl armor / Thalassian weapons (categoria Armas, não Recursos)

### ℹ️ Recursos no catálogo NÃO na wiki Aquatica (vanilla/mods)

**43 `rec_*`** — recursos base do jogo (Pedra, Madeira, Elemento, Mutagel, etc.). Refs via DodoDex, não wiki Aquatica.

**`abyss_manganese`** — na wiki (Resources), mas Category=Geral no catálogo (não Recursos).

---

## 5. Ferramentas

| Script | Função |
|--------|--------|
| `tools/audit_resource_icons.py` | Auditoria catálogo × refs × wiki (rodar após mudanças) |
| `tools/fetch_wiki_aquatica_resource_refs.py` | Baixa refs wiki para itens Abyss/Aquatica **vendidos** (13 chaves) |
| `tools/fetch_dododex_resource_references.py` | Baixa refs DodoDex para `rec_*` vanilla |
| `tools/update_catalog_resources.py` | Mantém `rec_*` e kit recursos em `docs/config.json` |
| `tools/sync_abyss_shop_catalog.py` | Sincroniza `abyss_*` do registro de espécies |

### Mapeamentos JSON

- `plugin/arkshop_web/data/wiki_resource_refs.json` — 13 itens Abyss/Aquatica (wiki)
- `plugin/arkshop_web/data/dododex_resource_slugs.json` — 43 `rec_*` (DodoDex)

---

## 6. Próximos passos (ação real)

1. **Ícones da loja:** gerar SVG/WebP em `static/species/icons/generated/` para os 13 itens Abyss + `daco_sushi` (refs internas prontas).
2. **Opcional catálogo:** adicionar `rec_aqualyrium`, `rec_barnacle`, etc. para kits VIP (paridade com `rec_manganese`).
3. **Opcional expansão:** decidir quais dos 130 itens wiki adicionar à loja antes de buscar mais refs.
4. **Monitorar DodoDex:** quando indexar Aquatica, atualizar `fetch_dododex_resource_references.py`.

---

## Referências

- Wiki completa: https://ark.wiki.gg/wiki/Aquatica
- Gap anterior (escopo reduzido): `docs/AQUATICA_RESOURCE_GAPS.md`
- Atribuição legal: `plugin/arkshop_web/static/species/ATTRIBUTION.md`
