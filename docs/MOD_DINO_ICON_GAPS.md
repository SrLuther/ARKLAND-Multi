# Lacunas de ícones — dinos de MOD

> Gerado em **2026-07-09 10:46 UTC** por `tools/audit_mod_dino_icon_gaps.py`. Auditoria apenas — não gera ícones.

## Resumo

| Métrica | Valor |
|---------|-------|
| Dinos de mod rastreados (catálogo + registro) | **64** |
| Dinos de mod no catálogo (`config.json` Type=dino) | **64** |
| Espécies mod só no registro (fora do catálogo) | **0** |
| Sem mapeamento em `market_species_defaults` | **48** |
| Com WebP AI (`generated/*.webp`) | **0** |
| Só SVG procedural (badge) | **43** |
| Na fila de regeneração | **0** |
| Sem ícone (fallback de tier) | **21** |
| WebP totais no disco | **92** |
| Referências em `refs/species_icons/` | **101** |

### Status no catálogo (loja)

- **SVG_ONLY**: 43
- **NO_ICON**: 21

### Por pacote de mod

| Pacote | Total | WebP | SVG only | Regen | Sem ícone |
|--------|-------|------|----------|-------|-----------|
| ARK Additions | 7 | 0 | 7 | 0 | 0 |
| Abyss | 28 | 0 | 28 | 0 | 0 |
| Brighamia | 3 | 0 | 3 | 0 | 0 |
| Grand Hunt | 4 | 0 | 4 | 0 | 0 |
| Indominus Rex | 2 | 0 | 1 | 0 | 1 |
| SmallBosses | 20 | 0 | 0 | 0 | 20 |

---

## Prioridade — catálogo sem ícone adequado

Ordem: **NO_ICON** (pior) → **SVG_ONLY** (badge genérico) → **NEEDS_REGEN** (WebP existente mas reprovado).

