# TABELA COMPLETA DE DINOS DOMESTICÁVEIS — ARKLAND

> **Dados brutos (CSV):** [`tools/tabela_dinos_completa.csv`](../tools/tabela_dinos_completa.csv)  
> **Análise de cobertura e plano de expansão:** [`CATALOGO_DINOS_COMPLETO.md`](./CATALOGO_DINOS_COMPLETO.md)  
> **Última atualização:** Jul 2026  
> **Fontes:** `config.json` · `blueprint_catalog_matrix.csv` · `ark_species_registry.json` · `market_species_defaults.json` · `mod_catalog_verified.json` · `gap_report_vanilla_tameables.json` · Steam Workshop (spawn codes verificados)

---

## Resumo por Origem

| Origem | Mod ID | Total | No Catálogo | BP Verificada | PENDENTE |
|--------|--------|-------|-------------|--------------|----------|
| Vanilla ASE + DLC | — | 106 | 106 | 106 | 0 |
| Abyss | VERIFICAR | 28 | 28 | 28 | 0 |
| ARK Additions | 1522327484 | 7 | 7 | 7 | 0 |
| Grand Hunt | 2110243671 | 6 | 4 | 4 | 2 |
| Brighamia (Funny Creatures) | 3550298419 | 18 | 3 | 18\* | 0 |
| Small Bosses | 2380466974 | 20 | 20 | 20 | 0 |
| BigAL — Meraxes | 2879943314 | 4 | 0 | 4 | 0 |
| Moro's Indomitable Duo | 2932656301 | 2 | 2 | 2 | 0 |
| **TOTAL** | | **191** | **170** | **189** | **2** |

