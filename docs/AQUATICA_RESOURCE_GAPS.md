# Aquatica — Gaps de recursos (wiki × catálogo × refs)

> ⚠️ **Escopo superado.** Ver auditoria completa em [`docs/RESOURCE_ICON_COMPLETE_AUDIT.md`](RESOURCE_ICON_COMPLETE_AUDIT.md) (143 itens wiki, 56 resource-like no catálogo, 54 refs PNG, 100% cobertura).

> Gerado em **2026-07-09** a partir de [Aquatica#Resources](https://ark.wiki.gg/wiki/Aquatica#Resources) e cruzamento com `plugin/CustomShop/configs/config.json`, `refs/resource_icons/`, `dododex_resource_slugs.json` e `ark_species_registry.json`.

## Resumo executivo

| Métrica | Valor |
|---------|-------|
| Recursos listados na wiki (seção **Resources**) | **7** |
| No catálogo (`abyss_*` e/ou `rec_*`) | **7 / 7** (100%) |
| Com `refs/resource_icons/*.png` | **7 / 7** (5 wiki + 2 usuário) |
| Ausentes no DodoDex (sitemap 2026-07-09) | **7 / 7** |
| Faltando no catálogo (só Resources) | **0** |

**Conclusão:** o catálogo de loja já cobre todos os recursos base da DLC. Referências visuais internas **completas** em `refs/resource_icons/` (5 via [ark.wiki.gg](https://ark.wiki.gg/wiki/Aquatica#Resources), 2 fornecidas pelo usuário). Gap restante: ícones gerados para a loja (`static/species/icons/generated/`) e entradas `rec_*` em kit para os 5 que ainda não têm pacote bulk.

---

## Fonte wiki — seção Resources

Lista oficial em [Aquatica#Resources](https://ark.wiki.gg/wiki/Aquatica#Resources):

1. Aqualyrium
2. Barnacle
3. Crystallized Wood
4. Fish Scale
5. Hardened Steel Ingot
6. Manganese
7. Seaweed

Blueprint path comum: `/Game/Abyss/CoreBlueprints/Resources/PrimalItemResource_{Name}.PrimalItemResource_{Name}`

---

## Cruzamento completo

| # | Wiki (EN) | Nome PT (catálogo) | Chave catálogo | Chave `rec_*` kit | `refs/resource_icons/` | DodoDex | Status |
|---|-----------|-------------------|----------------|-------------------|------------------------|---------|--------|
| 1 | Aqualyrium | Aqualyrium | `abyss_aqualyrium` | — | ✅ `rec_aqualyrium.png` (wiki) | ❌ ausente | **Ref wiki OK** |
| 2 | Barnacle | Craca | `abyss_barnacle` | — | ✅ `rec_barnacle.png` (wiki) | ❌ ausente | **Ref wiki OK** |
| 3 | Crystallized Wood | Madeira Cristalizada | `abyss_crystallized_wood` | — | ✅ `rec_crystallizedWood.png` (wiki) | ❌ ausente | **Ref wiki OK** |
| 4 | Fish Scale | Escama de Peixe | `abyss_fish_scale` | — | ✅ `rec_fishScale.png` (wiki) | ❌ ausente | **Ref wiki OK** |
| 5 | Hardened Steel Ingot | Lingote de Aço Endurecido | `abyss_hardened_steel` | `rec_HardenedSteelIngot` | ✅ `rec_HardenedSteelIngot.png` (usuário) | ❌ ausente | **Completo** (ref usuário) |
| 6 | Manganese | Manganês | `abyss_manganese` | `rec_manganese` | ✅ `rec_manganese.png` (usuário) | ❌ ausente | **Completo** (ref usuário) |
| 7 | Seaweed | Alga Marinha | `abyss_seaweed` | — | ✅ `rec_seaweed.png` (wiki) | ❌ ausente | **Ref wiki OK** |

### Duplicidade `abyss_*` vs `rec_*`

- `abyss_hardened_steel` e `rec_HardenedSteelIngot` apontam para o **mesmo blueprint**; o `rec_*` é pacote bulk (1000×) para kits VIP/emergência.
- `abyss_manganese` e `rec_manganese` — mesma situação.
- Os outros 5 recursos existem só como `abyss_*` (item avulso na loja). Não há `rec_aqualyrium`, `rec_barnacle`, etc.

---

## Itens Aquatica relacionados (fora de #Resources)

Presentes no catálogo mas **não** na seção Resources da wiki (sementes / consumíveis):

| Wiki | Chave catálogo | Categoria wiki | Ref |
|------|----------------|----------------|-----|
| Cucumis Seed | `abyss_seed_cucumis` | Seeds | ✅ `refs/resource_icons/abyss_seed_cucumis.png` (wiki) |
| Oryraise Seed | `abyss_seed_rice` | Seeds | ✅ `refs/resource_icons/abyss_seed_rice.png` (wiki) |
| Plant Species W Seed | `abyss_seed_plantspeciesw` | Seeds | ✅ `refs/resource_icons/abyss_seed_plantspeciesw.png` (wiki) |
| Cucumis | — | Consumables | **não catalogado** |
| Oryraise / Oryraise Ball | — | Consumables | **não catalogado** |
| Plant Species W Fruit | — | Consumables | **não catalogado** |
| Dried Seaweed | — | Consumables (craft) | **não catalogado** |

Sementes sincronizadas via `tools/sync_abyss_shop_catalog.py` a partir de `ark_species_registry.json`.

---

## Pipeline de referências

| Artefato | Papel |
|----------|-------|
| `refs/resource_icons/{rec_key}.png` | Guia interno para ícones de recursos `rec_*` (DodoDex ou usuário) |
| `refs/species_icons/abyss_{name}.png` | Guia interno para ícones de itens Abyss no pipeline de espécies |
| `plugin/arkshop_web/data/wiki_resource_refs.json` | Mapeamento `abyss_*` → refs internas da wiki (Aquatica) |
| `tools/fetch_wiki_aquatica_resource_refs.py` | Baixa refs da wiki para `refs/resource_icons/` (uso interno) |
| `plugin/arkshop_web/data/dododex_resource_slugs.json` | Mapeamento `rec_*` → slug DodoDex |
| `tools/update_catalog_resources.py` | Atualiza pacotes `rec_*` em `docs/config.json` (não inclui Aquatica além de Mn/Steel) |
| `tools/fetch_dododex_resource_references.py` | Baixa refs do DodoDex (uso interno, ver ATTRIBUTION) |
| `tools/sync_abyss_shop_catalog.py` | Sincroniza `abyss_*` do registro → `config.json` |

### DodoDex

Busca no sitemap (`2299` itens, 2026-07-09): **nenhum** slug contendo `aqualyrium`, `barnacle`, `crystallized`, `fish-scale`, `hardened-steel`, `manganese`, `seaweed`, `cucumis`, `oryraise` ou `plant-species-w`.

Itens Aquatica são **exclusivos da DLC** e ainda não indexados no DodoDex. Refs Aquatica em `wiki_resource_refs.json` (`image_source: wiki_reference_internal`). `MANUAL_SLUG_OVERRIDES` em `fetch_dododex_resource_references.py` marca `rec_HardenedSteelIngot` e `rec_manganese` como `None`.

### Wiki (imagens)

Ícones de item disponíveis na wiki via API MediaWiki (`File:{Name}.png`, 256×256). Baixados em **2026-07-09** com `tools/fetch_wiki_aquatica_resource_refs.py` → `plugin/arkshop_web/data/wiki_resource_refs.json`.

**Uso:** referência interna para geração AI apenas — **não** redistribuir na loja (ver `plugin/arkshop_web/static/species/ATTRIBUTION.md` — CC BY-NC-SA / © Studio Wildcard).

`rec_HardenedSteelIngot.png` e `rec_manganese.png` mantidos da ref fornecida pelo usuário (não sobrescritos pela wiki).

---

## Gaps por categoria

### ✅ No catálogo com ref (`refs/resource_icons/`)

| Chave catálogo | Arquivo | Fonte |
|----------------|---------|-------|
| `abyss_aqualyrium` | `refs/resource_icons/rec_aqualyrium.png` | wiki (2026-07-09) |
| `abyss_barnacle` | `refs/resource_icons/rec_barnacle.png` | wiki |
| `abyss_crystallized_wood` | `refs/resource_icons/rec_crystallizedWood.png` | wiki |
| `abyss_fish_scale` | `refs/resource_icons/rec_fishScale.png` | wiki |
| `abyss_seaweed` | `refs/resource_icons/rec_seaweed.png` | wiki |
| `abyss_hardened_steel` / `rec_HardenedSteelIngot` | `refs/resource_icons/rec_HardenedSteelIngot.png` | usuário |
| `abyss_manganese` / `rec_manganese` | `refs/resource_icons/rec_manganese.png` | usuário |
| `abyss_seed_cucumis` | `refs/resource_icons/abyss_seed_cucumis.png` | wiki |
| `abyss_seed_rice` | `refs/resource_icons/abyss_seed_rice.png` | wiki |
| `abyss_seed_plantspeciesw` | `refs/resource_icons/abyss_seed_plantspeciesw.png` | wiki |

### ⚠️ No catálogo SEM ref gerada para loja

Todos os recursos têm ref interna. Gap restante: ícones AI/SVG em `static/species/icons/` para exibição na loja.

### ❌ Na wiki (Resources) e ainda NÃO no catálogo

*Nenhum.*

---

## Chaves `rec_*` sugeridas (kits / DodoDex futuro)

Para paridade com `rec_manganese` e `rec_HardenedSteelIngot` se forem adicionados a kits VIP:

| Chave sugerida | Blueprint | Descrição sugerida |
|----------------|-----------|-------------------|
| `rec_aqualyrium` | `...PrimalItemResource_Aqualyrium...` | Aqualyrium (100×) |
| `rec_barnacle` | `...PrimalItemResource_Barnacle...` | Craca (100×) |
| `rec_crystallizedWood` | `...PrimalItemResource_CrystallizedWood...` | Madeira Cristalizada (100×) |
| `rec_fishScale` | `...PrimalItemResource_FishScale...` | Escama de Peixe (100×) |
| `rec_seaweed` | `...PrimalItemResource_Seaweed...` | Alga Marinha (1000×) |

Adicionar em `tools/update_catalog_resources.py` → `NEW_REC_ITEMS` e em `dododex_resource_slugs.json` com `image_source: "wiki_reference_internal"` (ver `wiki_resource_refs.json`) até o DodoDex indexar a DLC.

---

## Próximos passos

1. **Dev:** rodar `python tools/generate_ai_species_icons.py --species abyss_aqualyrium abyss_barnacle ...` usando refs em `refs/resource_icons/`.
2. **Dev:** opcionalmente criar entradas `rec_*` para kits VIP.
3. **Monitorar** DodoDex — quando indexar Aquatica, atualizar `fetch_dododex_resource_references.py`.

---

## Referências

- Wiki: https://ark.wiki.gg/wiki/Aquatica#Resources
- Mapeamento wiki: `plugin/arkshop_web/data/wiki_resource_refs.json`
- Registro Abyss: `plugin/arkshop_web/data/ark_species_registry.json`
- Checklist ícones: `docs/SPECIES_ICON_REFERENCE_CHECKLIST.md`
- Atribuição legal: `plugin/arkshop_web/static/species/ATTRIBUTION.md`