| # | species_key | display_name | mod | catalog_item_id | status | ref salva? | ref sugerida |
|---|-------------|--------------|-----|-------------------|--------|------------|--------------|
| 1 | `indoraptor` | IndoRaptor | Indominus Rex | `indoraptor, indoraptor_femea` | NO_ICON | não | `refs/species_icons/indoraptor.png` |
| 2 | `sb_crystal_blood` | Crystal Wyvern Blood Descendant | SmallBosses | `sb_crystal_blood, sb_crystal_blood_200` | NO_ICON | não | `refs/species_icons/sb_crystal_blood.png` |
| 3 | `sb_crystal_ember` | Crystal Wyvern Ember Descendant | SmallBosses | `sb_crystal_ember, sb_crystal_ember_200` | NO_ICON | não | `refs/species_icons/sb_crystal_ember.png` |
| 4 | `sb_crystal_queen` | Crystal Wyvern Queen | SmallBosses | `sb_crystal_queen, sb_crystal_queen_200` | NO_ICON | não | `refs/species_icons/sb_crystal_queen.png` |
| 5 | `sb_crystal_tropical` | Crystal Wyvern Tropical Descendant | SmallBosses | `sb_crystal_tropical, sb_crystal_tropical_200` | NO_ICON | não | `refs/species_icons/sb_crystal_tropical.png` |
| 6 | `sb_fire_elemental` | Fire Elemental | SmallBosses | `sb_fire_elemental, sb_fire_elemental_200` | NO_ICON | não | `refs/species_icons/sb_fire_elemental.png` |
| 7 | `sb_fire_elemental_tame` | Fire Elemental Domável | SmallBosses | `sb_fire_elemental_tame, sb_fire_elemental_tame_200` | NO_ICON | não | `refs/species_icons/sb_fire_elemental_tame.png` |
| 8 | `sb_broodmother` | Small Broodmother | SmallBosses | `sb_broodmother, sb_broodmother_200` | NO_ICON | não | `refs/species_icons/sb_broodmother.png` |
| 9 | `sb_cyclops` | Small Cyclops | SmallBosses | `sb_cyclops, sb_cyclops_200` | NO_ICON | não | `refs/species_icons/sb_cyclops.png` |
| 10 | `sb_desert_titan` | Small Desert Titan | SmallBosses | `sb_desert_titan, sb_desert_titan_200` | NO_ICON | não | `refs/species_icons/sb_desert_titan.png` |
| 11 | `sb_dodoreaper` | Small Dodoreaper | SmallBosses | `sb_dodoreaper, sb_dodoreaper_200` | NO_ICON | não | `refs/species_icons/sb_dodoreaper.png` |
| 12 | `sb_dodorex` | Small DodoRex | SmallBosses | `sb_dodorex, sb_dodorex_200` | NO_ICON | não | `refs/species_icons/sb_dodorex.png` |
| 13 | `sb_dodowyvern` | Small Dodowyvern | SmallBosses | `sb_dodowyvern, sb_dodowyvern_200` | NO_ICON | não | `refs/species_icons/sb_dodowyvern.png` |
| 14 | `sb_small_dragon` | Small Dragon | SmallBosses | `sb_small_dragon, sb_small_dragon_200` | NO_ICON | não | `refs/species_icons/sb_small_dragon.png` |
| 15 | `sb_drake_fire` | Small Drake Fogo | SmallBosses | `sb_drake_fire, sb_drake_fire_200` | NO_ICON | não | `refs/species_icons/sb_drake_fire.png` |
| 16 | `sb_hippocampus` | Small Hippocampus | SmallBosses | `sb_hippocampus, sb_hippocampus_200` | NO_ICON | não | `refs/species_icons/sb_hippocampus.png` |
| 17 | `sb_hydra` | Small Hydra | SmallBosses | `sb_hydra, sb_hydra_200` | NO_ICON | não | `refs/species_icons/sb_hydra.png` |
| 18 | `sb_manticore` | Small Manticore | SmallBosses | `sb_manticore, sb_manticore_200` | NO_ICON | não | `refs/species_icons/sb_manticore.png` |
| 19 | `sb_megapithecus` | Small Megapithecus | SmallBosses | `sb_megapithecus, sb_megapithecus_200` | NO_ICON | não | `refs/species_icons/sb_megapithecus.png` |
| 20 | `sb_moeder` | Small Moeder | SmallBosses | `sb_moeder, sb_moeder_200` | NO_ICON | não | `refs/species_icons/sb_moeder.png` |
| 21 | `sb_volcano_dragon` | Volcano Small Dragon | SmallBosses | `sb_volcano_dragon, sb_volcano_dragon_200` | NO_ICON | não | `refs/species_icons/sb_volcano_dragon.png` |
| 22 | `acro` | Acrocantossauro | ARK Additions | `acro, acrocanto_femea` | SVG_ONLY | não | `refs/species_icons/acro.png` |
| 23 | `archelon` | Archelon | ARK Additions | `archelon` | SVG_ONLY | não | `refs/species_icons/archelon.png` |
| 24 | `brachio` | Brachiosaurus | ARK Additions | `brachio` | SVG_ONLY | não | `refs/species_icons/brachio.png` |
| 25 | `concavenator` | Concavenator | ARK Additions | `concavenator` | SVG_ONLY | não | `refs/species_icons/concavenator.png` |
| 26 | `cryolophosaurus` | Cryolophosaurus | ARK Additions | `cryolophosaurus` | SVG_ONLY | não | `refs/species_icons/cryolophosaurus.png` |
| 27 | `deinosuchus` | Deinosuchus | ARK Additions | `deinosuchus` | SVG_ONLY | não | `refs/species_icons/deinosuchus.png` |
| 28 | `xiphactinus` | Xiphactinus | ARK Additions | `xiphactinus` | SVG_ONLY | não | `refs/species_icons/xiphactinus.png` |
| 29 | `abyss_ankylo_abyssal` | Anquilossauro Abissal | Abyss | `abyss_ankylo_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_ankylo_abyssal.png` |
| 30 | `abyss_thunnus` | Atum (Thunnus) | Abyss | `abyss_thunnus` | SVG_ONLY | não | `refs/species_icons/abyss_thunnus.png` |
| 31 | `abyss_takifugu` | Baiacu (Takifugu) | Abyss | `abyss_takifugu` | SVG_ONLY | não | `refs/species_icons/abyss_takifugu.png` |
| 32 | `abyss_mantis_shrimp` | Camarão-mantis | Abyss | `abyss_mantis_shrimp` | SVG_ONLY | não | `refs/species_icons/abyss_mantis_shrimp.png` |
| 33 | `abyss_seahorse` | Cavalo-marinho | Abyss | `abyss_seahorse` | SVG_ONLY | não | `refs/species_icons/abyss_seahorse.png` |
| 34 | `abyss_dakosaurus` | Dakosaurus | Abyss | `abyss_dakosaurus` | SVG_ONLY | não | `refs/species_icons/abyss_dakosaurus.png` |
| 35 | `abyss_kathreptis` | Kathreptis | Abyss | `abyss_kathreptis` | SVG_ONLY | não | `refs/species_icons/abyss_kathreptis.png` |
| 36 | `abyss_homarus` | Lagosta (Homarus) | Abyss | `abyss_homarus` | SVG_ONLY | não | `refs/species_icons/abyss_homarus.png` |
| 37 | `abyss_malleocephalus` | Malleocephalus | Abyss | `abyss_malleocephalus` | SVG_ONLY | não | `refs/species_icons/abyss_malleocephalus.png` |
| 38 | `abyss_istiophorus` | Marlim (Istiophorus) | Abyss | `abyss_istiophorus` | SVG_ONLY | não | `refs/species_icons/abyss_istiophorus.png` |
| 39 | `abyss_moschops_abyssal` | Moschops Abissal | Abyss | `abyss_moschops_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_moschops_abyssal.png` |
| 40 | `abyss_mudpuppy` | Mudpuppy | Abyss | `abyss_mudpuppy` | SVG_ONLY | não | `refs/species_icons/abyss_mudpuppy.png` |
| 41 | `abyss_monodon` | Narval (Monodon) | Abyss | `abyss_monodon` | SVG_ONLY | não | `refs/species_icons/abyss_monodon.png` |
| 42 | `abyss_ocepechelon` | Ocepechelon | Abyss | `abyss_ocepechelon` | SVG_ONLY | não | `refs/species_icons/abyss_ocepechelon.png` |
| 43 | `abyss_onchopristis` | Onchopristis | Abyss | `abyss_onchopristis` | SVG_ONLY | não | `refs/species_icons/abyss_onchopristis.png` |
| 44 | `abyss_qarmoutus` | Qarmoutus | Abyss | `abyss_qarmoutus` | SVG_ONLY | não | `refs/species_icons/abyss_qarmoutus.png` |
| 45 | `abyss_reaper_abyssal` | Reaper Abissal | Abyss | `abyss_reaper_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_reaper_abyssal.png` |
| 46 | `abyss_rex_abyssal` | Rex Abissal | Abyss | `abyss_rex_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_rex_abyssal.png` |
| 47 | `abyss_riftcrawler` | Rift Crawler | Abyss | `abyss_riftcrawler` | SVG_ONLY | não | `refs/species_icons/abyss_riftcrawler.png` |
| 48 | `abyss_stego_abyssal` | Stegossauro Abissal | Abyss | `abyss_stego_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_stego_abyssal.png` |
| 49 | `abyss_stereolepis` | Stereolepis | Abyss | `abyss_stereolepis` | SVG_ONLY | não | `refs/species_icons/abyss_stereolepis.png` |
| 50 | `abyss_theriz_abyssal` | Therizinosaur Abissal | Abyss | `abyss_theriz_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_theriz_abyssal.png` |
| 51 | `abyss_thyla_abyssal` | Thylacoleo Abissal | Abyss | `abyss_thyla_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_thyla_abyssal.png` |
| 52 | `abyss_tiktaalik` | Tiktaalik | Abyss | `abyss_tiktaalik` | SVG_ONLY | não | `refs/species_icons/abyss_tiktaalik.png` |
| 53 | `abyss_tridacna` | Tridacna | Abyss | `abyss_tridacna` | SVG_ONLY | não | `refs/species_icons/abyss_tridacna.png` |
| 54 | `abyss_vulcanite` | Vulcanita | Abyss | `abyss_vulcanite` | SVG_ONLY | não | `refs/species_icons/abyss_vulcanite.png` |
| 55 | `abyss_water_wyvern` | Wyvern Aquática | Abyss | `abyss_water_wyvern` | SVG_ONLY | não | `refs/species_icons/abyss_water_wyvern.png` |
| 56 | `abyss_yuty_abyssal` | Yutyrannus Abissal | Abyss | `abyss_yuty_abyssal` | SVG_ONLY | não | `refs/species_icons/abyss_yuty_abyssal.png` |
| 57 | `ancient_wyvern` | Ancient Wyvern | Brighamia | `ancient_wyvern` | SVG_ONLY | não | `refs/species_icons/ancient_wyvern.png` |
| 58 | `dread_wyvern` | Dread Wyvern | Brighamia | `dread_wyvern` | SVG_ONLY | não | `refs/species_icons/dread_wyvern.png` |
| 59 | `shimosaur` | Shimosaur | Brighamia | `shimosaur` | SVG_ONLY | não | `refs/species_icons/shimosaur.png` |
| 60 | `armaedron` | Armaedron | Grand Hunt | `armaedron, armaedron_femea` | SVG_ONLY | não | `refs/species_icons/armaedron.png` |
| 61 | `diru_ya_ku` | Diru-Ya-Ku | Grand Hunt | `diru_ya_ku` | SVG_ONLY | não | `refs/species_icons/diru_ya_ku.png` |
| 62 | `kutsu_ya_ku` | Kutsu-Ya-Ku | Grand Hunt | `kutsu_ya_ku` | SVG_ONLY | não | `refs/species_icons/kutsu_ya_ku.png` |
| 63 | `puretotokage` | Puretotokage | Grand Hunt | `puretotokage` | SVG_ONLY | não | `refs/species_icons/puretotokage.png` |
| 64 | `indominus` | Indominus Rex | Indominus Rex | `indominus, indominus_femea` | SVG_ONLY | não | `refs/species_icons/indominus.png` |