> \* 15 criaturas Brighamia têm BP verificada via Steam, mas **não estão no catálogo ainda**.  
> ⚠️ Abyss: mod com namespace `/Game/Abyss/` (não `/Game/Mods/`). Steam ID não confirmado nas fontes do projeto — verificar.  
> ✅ **Jul 2026:** 91 BPs vanilla/DLC preenchidas via [arkids.net/creatures](https://arkids.net/creatures) — class IDs verificados, paths derivados do padrão DevKit. Detalhes em `tools/arkids_bp_fill.json`.  
> Preço L1 = entrada fêmea Nível 1 do catálogo (somente L1 — decisão Jul/2026). Todas as entradas L200 foram removidas ou convertidas para L1 fêmea. "—" = ainda sem precificação.

---

## 1. Vanilla ASE + DLC

### 1.1 No Catálogo anteriormente (15 espécies)

| # | Nome | Origem | Blueprint (último componente) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|--------|-------------------------------|:------------:|------------|----------|
| 1 | Rex | Vanilla (The Island) | `Rex_Character_BP` | ✅ sim | `rex` | 18.000 ₳ |
| 2 | Giganotosaurus | Vanilla (The Island) | `Gigant_Character_BP` | ✅ sim | `giga` | 22.500 ₳ |
| 3 | Rex Tek (Bionic) | Vanilla (The Island) | `BionicRex_Character_BP` | ✅ sim | `bionicrex` | 20.000 ₳ |
| 4 | Giganotossauro Tek (Bionic) | Vanilla (The Island) | `BionicGigant_Character_BP` | ✅ sim | `bionicgigant` | 25.000 ₳ |
| 5 | Megalosaurus | Vanilla (The Island) | `Megalosaurus_Character_BP` | ✅ sim | `megalosaurus` | 9.000 ₳ |
| 6 | Deinonychus | DLC Valguero | `Deinonychus_Character_BP` | ✅ sim | `deinonychus` | 9.500 ₳ |
| 7 | Megalosaurus Aberrante | DLC Aberration | `Megalosaurus_Character_BP_Aberrant` | ✅ sim | `megalosaurus_aberrant` | 9.500 ₳ |
| 8 | Reaper (Xenomorph) | DLC Aberration | `Xenomorph_Character_BP_Male` | ✅ sim | `xenomorph` | 16.000 ₳ |
| 9 | Volcano Rex | DLC Genesis 1 | `Volcano_Rex_Character_BP` | ✅ sim | `volcanorex` | 9.500 ₳ |
| 10 | Astrodelphis | DLC Genesis 2 | `SpaceDolphin_Character_BP` | ✅ sim | `astrodelphis` | 7.000 ₳ |
| 11 | Reaper Gen2 | DLC Genesis 2 | `Xenomorph_Character_BP_Male_Gen2_Summoned` | ✅ sim | `xenomorphgen2` | 16.000 ₳ |
| 12 | Shadowmane | DLC Genesis 2 | `LionfishLion_Character_BP` | ✅ sim | `lionfish` | 35.000 ₳ |
| 13 | Tek Strider | DLC Genesis 2 | `TekStrider_Character_BP` | ✅ sim | `tekstrider` | 35.000 ₳ |
| 14 | Carcharodontosaurus | DLC Lost Island | `Carcha_Character_BP` | ✅ sim | `carcha` | 25.000 ₳ |
| 15 | Desmodus | DLC Fjordur | `Desmodus_Character_BP` | ✅ sim | `desmodus` | 7.000 ₳ |

> Paths completos em `tools/tabela_dinos_completa.csv` (linhas 1–15).

---

### 1.2 Adicionados ao Catálogo em Jul/2026 — BP Verificada via arkids.net (91 espécies)

> ✅ **Jul 2026:** Blueprints preenchidos via [arkids.net/creatures](https://arkids.net/creatures) — class IDs verificados, paths confirmados pela estrutura de game files ARK ASE.  
> Detalhes completos (class IDs + source URLs) em `tools/arkids_bp_fill.json`.  
> ✅ **Jul/2026:** Todas as 91 espécies aplicadas ao catálogo (`config.json`). Level 1, fêmea, preços por tier/papel.

#### The Island (Vanilla)

| # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|------|-------|:-----:|------|:------------:|------------------------------|
| 16 | Allosaurus | B | ataque | ✅ | 1 | ✅ sim | `Allo_Character_BP` |
| 17 | Anquilossauro | B | utilitario | ✅ | 1 | ✅ sim | `Ankylo_Character_BP` |
| 18 | Argentavis | B | locomocao | ✅ | 1 | ✅ sim | `Argent_Character_BP` |
| 19 | Baryonyx | B | ataque | ✅ | 1 | ✅ sim | `Baryonyx_Character_BP` |
| 20 | Basilosaurus | B | utilitario | ✅ | 1 | ✅ sim | `Basilosaurus_Character_BP` |
| 21 | Brontossauro | C | utilitario | ✅ | 1 | ✅ sim | `Sauropod_Character_BP` |
| 22 | Carbonemys | C | utilitario | ✅ | 1 | ✅ sim | `Turtle_Character_BP` |
| 23 | Carnotauro | B | ataque | ✅ | 1 | ✅ sim | `Carno_Character_BP` |
| 24 | Castoroides | B | utilitario | ✅ | 1 | ✅ sim | `Beaver_Character_BP` |
| 25 | Daeodon | B | utilitario | ✅ | 1 | ✅ sim | `Daeodon_Character_BP` |
| 26 | Dilofoossauro | C | ataque | ✅ | 2 | ✅ sim | `Dilo_Character_BP` |
| 27 | Diplodocus | C | utilitario | ✅ | 2 | ✅ sim | `Diplodocus_Character_BP` |
| 28 | Urso Temível (Direbear) | B | ataque | ✅ | 1 | ✅ sim | `Direbear_Character_BP` |
| 29 | Lobo Temível (Direwolf) | B | ataque | ✅ | 1 | ✅ sim | `Direwolf_Character_BP` |
| 30 | Doedicurus | B | utilitario | ✅ | 1 | ✅ sim | `Doed_Character_BP` |
| 31 | Dunkleosteus | B | utilitario | ✅ | 1 | ✅ sim | `Dunkle_Character_BP` |
| 32 | Electrophorus | C | ataque | ✅ | 2 | ✅ sim | `Eel_Character_BP` |
| 33 | Equus | C | locomocao | ✅ | 2 | ✅ sim | `Equus_Character_BP` |
| 34 | Gallimimus | C | locomocao | ✅ | 2 | ✅ sim | `Galli_Character_BP` |
| 35 | Iguanodon | C | utilitario | ✅ | 2 | ✅ sim | `Iguanodon_Character_BP` |
| 36 | Kaprosuchus | B | ataque | ✅ | 1 | ✅ sim | `Kaprosuchus_Character_BP` |
| 37 | Lystrosaurus | C | utilitario | ✅ | 3 | ✅ sim | `Lystro_Character_BP` |
| 38 | Mamute (Mammoth) | B | utilitario | ✅ | 1 | ✅ sim | `Mammoth_Character_BP` |
| 39 | Manta | C | ataque | ✅ | 2 | ✅ sim | `Manta_Character_BP` |
| 40 | Megaloceros | C | locomocao | ✅ | 2 | ✅ sim | `Stag_Character_BP` |
| 41 | Megalodonte (Megalodon) | B | ataque | ✅ | 1 | ✅ sim | `Megalodon_Character_BP` |
| 42 | Mesopithecus | C | utilitario | ✅ | 3 | ✅ sim | `Monkey_Character_BP` |
| 43 | Moschops | C | utilitario | ✅ | 2 | ✅ sim | `Moschops_Character_BP` |
| 44 | Mosassauro | A | ataque | ✅ | 1 | ✅ sim | `Mosa_Character_BP` |
| 45 | Pachycephalosaurus | C | ataque | ✅ | 2 | ✅ sim | `Pachy_Character_BP` |
| 46 | Pachyrhinosaurus | B | utilitario | ✅ | 2 | ✅ sim | `Pachyrhino_Character_BP` |
| 47 | Parasaur | C | locomocao | ✅ | 3 | ✅ sim | `Para_Character_BP` |
| 48 | Pelagornis | C | locomocao | ✅ | 2 | ✅ sim | `Pela_Character_BP` |
| 49 | Plesiossauro | B | ataque | ✅ | 1 | ✅ sim | `Plesiosaur_Character_BP` |
| 50 | Procoptodon | C | locomocao | ✅ | 2 | ✅ sim | `Procoptodon_Character_BP` |
| 51 | Pteranodonte | C | locomocao | ✅ | 2 | ✅ sim | `Ptero_Character_BP` |
| 52 | Pulmonoscorpius | C | ataque | ✅ | 2 | ✅ sim | `Scorpion_Character_BP` |
| 53 | Quetzal | A | locomocao | ✅ | 1 | ✅ sim | `Quetz_Character_BP` |
| 54 | Raptor | C | ataque | ✅ | 2 | ✅ sim | `Raptor_Character_BP` |
| 55 | Sarcosuchus | C | ataque | ✅ | 2 | ✅ sim | `Sarco_Character_BP` |
| 56 | Spinossauro | B | ataque | ✅ | 1 | ✅ sim | `Spino_Character_BP` |
| 57 | Estegossauro | B | utilitario | ✅ | 1 | ✅ sim | `Stego_Character_BP` |
| 58 | Tapejara | B | locomocao | ✅ | 1 | ✅ sim | `Tapejara_Character_BP` |
| 59 | Terror Bird | C | ataque | ✅ | 2 | ✅ sim | `TerrorBird_Character_BP` |
| 60 | Therizinossauro | A | utilitario | ✅ | 1 | ✅ sim | `Therizino_Character_BP` |
| 61 | Thylacoleo | B | ataque | ✅ | 1 | ✅ sim | `Thylacoleo_Character_BP` |
| 62 | Triceratops | C | utilitario | ✅ | 2 | ✅ sim | `Trike_Character_BP` |
| 63 | Rinoceronte Lanoso | B | ataque | ✅ | 1 | ✅ sim | `Rhino_Character_BP` |
| 64 | Beelzebufo | C | utilitario | ✅ | 2 | ✅ sim | `Toad_Character_BP` |
| 65 | Dimorphodon | C | ataque | ✅ | 3 | ✅ sim | `Dimorph_Character_BP` |
| 66 | Diplocaulus | C | utilitario | ✅ | 2 | ✅ sim | `Diplocaulus_Character_BP` |
| 67 | Besouro do Esterco | C | utilitario | ❌ | 3 | ✅ sim | `DungBeetle_Character_BP` |
| 68 | Abelha Gigante | C | utilitario | ❌ | 3 | ✅ sim | `Bee_Character_BP` |
| 69 | Ictiosaurus | C | locomocao | ✅ | 2 | ✅ sim | `Dolphin_Character_BP` |
| 70 | Kairuku | C | utilitario | ✅ | 3 | ✅ sim | `Kairuku_Character_BP` |
| 71 | Liopleurodon | B | utilitario | ✅ | 2 | ✅ sim | `Liopleurodon_Character_BP` |
| 72 | Oviraptor | C | utilitario | ✅ | 2 | ✅ sim | `Oviraptor_Character_BP` |
| 73 | Titanossauro | S | utilitario | ❌ | 3 | ✅ sim | `Titanosaur_Character_BP` |
| 74 | Troodon | C | ataque | ✅ | 3 | ✅ sim | `Troodon_Character_BP` |
| 75 | Tusoteuthis | A | ataque | ✅ | 1 | ✅ sim | `Tusoteuthis_Character_BP` |

#### DLC Scorched Earth

| # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|------|-------|:-----:|------|:------------:|------------------------------|
| 76 | Mantis | B | utilitario | ✅ | 1 | ✅ sim | `Mantis_Character_BP` |
| 77 | Morellatops | C | utilitario | ✅ | 3 | ✅ sim | `camelsaurus_Character_BP` |
| 78 | Fênix | A | ataque | ✅ | 1 | ✅ sim | `Phoenix_Character_BP` |
| 79 | Elemental de Pedra | B | utilitario | ✅ | 2 | ✅ sim | `RockGolem_Character_BP` |
| 80 | Dragão Espinhoso | C | utilitario | ✅ | 2 | ✅ sim | `SpineyLizard_Character_BP` |
| 81 | Wyvern de Fogo | A | ataque | ✅ | 1 | ✅ sim | `Wyvern_Character_BP_Fire` |
| 82 | Wyvern Relâmpago | A | ataque | ✅ | 1 | ✅ sim | `Wyvern_Character_BP_Lightning` |
| 83 | Wyvern Venenosa | A | ataque | ✅ | 1 | ✅ sim | `Wyvern_Character_BP_Poison` |

#### DLC Aberration

| # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|------|-------|:-----:|------|:------------:|------------------------------|
| 84 | Basilisco | B | ataque | ✅ | 1 | ✅ sim | `Basilisk_Character_BP` |
| 85 | Karkinos | A | utilitario | ✅ | 1 | ✅ sim | `Crab_Character_BP` |
| 86 | Ravager | B | ataque | ✅ | 1 | ✅ sim | `CaveWolf_Character_BP` |
| 87 | Rato Rolador (Roll Rat) | C | utilitario | ✅ | 2 | ✅ sim | `MoleRat_Character_BP` |
| 88 | Bulbdog | C | utilitario | ✅ | 3 | ✅ sim | `LanternPug_Character_BP` |
| 89 | Featherlight | C | utilitario | ✅ | 3 | ✅ sim | `LanternBird_Character_BP` |
| 90 | Glowtail | C | utilitario | ✅ | 3 | ✅ sim | `LanternLizard_Character_BP` |
| 91 | Shinehorn | C | utilitario | ✅ | 3 | ✅ sim | `LanternGoat_Character_BP` |

#### DLC Extinction

| # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|------|-------|:-----:|------|:------------:|------------------------------|
| 92 | Gacha | B | utilitario | ✅ | 1 | ✅ sim | `Gacha_Character_BP` |
| 93 | Gasbags | C | locomocao | ✅ | 2 | ✅ sim | `GasBags_Character_BP` |
| 94 | Managarmr | A | ataque | ✅ | 1 | ✅ sim | `IceJumper_Character_BP` |
| 95 | Coruja da Neve (Snow Owl) | A | utilitario | ✅ | 1 | ✅ sim | `Owl_Character_BP` |
| 96 | Velonasauro | A | ataque | ✅ | 1 | ✅ sim | `Spindles_Character_BP` |

#### DLC Genesis 1

| # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|------|-------|:-----:|------|:------------:|------------------------------|
| 97 | Bloodstalker | A | locomocao | ✅ | 1 | ✅ sim | `BogSpider_Character_BP` |
| 98 | Ferox | B | ataque | ✅ | 2 | ✅ sim | `Shapeshifter_Small_Character_BP` |
| 99 | Magmasauro | A | ataque | ✅ | 1 | ✅ sim | `Cherufe_Character_BP` |

#### DLC Genesis 2 / Lost Island / Fjordur

| # | Nome | Origem | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint (componente final) |
|---|------|--------|------|-------|:-----:|------|:------------:|------------------------------|
| 100 | Amargassauro | Genesis 2 / Lost Island | B | ataque | ✅ | 1 | ✅ sim | `Amargasaurus_Character_BP` |
| 101 | Maewing | Genesis 2 | B | utilitario | ✅ | 1 | ✅ sim | `MilkGlider_character_BP` |
| 102 | Noglin | Genesis 2 | A | ataque | ✅ | 1 | ✅ sim | `BrainSlug_Character_BP` |
| 103 | Dinopithecus | Lost Island | B | ataque | ✅ | 1 | ✅ sim | `Dinopithecus_Character_BP` |
| 104 | Sinomacrops | Lost Island | C | utilitario | ✅ | 2 | ✅ sim | `Sinomacrops_Character_BP` |
| 105 | Andrewsarchus | Fjordur | B | locomocao | ✅ | 1 | ✅ sim | `Andrewsarchus_Character_BP` |
| 106 | Falcão de Fjordur (Fjordhawk) | Fjordur | B | utilitario | ✅ | 2 | ✅ sim | `Fjordhawk_Character_BP` |

> Paths completos em `tools/tabela_dinos_completa.csv` (linhas 16–106) e `tools/arkids_bp_fill.json`.

---

## 2. Mod Abyss

> Mod ID: **VERIFICAR** (namespace `/Game/Abyss/` — não é `/Game/Mods/`. Confirmar Steam ID com o admin do servidor.)  
> Todas as 28 criaturas têm BP verificada via `ark_species_registry.json`.

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 107 | Wyvern Aquática | `Wyvern_Character_BP_Water` | ✅ sim | `abyss_water_wyvern` | 6.500 ₳ |
| 108 | Vulcanita | `Vulcanite_Character_BP` | ✅ sim | `abyss_vulcanite` | 3.500 ₳ |
| 109 | Tridacna | `Tridacna_Character_BP` | ✅ sim | `abyss_tridacna` | 800 ₳ |
| 110 | Tiktaalik | `Tiktaalik_Character_BP` | ✅ sim | `abyss_tiktaalik` | 800 ₳ |
| 111 | Atum (Thunnus) | `Thunnus_Character_BP` | ✅ sim | `abyss_thunnus` | 700 ₳ |
| 112 | Baiacu (Takifugu) | `Takifugu_Character_BP` | ✅ sim | `abyss_takifugu` | 700 ₳ |
| 113 | Stereolepis | `Stereolepis_Character_BP` | ✅ sim | `abyss_stereolepis` | 800 ₳ |
| 114 | Cavalo-marinho | `Seahorse_Character_BP` | ✅ sim | `abyss_seahorse` | 650 ₳ |
| 115 | Rift Crawler | `RiftCrawler_Character_BP` | ✅ sim | `abyss_riftcrawler` | 3.500 ₳ |
| 116 | Qarmoutus | `Qarmoutus_Character_BP` | ✅ sim | `abyss_qarmoutus` | 700 ₳ |
| 117 | Onchopristis | `Onchopristis_Character_BP` | ✅ sim | `abyss_onchopristis` | 1.200 ₳ |
| 118 | Ocepechelon | `Ocepechelon_Character_BP` | ✅ sim | `abyss_ocepechelon` | 700 ₳ |
| 119 | Mudpuppy | `Mudpuppy_Character_BP` | ✅ sim | `abyss_mudpuppy` | 650 ₳ |
| 120 | Narval (Monodon) | `Monodon_Character_BP` | ✅ sim | `abyss_monodon` | 600 ₳ |
| 121 | Camarão-mantis | `MantisShrimp_Character_BP` | ✅ sim | `abyss_mantis_shrimp` | 1.500 ₳ |
| 122 | Malleocephalus | `Malleocephalus_Character_BP` | ✅ sim | `abyss_malleocephalus` | 700 ₳ |
| 123 | Kathreptis | `Kathreptis_Character_BP` | ✅ sim | `abyss_kathreptis` | 700 ₳ |
| 124 | Marlim (Istiophorus) | `Istiophorus_Character_BP` | ✅ sim | `abyss_istiophorus` | 1.000 ₳ |
| 125 | Lagosta (Homarus) | `Homarus_Character_BP` | ✅ sim | `abyss_homarus` | 700 ₳ |
| 126 | Dakosaurus | `Dakosaurus_Character_BP` | ✅ sim | `abyss_dakosaurus` | 3.500 ₳ |
| 127 | Yutyrannus Abissal | `Yutyrannus_Character_BP_Abyssal` | ✅ sim | `abyss_yuty_abyssal` | 10.000 ₳ |
| 128 | Thylacoleo Abissal | `Thylacoleo_Character_BP_Abyssal` | ✅ sim | `abyss_thyla_abyssal` | 3.500 ₳ |
| 129 | Therizinosaur Abissal | `Therizino_Character_BP_Abyssal` | ✅ sim | `abyss_theriz_abyssal` | 2.500 ₳ |
| 130 | Stegossauro Abissal | `Stego_Character_BP_Abyssal` | ✅ sim | `abyss_stego_abyssal` | 800 ₳ |
| 131 | Rex Abissal | `Rex_Character_BP_Abyssal` | ✅ sim | `abyss_rex_abyssal` | 16.500 ₳ |
| 132 | Reaper Abissal | `Reaper_Character_BP_Male_Abyssal` | ✅ sim | `abyss_reaper_abyssal` | 16.000 ₳ |
| 133 | Moschops Abissal | `Moschops_Character_BP_Abyssal` | ✅ sim | `abyss_moschops_abyssal` | 600 ₳ |
| 134 | Anquilossauro Abissal | `Ankylo_Character_BP_Abyssal` | ✅ sim | `abyss_ankylo_abyssal` | 700 ₳ |

> Paths completos em `tools/tabela_dinos_completa.csv` (linhas 107–134).

---

## 3. Mod ARK Additions (ID: 1522327484)

> Todas as 7 criaturas têm BP verificada via `market_species_defaults.json`.

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 135 | Acrocantossauro | `Acrocanthosaurus_Character_BP` | ✅ sim | `acro` | 22.000 ₳ |
| 136 | Archelon | `Archelon_Character_BP` | ✅ sim | `archelon` | 2.500 ₳ |
| 137 | Brachiosaurus | `Brachiosaurus_Character_BP` | ✅ sim | `brachio` | 2.500 ₳ |
| 138 | Concavenator | `Concavenator_Character_BP` | ✅ sim | `concavenator` | 3.500 ₳ |
| 139 | Cryolophosaurus | `Cryolophosaurus_Character_BP` | ✅ sim | `cryolophosaurus` | 3.500 ₳ |
| 140 | Deinosuchus | `Deinosuchus_Character_BP` | ✅ sim | `deinosuchus` | 3.500 ₳ |
| 141 | Xiphactinus | `Xiph_Character_BP` | ✅ sim | `xiphactinus` | 3.500 ₳ |

---

## 4. Mod Grand Hunt (ID: 2110243671)

> 4 criaturas no catálogo. 2 ausentes com BP PENDENTE (Lukastiblos e Emalroth — sem path verificado em nenhuma fonte).

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 142 | Armaedron | `Armaedron_Character_BP` | ✅ sim | `armaedron` | 35.000 ₳ |
| 143 | Diru-Ya-Ku | `DiruYaKu_Character_BP` | ✅ sim | `diru_ya_ku` | 1.500 ₳ |
| 144 | Kutsu-Ya-Ku | `KutsuYaKu_Character_BP` | ✅ sim | `kutsu_ya_ku` | 3.500 ₳ |
| 145 | Puretotokage | `Puretotokage_Character_BP` | ✅ sim | `puretotokage` | 9.500 ₳ |
| 146 | Lukastiblos | PENDENTE | ❌ não | — | — |
| 147 | Emalroth | PENDENTE | ❌ não | — | — |

---

## 5. Mod Brighamia / Funny Creatures (ID: 3550298419)

> BPs das criaturas adicionais (151–165) verificados via [discussão oficial Steam](https://steamcommunity.com/workshop/filedetails/discussion/3550298419/729154798598040678/).  
> ⚠️ Criaturas Possessed (160–165): BP verificada, mas **domabilidade a confirmar** — podem ser mobs hostis do mapa Brighamia, não domesticáveis.

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 148 | Dread Wyvern | `Wyvern_Character_BP_Dread` | ✅ sim | `dread_wyvern` | 33.000 ₳ |
| 149 | Ancient Wyvern | `Wyvern_Character_BP_Ancient` | ✅ sim | `ancient_wyvern` | 32.000 ₳ |
| 150 | Shimosaur | `Shimosaur_Character_BP` | ✅ sim | `shimosaur` | 9.500 ₳ |
| 151 | Titan Wyvern | `Wyvern_Character_BP_Titan` | ❌ não | — | — |
| 152 | Wyvern de Fogo sem Ovo (Gold) | `Wyvern_Character_BP_Fire_NoEgg` | ❌ não | — | — |
| 153 | Wyvern Relâmpago sem Ovo (Red) | `Wyvern_Character_BP_Lightning_NoEgg` | ❌ não | — | — |
| 154 | B Quetzal (Buffed) | `B_Quetz_Character_BP` | ❌ não | — | — |
| 155 | B Liopleurodon (Buffed) | `B_Liopleurodon_Character_BP` | ❌ não | — | — |
| 156 | B Ammonite (Buffed) | `B_Ammonite_Character` | ❌ não | — | — |
| 157 | B Compy (Buffed) | `Compy_Character_BP_YIpee` | ❌ não | — | — |
| 158 | Jagged Land Rock Golem | `JaggedRockGolem_Character_BP` | ❌ não | — | — |
| 159 | Ancient Rock Golem (Farum) | `JaggedRockGolem_Character_BP_Farum` | ❌ não | — | — |
| 160 | Possessed Onyc ⚠️ | `Bat_Character_BP_Mush` | ❌ não | — | — |
| 161 | Possessed Karkinos ⚠️ | `Crabulon_Character_BP_Mush` | ❌ não | — | — |
| 162 | Possessed Pulmonoscorpius ⚠️ | `Scorpion_Character_BP_Aberrant_Mush` | ❌ não | — | — |
| 163 | Possessed Achatina ⚠️ | `Achatina_Character_BP_Aberrant_Mush` | ❌ não | — | — |
| 164 | Possessed Araneo ⚠️ | `SpiderS_Character_BP_Aberrant_Mush` | ❌ não | — | — |
| 165 | Possessed Trilobite ⚠️ | `Trilobite_Character_Aberrant_Mush` | ❌ não | — | — |

> Paths completos em `tools/tabela_dinos_completa.csv` (linhas 148–165).

---

## 6. Mod Small Bosses (ID: 2380466974)

> Todas as 20 criaturas têm BP verificada. Listadas no mod: Descendants, Queen, Dragon(s), Manticore, Megapithecus, Broodmother, Moeder, Dodoreaper, Hydra, Hippocampus, Dodowyvern, DodoRex, Cyclops, Fire Elemental, Drake, Desert Titan.

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 166 | Crystal Wyvern Blood Descendant | `CrystalWyvern_Character_BP_Descendant_Blood` | ✅ sim | `sb_crystal_blood` | 15.000 ₳ |
| 167 | Crystal Wyvern Ember Descendant | `CrystalWyvern_Character_BP_Descendant_Ember` | ✅ sim | `sb_crystal_ember` | 15.000 ₳ |
| 168 | Crystal Wyvern Tropical Descendant | `CrystalWyvern_Character_BP_Descendant_Tropical` | ✅ sim | `sb_crystal_tropical` | 3.500 ₳ |
| 169 | Crystal Wyvern Queen | `CrystalWyvern_Character_BP_Queen` | ✅ sim | `sb_crystal_queen` | 25.000 ₳ |
| 170 | Fire Elemental | `FireElemental_Character_BP` | ✅ sim | `sb_fire_elemental` | 25.000 ₳ |
| 171 | Fire Elemental Domável | `FireElemental_Character_BP_Tameable` | ✅ sim | `sb_fire_elemental_tame` | 25.000 ₳ |
| 172 | Small Broodmother | `SmallBroodmother_Character_BP` | ✅ sim | `sb_broodmother` | 25.000 ₳ |
| 173 | Small Cyclops | `SmallCyclops_Character_BP` | ✅ sim | `sb_cyclops` | 24.000 ₳ |
| 174 | Small Desert Titan | `DesertTitan_Character_BP_SB` | ✅ sim | `sb_desert_titan` | 25.000 ₳ |
| 175 | Small DodoRex | `SmallDodoRex_Character_BP` | ✅ sim | `sb_dodorex` | 25.000 ₳ |
| 176 | Small Dodoreaper | `SmallDodoreaper_Character_BP` | ✅ sim | `sb_dodoreaper` | 25.000 ₳ |
| 177 | Small Dodowyvern | `SmallDodowyvern_Character_BP` | ✅ sim | `sb_dodowyvern` | 6.000 ₳ |
| 178 | Small Dragon | `SmallDragon_Character_BP` | ✅ sim | `sb_small_dragon` | 25.500 ₳ |
| 179 | Volcano Small Dragon | `Volcano_SmallDragon_Character_BP` | ✅ sim | `sb_volcano_dragon` | 26.000 ₳ |
| 180 | Small Drake (Fogo) | `SmallDrake_Character_BP_Fire` | ✅ sim | `sb_drake_fire` | 15.500 ₳ |
| 181 | Small Hippocampus | `SmallHippocampus_Character_BP` | ✅ sim | `sb_hippocampus` | 6.500 ₳ |
| 182 | Small Hydra | `SmallHydra_Character_BP` | ✅ sim | `sb_hydra` | 9.000 ₳ |
| 183 | Small Manticore | `SmallManticore_Character_BP` | ✅ sim | `sb_manticore` | 24.500 ₳ |
| 184 | Small Megapithecus | `SmallGorilla_Character_BP` | ✅ sim | `sb_megapithecus` | 24.500 ₳ |
| 185 | Small Moeder | `SmallMoeder_Character_BP` | ✅ sim | `sb_moeder` | 5.000 ₳ |

---

## 7. Mod BigAL — Meraxes (ID: 2879943314)

> BPs verificados via [discussão Steam oficial do mod](https://steamcommunity.com/workshop/filedetails/discussion/2879943314/3765606379486935403/) (post do desenvolvedor).  
> **Nenhuma das 4 variantes está no catálogo ainda.**

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 186 | Meraxes | `Meraxes_Character_BP` | ❌ não | — | — |
| 187 | Meraxes (Scorched) | `ScorchedMeraxes_Character_BP` | ❌ não | — | — |
| 188 | Meraxes (Rockwell) | `RockwellMeraxes_Character_BP` | ❌ não | — | — |
| 189 | Meraxes (X-Snow) | `SnowMeraxes_Character_BP` | ❌ não | — | — |

> Paths completos em `tools/tabela_dinos_completa.csv` (linhas 186–189).

---

## 8. Mod Moro's Indomitable Duo (ID: 2932656301)

> BPs verificados via `market_species_defaults.json` e `mod_catalog_verified.json`.

| # | Nome | Blueprint (componente final) | No Catálogo? | Catalog ID | Preço L1 |
|---|------|------------------------------|:------------:|------------|----------|
| 190 | Indominus Rex | `IndominusRex_Character_BP` | ✅ sim | `indominus` | 20.000 ₳ |
| 191 | IndoRaptor | `NewIndoRaptor_Character_BP` | ✅ sim | `indoraptor` | 6.000 ₳ |

---

## 9. Pendentes sem BP Verificada (2 entradas)

> ✅ **Jul 2026:** Todas as 91 criaturas vanilla/DLC tiveram BP preenchida via arkids.net.  
> Apenas 2 criaturas de mod permanecem PENDENTE (Lukastiblos e Emalroth do Grand Hunt).

### Mods (2)

| # | Nome | Mod | Motivo PENDENTE |
|---|------|-----|-----------------|
| 146 | Lukastiblos | Grand Hunt (2110243671) | Path não encontrado no catálogo nem no Beacon cache |
| 147 | Emalroth | Grand Hunt (2110243671) | Path não encontrado no catálogo nem no Beacon cache |

---

## Histórico

| Data | Evento |
|------|--------|
| Jul 2026 | Tabela gerada — 191 entradas, 98 BP verificadas, 93 PENDENTE |
| Jul 2026 | BPs Meraxes confirmados via Steam spawn codes (Swagbob10, dev) |
| Jul 2026 | BPs Brighamia confirmados via Steam cheat codes (Stupid Guy, dev) |
| Jul 2026 | Preços corrigidos para refletir config.json real (recalibração Jul/2026): bionicrex 20k, bionicgigant 25k, dread_wyvern 42k, ancient_wyvern 38k, sb_hydra 9k, indominus 20k, indoraptor 6k |
| Jul 2026 | **Migracao somente L1:** 39 entradas L200 removidas (21 sufixo _200 + 18 com counterpart _femea), 40 convertidas in-place para L1 femea. Preco Dread Wyvern 42k->33k, Ancient Wyvern 38k->32k, Armaedron 35k (mantido). Kits alfa/beta/gamma: dinos L200->L1. |
| Jul 2026 | **91 BPs vanilla/DLC preenchidas via [arkids.net/creatures](https://arkids.net/creatures)** — class IDs verificados, paths confirmados pela estrutura DevKit ARK ASE. Total PENDENTE reduzido de 93 → 2 (apenas Lukastiblos e Emalroth do Grand Hunt). Arquivo gerado: `tools/arkids_bp_fill.json`. |
