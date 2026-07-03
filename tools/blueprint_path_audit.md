# Auditoria de blueprint paths — CustomShop

**Data:** 2026-07-02  
**Escopo:** `plugin/CustomShop/configs/config.json` (canônico) — 1182 referências Blueprint/Command  
**Padrões verificados:** `Armor/Hide→Leather`, `Resources/PrimalItemConsumable`, `Armor/Tek→TEK`, `Structures/Tek→tek` (subset), fragmentos JSON, sufixo `_BP_C`

## Resumo

| Métrica | Valor |
|---------|-------|
| Paths incorretos encontrados | **10** (11 ocorrências no config) |
| Corrigidos no canônico | **10** |
| Categorias afetadas | Armadura Tek (4), Consumível Aberration (1), Estruturas Tek (5) |
| Já corretos (Hide/Leather) | Conjunto couro no `starter` e demais tiers vanilla |

## Correções aplicadas

### Armadura Tek — pasta `Armor/Tek/` → `Armor/TEK/`

| Path errado | Path correto | Item/kit |
|-------------|--------------|----------|
| `.../Armor/Tek/PrimalItemArmor_TekGloves...` | `.../Armor/TEK/PrimalItemArmor_TekGloves...` | `armor_tek` |
| `.../Armor/Tek/PrimalItemArmor_TekBoots...` | `.../Armor/TEK/PrimalItemArmor_TekBoots...` | `armor_tek_bp` |
| `.../Armor/Tek/PrimalItemArmor_TekBoots...` | `.../Armor/TEK/...` | `tekgrams` (UnlockEngram) |
| `.../Armor/Tek/PrimalItemArmor_TekShirt...` | `.../Armor/TEK/...` | `tekgrams` |
| `.../Armor/Tek/PrimalItemArmor_TekGloves...` | `.../Armor/TEK/...` | `tekgrams` |
| `.../Armor/Tek/PrimalItemArmor_TekPants...` | `.../Armor/TEK/...` | `tekgrams` |

```text
cheat giveitem "Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves'" 1 100 0
```

### Consumível — `Resources/` → `Items/Consumables/`

| Path errado | Path correto | Item/kit |
|-------------|--------------|----------|
| `/Game/Aberration/CoreBlueprints/Resources/PrimalItemConsumable_NamelessVenom...` | `/Game/Aberration/CoreBlueprints/Items/Consumables/PrimalItemConsumable_NamelessVenom...` | `kitboss_rockwell` |

```text
cheat giveitem "Blueprint'/Game/Aberration/CoreBlueprints/Items/Consumables/PrimalItemConsumable_NamelessVenom.PrimalItemConsumable_NamelessVenom'" 20 0 0
```

### Estruturas Tek — pasta `Structures/Tek/` → `Structures/tek/` (assets específicos)

| Path errado | Path correto | Item/kit |
|-------------|--------------|----------|
| `.../Structures/Tek/PrimalItemStructure_TekRoof...` | `.../Structures/tek/PrimalItemStructure_TekRoof...` | `tekgrams` |
| `.../Structures/Tek/PrimalItemStructure_TekWall_Sloped_Left...` | `.../Structures/tek/...` | `tekgrams` |
| `.../Structures/Tek/PrimalItemStructure_TekWall_Sloped_Right...` | `.../Structures/tek/...` | `tekgrams` |
| `.../Structures/Tek/PrimalItemStructure_TekStairs...` | `.../Structures/tek/...` | `tekgrams` |
| `.../Structures/Tek/PrimalItemStructure_TekFenceFoundation...` | `.../Structures/tek/PrimalItemStructure_Tekfencefoundation...` | `tekgrams` |

```text
cheat UnlockEngram "Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_TekStairs.PrimalItemStructure_TekStairs'"
```

> **Nota:** A maioria das estruturas Tek vanilla permanece em `Structures/Tek/` (maiúsculo). Apenas escadas, telhados inclinados, muro inclinado e fence foundation usam `Structures/tek/` (minúsculo), conforme [wiki.gg Table of Tekgrams](https://ark.wiki.gg/wiki/Table_of_Tekgrams).

## Já cobertos em `_KNOWN_BLUEPRINT_FIXES` (re-import ArkShop)

| Padrão | Exemplo |
|--------|---------|
| Carne crua em Resources | `PrimalItemConsumable_RawMeat` |
| Couro em Armor/Hide | 5 peças `PrimalItemArmor_Hide*` → `Armor/Leather/` |

## Verificado — sem problemas

- **Armaduras vanilla:** Cloth, Leather (ex-Hide), Metal/Flak, Ghillie, Hazard, Riot, SCUBA — pastas corretas
- **Recursos (`PrimalItemResource_*`):** pasta `Resources/` é correta para materiais
- **Selas:** `Armor/Saddles/` — OK
- **Fragmentos JSON malformados:** nenhum no catálogo atual
- **Sufixo `_BP_C` em kits:** nenhum

## Cópias espelho ainda desatualizadas

Os mesmos paths errados permanecem em:

- `docs/config.json` (3 ocorrências Tek armor + NamelessVenom)
- `plugin/CustomShop/bin/config.json` (11 ocorrências — espelho de build)
- `tools/tek_unlock_commands.txt` (referência histórica)
- `tools/_compare_tek_boss_unlocks.py` (`BOSS_PATHS` — alguns Tek armor ainda com `Armor/Tek/`)

Recomendação: re-sincronizar `bin/` e `docs/` a partir do canônico ou rodar `sanitize_catalog_blueprints` nelas.

## Código atualizado

- `src/shop_catalog_import.py` — `_KNOWN_BLUEPRINT_FIXES` + `apply_known_blueprint_fixes()` + sanitização de `Commands`
- `tests/test_shop_catalog_import.py` — 5 novos testes