---

## Tabela completa (todos os dinos de mod)

| species_key | display_name | mod/source | catalog_item_id | in_catalog? | status | webp | svg | ref? | ref sugerida |
|-------------|--------------|------------|-----------------|-------------|--------|------|-----|------|--------------|
| `abyss_ankylo_abyssal` | Anquilossauro Abissal | Abyss | `abyss_ankylo_abyssal` | sim | SVG_ONLY | `—` | `abyss_ankylo_abyssal` | não | `refs/species_icons/abyss_ankylo_abyssal.png` |
| `abyss_dakosaurus` | Dakosaurus | Abyss | `abyss_dakosaurus` | sim | SVG_ONLY | `—` | `abyss_dakosaurus` | não | `refs/species_icons/abyss_dakosaurus.png` |
| `abyss_homarus` | Lagosta (Homarus) | Abyss | `abyss_homarus` | sim | SVG_ONLY | `—` | `abyss_homarus` | não | `refs/species_icons/abyss_homarus.png` |
| `abyss_istiophorus` | Marlim (Istiophorus) | Abyss | `abyss_istiophorus` | sim | SVG_ONLY | `—` | `abyss_istiophorus` | não | `refs/species_icons/abyss_istiophorus.png` |
| `abyss_kathreptis` | Kathreptis | Abyss | `abyss_kathreptis` | sim | SVG_ONLY | `—` | `abyss_kathreptis` | não | `refs/species_icons/abyss_kathreptis.png` |
| `abyss_malleocephalus` | Malleocephalus | Abyss | `abyss_malleocephalus` | sim | SVG_ONLY | `—` | `abyss_malleocephalus` | não | `refs/species_icons/abyss_malleocephalus.png` |
| `abyss_mantis_shrimp` | Camarão-mantis | Abyss | `abyss_mantis_shrimp` | sim | SVG_ONLY | `—` | `abyss_mantis_shrimp` | não | `refs/species_icons/abyss_mantis_shrimp.png` |
| `abyss_monodon` | Narval (Monodon) | Abyss | `abyss_monodon` | sim | SVG_ONLY | `—` | `abyss_monodon` | não | `refs/species_icons/abyss_monodon.png` |
| `abyss_moschops_abyssal` | Moschops Abissal | Abyss | `abyss_moschops_abyssal` | sim | SVG_ONLY | `—` | `abyss_moschops_abyssal` | não | `refs/species_icons/abyss_moschops_abyssal.png` |
| `abyss_mudpuppy` | Mudpuppy | Abyss | `abyss_mudpuppy` | sim | SVG_ONLY | `—` | `abyss_mudpuppy` | não | `refs/species_icons/abyss_mudpuppy.png` |
| `abyss_ocepechelon` | Ocepechelon | Abyss | `abyss_ocepechelon` | sim | SVG_ONLY | `—` | `abyss_ocepechelon` | não | `refs/species_icons/abyss_ocepechelon.png` |
| `abyss_onchopristis` | Onchopristis | Abyss | `abyss_onchopristis` | sim | SVG_ONLY | `—` | `abyss_onchopristis` | não | `refs/species_icons/abyss_onchopristis.png` |
| `abyss_qarmoutus` | Qarmoutus | Abyss | `abyss_qarmoutus` | sim | SVG_ONLY | `—` | `abyss_qarmoutus` | não | `refs/species_icons/abyss_qarmoutus.png` |
| `abyss_reaper_abyssal` | Reaper Abissal | Abyss | `abyss_reaper_abyssal` | sim | SVG_ONLY | `—` | `abyss_reaper_abyssal` | não | `refs/species_icons/abyss_reaper_abyssal.png` |
| `abyss_rex_abyssal` | Rex Abissal | Abyss | `abyss_rex_abyssal` | sim | SVG_ONLY | `—` | `abyss_rex_abyssal` | não | `refs/species_icons/abyss_rex_abyssal.png` |
| `abyss_riftcrawler` | Rift Crawler | Abyss | `abyss_riftcrawler` | sim | SVG_ONLY | `—` | `abyss_riftcrawler` | não | `refs/species_icons/abyss_riftcrawler.png` |
| `abyss_seahorse` | Cavalo-marinho | Abyss | `abyss_seahorse` | sim | SVG_ONLY | `—` | `abyss_seahorse` | não | `refs/species_icons/abyss_seahorse.png` |
| `abyss_stego_abyssal` | Stegossauro Abissal | Abyss | `abyss_stego_abyssal` | sim | SVG_ONLY | `—` | `abyss_stego_abyssal` | não | `refs/species_icons/abyss_stego_abyssal.png` |
| `abyss_stereolepis` | Stereolepis | Abyss | `abyss_stereolepis` | sim | SVG_ONLY | `—` | `abyss_stereolepis` | não | `refs/species_icons/abyss_stereolepis.png` |
| `abyss_takifugu` | Baiacu (Takifugu) | Abyss | `abyss_takifugu` | sim | SVG_ONLY | `—` | `abyss_takifugu` | não | `refs/species_icons/abyss_takifugu.png` |
| `abyss_theriz_abyssal` | Therizinosaur Abissal | Abyss | `abyss_theriz_abyssal` | sim | SVG_ONLY | `—` | `abyss_theriz_abyssal` | não | `refs/species_icons/abyss_theriz_abyssal.png` |
| `abyss_thunnus` | Atum (Thunnus) | Abyss | `abyss_thunnus` | sim | SVG_ONLY | `—` | `abyss_thunnus` | não | `refs/species_icons/abyss_thunnus.png` |
| `abyss_thyla_abyssal` | Thylacoleo Abissal | Abyss | `abyss_thyla_abyssal` | sim | SVG_ONLY | `—` | `abyss_thyla_abyssal` | não | `refs/species_icons/abyss_thyla_abyssal.png` |
| `abyss_tiktaalik` | Tiktaalik | Abyss | `abyss_tiktaalik` | sim | SVG_ONLY | `—` | `abyss_tiktaalik` | não | `refs/species_icons/abyss_tiktaalik.png` |
| `abyss_tridacna` | Tridacna | Abyss | `abyss_tridacna` | sim | SVG_ONLY | `—` | `abyss_tridacna` | não | `refs/species_icons/abyss_tridacna.png` |
| `abyss_vulcanite` | Vulcanita | Abyss | `abyss_vulcanite` | sim | SVG_ONLY | `—` | `abyss_vulcanite` | não | `refs/species_icons/abyss_vulcanite.png` |
| `abyss_water_wyvern` | Wyvern Aquática | Abyss | `abyss_water_wyvern` | sim | SVG_ONLY | `—` | `abyss_water_wyvern` | não | `refs/species_icons/abyss_water_wyvern.png` |
| `abyss_yuty_abyssal` | Yutyrannus Abissal | Abyss | `abyss_yuty_abyssal` | sim | SVG_ONLY | `—` | `abyss_yuty_abyssal` | não | `refs/species_icons/abyss_yuty_abyssal.png` |
| `acro` | Acrocantossauro | ARK Additions | `acro, acrocanto_femea` | sim | SVG_ONLY | `—` | `acro` | não | `refs/species_icons/acro.png` |
| `ancient_wyvern` | Ancient Wyvern | Brighamia | `ancient_wyvern` | sim | SVG_ONLY | `—` | `ancient_wyvern` | não | `refs/species_icons/ancient_wyvern.png` |
| `archelon` | Archelon | ARK Additions | `archelon` | sim | SVG_ONLY | `—` | `archelon` | não | `refs/species_icons/archelon.png` |
| `armaedron` | Armaedron | Grand Hunt | `armaedron, armaedron_femea` | sim | SVG_ONLY | `—` | `armaedron` | não | `refs/species_icons/armaedron.png` |
| `brachio` | Brachiosaurus | ARK Additions | `brachio` | sim | SVG_ONLY | `—` | `brachio` | não | `refs/species_icons/brachio.png` |
| `concavenator` | Concavenator | ARK Additions | `concavenator` | sim | SVG_ONLY | `—` | `concavenator` | não | `refs/species_icons/concavenator.png` |
| `cryolophosaurus` | Cryolophosaurus | ARK Additions | `cryolophosaurus` | sim | SVG_ONLY | `—` | `cryolophosaurus` | não | `refs/species_icons/cryolophosaurus.png` |
| `deinosuchus` | Deinosuchus | ARK Additions | `deinosuchus` | sim | SVG_ONLY | `—` | `deinosuchus` | não | `refs/species_icons/deinosuchus.png` |
| `diru_ya_ku` | Diru-Ya-Ku | Grand Hunt | `diru_ya_ku` | sim | SVG_ONLY | `—` | `diru_ya_ku` | não | `refs/species_icons/diru_ya_ku.png` |
| `dread_wyvern` | Dread Wyvern | Brighamia | `dread_wyvern` | sim | SVG_ONLY | `—` | `dread_wyvern` | não | `refs/species_icons/dread_wyvern.png` |
| `indominus` | Indominus Rex | Indominus Rex | `indominus, indominus_femea` | sim | SVG_ONLY | `—` | `indominus` | não | `refs/species_icons/indominus.png` |
| `indoraptor` | IndoRaptor | Indominus Rex | `indoraptor, indoraptor_femea` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/indoraptor.png` |
| `kutsu_ya_ku` | Kutsu-Ya-Ku | Grand Hunt | `kutsu_ya_ku` | sim | SVG_ONLY | `—` | `kutsu_ya_ku` | não | `refs/species_icons/kutsu_ya_ku.png` |
| `puretotokage` | Puretotokage | Grand Hunt | `puretotokage` | sim | SVG_ONLY | `—` | `puretotokage` | não | `refs/species_icons/puretotokage.png` |
| `sb_broodmother` | Small Broodmother | SmallBosses | `sb_broodmother, sb_broodmother_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_broodmother.png` |
| `sb_crystal_blood` | Crystal Wyvern Blood Descendant | SmallBosses | `sb_crystal_blood, sb_crystal_blood_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_crystal_blood.png` |
| `sb_crystal_ember` | Crystal Wyvern Ember Descendant | SmallBosses | `sb_crystal_ember, sb_crystal_ember_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_crystal_ember.png` |
| `sb_crystal_queen` | Crystal Wyvern Queen | SmallBosses | `sb_crystal_queen, sb_crystal_queen_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_crystal_queen.png` |
| `sb_crystal_tropical` | Crystal Wyvern Tropical Descendant | SmallBosses | `sb_crystal_tropical, sb_crystal_tropical_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_crystal_tropical.png` |
| `sb_cyclops` | Small Cyclops | SmallBosses | `sb_cyclops, sb_cyclops_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_cyclops.png` |
| `sb_desert_titan` | Small Desert Titan | SmallBosses | `sb_desert_titan, sb_desert_titan_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_desert_titan.png` |
| `sb_dodoreaper` | Small Dodoreaper | SmallBosses | `sb_dodoreaper, sb_dodoreaper_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_dodoreaper.png` |
| `sb_dodorex` | Small DodoRex | SmallBosses | `sb_dodorex, sb_dodorex_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_dodorex.png` |
| `sb_dodowyvern` | Small Dodowyvern | SmallBosses | `sb_dodowyvern, sb_dodowyvern_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_dodowyvern.png` |
| `sb_drake_fire` | Small Drake Fogo | SmallBosses | `sb_drake_fire, sb_drake_fire_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_drake_fire.png` |
| `sb_fire_elemental` | Fire Elemental | SmallBosses | `sb_fire_elemental, sb_fire_elemental_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_fire_elemental.png` |
| `sb_fire_elemental_tame` | Fire Elemental Domável | SmallBosses | `sb_fire_elemental_tame, sb_fire_elemental_tame_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_fire_elemental_tame.png` |
| `sb_hippocampus` | Small Hippocampus | SmallBosses | `sb_hippocampus, sb_hippocampus_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_hippocampus.png` |
| `sb_hydra` | Small Hydra | SmallBosses | `sb_hydra, sb_hydra_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_hydra.png` |
| `sb_manticore` | Small Manticore | SmallBosses | `sb_manticore, sb_manticore_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_manticore.png` |
| `sb_megapithecus` | Small Megapithecus | SmallBosses | `sb_megapithecus, sb_megapithecus_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_megapithecus.png` |
| `sb_moeder` | Small Moeder | SmallBosses | `sb_moeder, sb_moeder_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_moeder.png` |
| `sb_small_dragon` | Small Dragon | SmallBosses | `sb_small_dragon, sb_small_dragon_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_small_dragon.png` |
| `sb_volcano_dragon` | Volcano Small Dragon | SmallBosses | `sb_volcano_dragon, sb_volcano_dragon_200` | sim | NO_ICON | `—` | `—` | não | `refs/species_icons/sb_volcano_dragon.png` |
| `shimosaur` | Shimosaur | Brighamia | `shimosaur` | sim | SVG_ONLY | `—` | `shimosaur` | não | `refs/species_icons/shimosaur.png` |
| `xiphactinus` | Xiphactinus | ARK Additions | `xiphactinus` | sim | SVG_ONLY | `—` | `xiphactinus` | não | `refs/species_icons/xiphactinus.png` |

---

## ARK Additions

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `acro` | Acrocantossauro | SVG_ONLY | `acro, acrocanto_femea` | não |
| `archelon` | Archelon | SVG_ONLY | `archelon` | não |
| `brachio` | Brachiosaurus | SVG_ONLY | `brachio` | não |
| `concavenator` | Concavenator | SVG_ONLY | `concavenator` | não |
| `cryolophosaurus` | Cryolophosaurus | SVG_ONLY | `cryolophosaurus` | não |
| `deinosuchus` | Deinosuchus | SVG_ONLY | `deinosuchus` | não |
| `xiphactinus` | Xiphactinus | SVG_ONLY | `xiphactinus` | não |

## Abyss

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `abyss_ankylo_abyssal` | Anquilossauro Abissal | SVG_ONLY | `abyss_ankylo_abyssal` | não |
| `abyss_thunnus` | Atum (Thunnus) | SVG_ONLY | `abyss_thunnus` | não |
| `abyss_takifugu` | Baiacu (Takifugu) | SVG_ONLY | `abyss_takifugu` | não |
| `abyss_mantis_shrimp` | Camarão-mantis | SVG_ONLY | `abyss_mantis_shrimp` | não |
| `abyss_seahorse` | Cavalo-marinho | SVG_ONLY | `abyss_seahorse` | não |
| `abyss_dakosaurus` | Dakosaurus | SVG_ONLY | `abyss_dakosaurus` | não |
| `abyss_kathreptis` | Kathreptis | SVG_ONLY | `abyss_kathreptis` | não |
| `abyss_homarus` | Lagosta (Homarus) | SVG_ONLY | `abyss_homarus` | não |
| `abyss_malleocephalus` | Malleocephalus | SVG_ONLY | `abyss_malleocephalus` | não |
| `abyss_istiophorus` | Marlim (Istiophorus) | SVG_ONLY | `abyss_istiophorus` | não |
| `abyss_moschops_abyssal` | Moschops Abissal | SVG_ONLY | `abyss_moschops_abyssal` | não |
| `abyss_mudpuppy` | Mudpuppy | SVG_ONLY | `abyss_mudpuppy` | não |
| `abyss_monodon` | Narval (Monodon) | SVG_ONLY | `abyss_monodon` | não |
| `abyss_ocepechelon` | Ocepechelon | SVG_ONLY | `abyss_ocepechelon` | não |
| `abyss_onchopristis` | Onchopristis | SVG_ONLY | `abyss_onchopristis` | não |
| `abyss_qarmoutus` | Qarmoutus | SVG_ONLY | `abyss_qarmoutus` | não |
| `abyss_reaper_abyssal` | Reaper Abissal | SVG_ONLY | `abyss_reaper_abyssal` | não |
| `abyss_rex_abyssal` | Rex Abissal | SVG_ONLY | `abyss_rex_abyssal` | não |
| `abyss_riftcrawler` | Rift Crawler | SVG_ONLY | `abyss_riftcrawler` | não |
| `abyss_stego_abyssal` | Stegossauro Abissal | SVG_ONLY | `abyss_stego_abyssal` | não |
| `abyss_stereolepis` | Stereolepis | SVG_ONLY | `abyss_stereolepis` | não |
| `abyss_theriz_abyssal` | Therizinosaur Abissal | SVG_ONLY | `abyss_theriz_abyssal` | não |
| `abyss_thyla_abyssal` | Thylacoleo Abissal | SVG_ONLY | `abyss_thyla_abyssal` | não |
| `abyss_tiktaalik` | Tiktaalik | SVG_ONLY | `abyss_tiktaalik` | não |
| `abyss_tridacna` | Tridacna | SVG_ONLY | `abyss_tridacna` | não |
| `abyss_vulcanite` | Vulcanita | SVG_ONLY | `abyss_vulcanite` | não |
| `abyss_water_wyvern` | Wyvern Aquática | SVG_ONLY | `abyss_water_wyvern` | não |
| `abyss_yuty_abyssal` | Yutyrannus Abissal | SVG_ONLY | `abyss_yuty_abyssal` | não |

## Brighamia

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `ancient_wyvern` | Ancient Wyvern | SVG_ONLY | `ancient_wyvern` | não |
| `dread_wyvern` | Dread Wyvern | SVG_ONLY | `dread_wyvern` | não |
| `shimosaur` | Shimosaur | SVG_ONLY | `shimosaur` | não |

## Grand Hunt

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `armaedron` | Armaedron | SVG_ONLY | `armaedron, armaedron_femea` | não |
| `diru_ya_ku` | Diru-Ya-Ku | SVG_ONLY | `diru_ya_ku` | não |
| `kutsu_ya_ku` | Kutsu-Ya-Ku | SVG_ONLY | `kutsu_ya_ku` | não |
| `puretotokage` | Puretotokage | SVG_ONLY | `puretotokage` | não |

## Indominus Rex

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `indominus` | Indominus Rex | SVG_ONLY | `indominus, indominus_femea` | não |
| `indoraptor` | IndoRaptor | NO_ICON | `indoraptor, indoraptor_femea` | não |

## SmallBosses

| species_key | display_name | status | catalog_item_id | ref? |
|-------------|--------------|--------|-----------------|------|
| `sb_crystal_blood` | Crystal Wyvern Blood Descendant | NO_ICON | `sb_crystal_blood, sb_crystal_blood_200` | não |
| `sb_crystal_ember` | Crystal Wyvern Ember Descendant | NO_ICON | `sb_crystal_ember, sb_crystal_ember_200` | não |
| `sb_crystal_queen` | Crystal Wyvern Queen | NO_ICON | `sb_crystal_queen, sb_crystal_queen_200` | não |
| `sb_crystal_tropical` | Crystal Wyvern Tropical Descendant | NO_ICON | `sb_crystal_tropical, sb_crystal_tropical_200` | não |
| `sb_fire_elemental` | Fire Elemental | NO_ICON | `sb_fire_elemental, sb_fire_elemental_200` | não |
| `sb_fire_elemental_tame` | Fire Elemental Domável | NO_ICON | `sb_fire_elemental_tame, sb_fire_elemental_tame_200` | não |
| `sb_broodmother` | Small Broodmother | NO_ICON | `sb_broodmother, sb_broodmother_200` | não |
| `sb_cyclops` | Small Cyclops | NO_ICON | `sb_cyclops, sb_cyclops_200` | não |
| `sb_desert_titan` | Small Desert Titan | NO_ICON | `sb_desert_titan, sb_desert_titan_200` | não |
| `sb_dodoreaper` | Small Dodoreaper | NO_ICON | `sb_dodoreaper, sb_dodoreaper_200` | não |
| `sb_dodorex` | Small DodoRex | NO_ICON | `sb_dodorex, sb_dodorex_200` | não |
| `sb_dodowyvern` | Small Dodowyvern | NO_ICON | `sb_dodowyvern, sb_dodowyvern_200` | não |
| `sb_small_dragon` | Small Dragon | NO_ICON | `sb_small_dragon, sb_small_dragon_200` | não |
| `sb_drake_fire` | Small Drake Fogo | NO_ICON | `sb_drake_fire, sb_drake_fire_200` | não |
| `sb_hippocampus` | Small Hippocampus | NO_ICON | `sb_hippocampus, sb_hippocampus_200` | não |
| `sb_hydra` | Small Hydra | NO_ICON | `sb_hydra, sb_hydra_200` | não |
| `sb_manticore` | Small Manticore | NO_ICON | `sb_manticore, sb_manticore_200` | não |
| `sb_megapithecus` | Small Megapithecus | NO_ICON | `sb_megapithecus, sb_megapithecus_200` | não |
| `sb_moeder` | Small Moeder | NO_ICON | `sb_moeder, sb_moeder_200` | não |
| `sb_volcano_dragon` | Volcano Small Dragon | NO_ICON | `sb_volcano_dragon, sb_volcano_dragon_200` | não |

---

## Site ao vivo (arkland.com.br)

O portal público em [arkland.com.br](https://arkland.com.br) carrega o catálogo de doações (abas Itens / Dinos / Kits) e o Comércio P2P (Tabela Oficial, Mercado, Encomenda). A página inicial é acessível sem login; mercado/encomenda exigem Steam.

Com base no HTML público, na API `/api/catalog` (88 itens Type=dino de mod, alinhados ao `config.json` local) e no pipeline de ícones do repositório: todos os dinos de mod listados acima aparecem na loja com **badge SVG procedural** ou **silhueta de tier** — nenhum mod do catálogo possui WebP AI dedicado.

### Lacunas visíveis no catálogo (prioridade alta)

| Prioridade | Espécies | Impacto |
|------------|----------|---------|
| **P0** | `indoraptor` | Único mod no catálogo sem SVG — cai direto no fallback de tier S+ |
| **P1** | 20× SmallBosses (`sb_*`) | 40 itens na loja, zero ícone (nem SVG) |
| **P2** | 28× Abyss dinos | SVG badge apenas; sem WebP AI |
| **P3** | ARK Additions, Grand Hunt, Brighamia, Indominus | SVG badge; sem WebP AI nem ref salva |

## Fontes auditadas

- `plugin/CustomShop/configs/config.json` (Items Type=dino)
- `plugin/arkshop_web/data/market_species_defaults.json`
- `plugin/arkshop_web/data/ark_species_registry.json`
- `plugin/arkshop_web/data/species_icons_manifest.json`
- `plugin/arkshop_web/static/species/icons/*.svg`
- `plugin/arkshop_web/static/species/icons/generated/*.webp`
- `plugin/arkshop_web/static/species/icons/generated/manifest.json`
- `refs/species_icons/`
- Resolução: `resolve_species_image` em `ark_species_registry.py`

## Critérios

- **mod**: não está em `official_vanilla_species.json` (99 oficiais) nem em `VANILLA_CURATED`
- **dino**: `Type=dino` no catálogo ou `registry_entry_is_commerce_dino` no overlay
- Exclui recursos/sementes Abyss (`role`: resource, seed, etc.)
- **HAS_AI_WEBP**: `generated/{canonical}.webp` existe e não está na fila regen
- **SVG_ONLY**: só badge procedural em `icons/*.svg`
- **NO_ICON**: cai em silhueta de tier (`tier-s.svg`, etc.)
