# Checklist — referências de ícones de espécies

> Gerado em **2026-07-09 04:48 UTC** por `tools/audit_species_icon_references.py`. Não gera ícones — só lista o que falta para você caçar referências.

## Resumo

| Métrica | Valor |
|---------|-------|
| Espécies rastreadas (todas as fontes) | **157** |
| No catálogo atual (`market_species_defaults` + `config.json` dino) | **27** |
| Oficial vanilla (`official_vanilla_species.json`) | **99** |
| WebP AI em `generated/` | **91** |
| SVG procedural em `icons/` | **154** |
| Referências salvas em `refs/species_icons/` | **100** |

### Status global

| Status | Qtd | Significado |
|--------|-----|-------------|
| HAS_AI_WEBP | 78 | WebP gerado (ou alias resolve) |
| SVG_ONLY | 55 | SVG procedural, sem WebP AI |
| NEEDS_REGEN | 23 | WebP existe mas na fila de regeneração |
| NO_ICON | 1 | Sem SVG nem WebP (fallback de tier) |

### Catálogo atual

- **HAS_AI_WEBP**: 6
- **NEEDS_REGEN**: 5
- **NO_ICON**: 1
- **SVG_ONLY**: 15

### Prioridades para caçar referências

- **Prioridade A** (catálogo sem ícone): **1**
- **Prioridade B** (catálogo só SVG): **15**
- **Prioridade C** (vanilla oficial sem WebP OK / regen): **22**
- **Prioridade D** (SVG no disco sem WebP): **55**

---

## Prioridade A — Catálogo sem nenhum ícone

**Total: 1**

| species_key | display_name | origin | current_status | in_catalog? | ref sugerida |
|-------------|--------------|--------|----------------|-------------|--------------|
| `indoraptor` | IndoRaptor | mod | NO_ICON | sim | `refs/species_icons/indoraptor.png` |

## Prioridade B — Catálogo com SVG apenas (upgrade AI)

**Total: 15**

| species_key | display_name | origin | current_status | in_catalog? | ref sugerida |
|-------------|--------------|--------|----------------|-------------|--------------|
| `acro` | Acrocantossauro | mod | SVG_ONLY | sim | `refs/species_icons/acro.png` |
| `ancient_wyvern` | Ancient Wyvern | mod | SVG_ONLY | sim | `refs/species_icons/ancient_wyvern.png` |
| `archelon` | Archelon | mod | SVG_ONLY | sim | `refs/species_icons/archelon.png` |
| `armaedron` | Armaedron | mod | SVG_ONLY | sim | `refs/species_icons/armaedron.png` |
| `brachio` | Brachiosaurus | mod | SVG_ONLY | sim | `refs/species_icons/brachio.png` |
| `concavenator` | Concavenator | mod | SVG_ONLY | sim | `refs/species_icons/concavenator.png` |
| `cryolophosaurus` | Cryolophosaurus | mod | SVG_ONLY | sim | `refs/species_icons/cryolophosaurus.png` |
| `deinosuchus` | Deinosuchus | mod | SVG_ONLY | sim | `refs/species_icons/deinosuchus.png` |
| `diru_ya_ku` | Diru-Ya-Ku | mod | SVG_ONLY | sim | `refs/species_icons/diru_ya_ku.png` |
| `dread_wyvern` | Dread Wyvern | mod | SVG_ONLY | sim | `refs/species_icons/dread_wyvern.png` |
| `indominus` | Indominus Rex | mod | SVG_ONLY | sim | `refs/species_icons/indominus.png` |
| `kutsu_ya_ku` | Kutsu-Ya-Ku | mod | SVG_ONLY | sim | `refs/species_icons/kutsu_ya_ku.png` |
| `puretotokage` | Puretotokage | mod | SVG_ONLY | sim | `refs/species_icons/puretotokage.png` |
| `shimosaur` | Shimosaur | mod | SVG_ONLY | sim | `refs/species_icons/shimosaur.png` |
| `xiphactinus` | Xiphactinus | mod | SVG_ONLY | sim | `refs/species_icons/xiphactinus.png` |

## Prioridade C — Vanilla oficial (99) sem WebP aprovado ou na fila regen

**Total: 22**

| species_key | display_name | origin | current_status | in_catalog? | nota regen | ref sugerida |
|-------------|--------------|--------|----------------|-------------|------------|--------------|
| `astrocetus` | Astrocetus | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/astrocetus.png` |
| `bloodstalker` | Bloodstalker | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/bloodstalker.png` |
| `beaver` | Castoroides | vanilla | NEEDS_REGEN | não | Duas imagens (alias beaver consolidado) | `refs/species_icons/castoroides.png` |
| `castoroides` | Castoroides | vanilla | NEEDS_REGEN | não | Duas imagens (alias beaver consolidado) | `refs/species_icons/castoroides.png` |
| `deinonychus_femea` | Deinonychus | vanilla | NEEDS_REGEN | sim | Duas imagens (variante deinonychus_femea) | `refs/species_icons/deinonychus.png` |
| `deinonychus` | Deinonychus | vanilla | NEEDS_REGEN | não | Duas imagens (variante deinonychus_femea) | `refs/species_icons/deinonychus.png` |
| `doed` | Doedicurus | vanilla | NEEDS_REGEN | não | Duas imagens (alias doed consolidado) | `refs/species_icons/doedicurus.png` |
| `doedicurus` | Doedicurus | vanilla | NEEDS_REGEN | não | Duas imagens (alias doed consolidado) | `refs/species_icons/doedicurus.png` |
| `gacha` | Gacha | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/gacha.png` |
| `gasbags` | Gasbags | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/gasbags.png` |
| `giga` | Giga | vanilla | NEEDS_REGEN | sim | Duas imagens giganotossauro (giga + gigant) | `refs/species_icons/giga.png` |
| `gigant` | Giganotossauro | vanilla | NEEDS_REGEN | não | Duas imagens giganotossauro (giga + gigant) | `refs/species_icons/giga.png` |
| `megalosaurus_femea` | Megalosaurus | vanilla | NEEDS_REGEN | sim | Duas imagens (variantes _femea) | `refs/species_icons/megalosaurus.png` |
| `megalosaurus_aberrant_femea` | Megalosaurus Aberrante | vanilla | NEEDS_REGEN | sim | Duas imagens (variantes _femea) | `refs/species_icons/megalosaurus.png` |
| `megalosaurus` | Megalossauro | vanilla | NEEDS_REGEN | não | Duas imagens (variantes _femea) | `refs/species_icons/megalosaurus.png` |
| `mosasaurus` | Mosasauro | vanilla | NEEDS_REGEN | não | Muito magro; anatomia incorreta | `refs/species_icons/mosasaurus.png` |
| `phiomia` | Phiomia | vanilla | NEEDS_REGEN | não | Parece elefante | `refs/species_icons/phiomia.png` |
| `rhynio` | Rhinognatha | vanilla | NEEDS_REGEN | não | Parece besouro de esterco (Rhinognatha) | `refs/species_icons/rhynio.png` |
| `sinomacrops` | Sinomacrops | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/sinomacrops.png` |
| `tekstrider_femea` | Tek Strider | vanilla | NEEDS_REGEN | sim | Ícone ruim (variante tekstrider_femea) | `refs/species_icons/tekstrider.png` |
| `tekstrider` | Tek Strider | vanilla | NEEDS_REGEN | não | Ícone ruim (variante tekstrider_femea) | `refs/species_icons/tekstrider.png` |
| `crystalwyvern` | Wyvern de Cristal | vanilla | NEEDS_REGEN | não | Ícone ruim | `refs/species_icons/crystalwyvern.png` |

## Prioridade D — SVG no disco sem WebP correspondente

**Total: 55**

| species_key | display_name | origin | current_status | in_catalog? | ref sugerida |
|-------------|--------------|--------|----------------|-------------|--------------|
| `abyss_seaweed` | Alga Marinha | abyss | SVG_ONLY | não | `refs/species_icons/abyss_seaweed.png` |
| `abyss_ankylo_abyssal` | Anquilossauro Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_ankylo_abyssal.png` |
| `abyss_aqualyrium` | Aqualyrium | abyss | SVG_ONLY | não | `refs/species_icons/abyss_aqualyrium.png` |
| `abyss_thunnus` | Atum (Thunnus) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_thunnus.png` |
| `abyss_takifugu` | Baiacu (Takifugu) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_takifugu.png` |
| `abyss_mantis_shrimp` | Camarão-mantis | abyss | SVG_ONLY | não | `refs/species_icons/abyss_mantis_shrimp.png` |
| `abyss_seahorse` | Cavalo-marinho | abyss | SVG_ONLY | não | `refs/species_icons/abyss_seahorse.png` |
| `abyss_barnacle` | Craca | abyss | SVG_ONLY | não | `refs/species_icons/abyss_barnacle.png` |
| `abyss_dakosaurus` | Dakosaurus | abyss | SVG_ONLY | não | `refs/species_icons/abyss_dakosaurus.png` |
| `abyss_fish_scale` | Escama de Peixe | abyss | SVG_ONLY | não | `refs/species_icons/abyss_fish_scale.png` |
| `abyss_kathreptis` | Kathreptis | abyss | SVG_ONLY | não | `refs/species_icons/abyss_kathreptis.png` |
| `abyss_homarus` | Lagosta (Homarus) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_homarus.png` |
| `abyss_hardened_steel` | Lingote de Aço Endurecido | abyss | SVG_ONLY | não | `refs/species_icons/abyss_hardened_steel.png` |
| `abyss_crystallized_wood` | Madeira Cristalizada | abyss | SVG_ONLY | não | `refs/species_icons/abyss_crystallized_wood.png` |
| `abyss_malleocephalus` | Malleocephalus | abyss | SVG_ONLY | não | `refs/species_icons/abyss_malleocephalus.png` |
| `abyss_manganese` | Manganês | abyss | SVG_ONLY | não | `refs/species_icons/abyss_manganese.png` |
| `abyss_istiophorus` | Marlim (Istiophorus) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_istiophorus.png` |
| `abyss_moschops_abyssal` | Moschops Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_moschops_abyssal.png` |
| `abyss_mudpuppy` | Mudpuppy | abyss | SVG_ONLY | não | `refs/species_icons/abyss_mudpuppy.png` |
| `abyss_monodon` | Narval (Monodon) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_monodon.png` |
| `abyss_ocepechelon` | Ocepechelon | abyss | SVG_ONLY | não | `refs/species_icons/abyss_ocepechelon.png` |
| `abyss_onchopristis` | Onchopristis | abyss | SVG_ONLY | não | `refs/species_icons/abyss_onchopristis.png` |
| `abyss_qarmoutus` | Qarmoutus | abyss | SVG_ONLY | não | `refs/species_icons/abyss_qarmoutus.png` |
| `abyss_reaper_abyssal` | Reaper Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_reaper_abyssal.png` |
| `abyss_rex_abyssal` | Rex Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_rex_abyssal.png` |
| `abyss_riftcrawler` | Rift Crawler | abyss | SVG_ONLY | não | `refs/species_icons/abyss_riftcrawler.png` |
| `abyss_seed_rice` | Semente de Arroz | abyss | SVG_ONLY | não | `refs/species_icons/abyss_seed_rice.png` |
| `abyss_seed_cucumis` | Semente de Pepino | abyss | SVG_ONLY | não | `refs/species_icons/abyss_seed_cucumis.png` |
| `abyss_seed_plantspeciesw` | Semente Planta W (Abyss) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_seed_plantspeciesw.png` |
| `abyss_hover_skiff` | Skiff Thalassiano | abyss | SVG_ONLY | não | `refs/species_icons/abyss_hover_skiff.png` |
| `abyss_stego_abyssal` | Stegossauro Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_stego_abyssal.png` |
| `abyss_stereolepis` | Stereolepis | abyss | SVG_ONLY | não | `refs/species_icons/abyss_stereolepis.png` |
| `abyss_theriz_abyssal` | Therizinosaur Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_theriz_abyssal.png` |
| `abyss_thyla_abyssal` | Thylacoleo Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_thyla_abyssal.png` |
| `abyss_tiktaalik` | Tiktaalik | abyss | SVG_ONLY | não | `refs/species_icons/abyss_tiktaalik.png` |
| `abyss_tridacna` | Tridacna | abyss | SVG_ONLY | não | `refs/species_icons/abyss_tridacna.png` |
| `abyss_hover_sail` | Vela Thalassiana (HoverSail) | abyss | SVG_ONLY | não | `refs/species_icons/abyss_hover_sail.png` |
| `abyss_vulcanite` | Vulcanita | abyss | SVG_ONLY | não | `refs/species_icons/abyss_vulcanite.png` |
| `abyss_water_wyvern` | Wyvern Aquática | abyss | SVG_ONLY | não | `refs/species_icons/abyss_water_wyvern.png` |
| `abyss_yuty_abyssal` | Yutyrannus Abissal | abyss | SVG_ONLY | não | `refs/species_icons/abyss_yuty_abyssal.png` |
| `acro` | Acrocantossauro | mod | SVG_ONLY | sim | `refs/species_icons/acro.png` |
| `ancient_wyvern` | Ancient Wyvern | mod | SVG_ONLY | sim | `refs/species_icons/ancient_wyvern.png` |
| `archelon` | Archelon | mod | SVG_ONLY | sim | `refs/species_icons/archelon.png` |
| `armaedron` | Armaedron | mod | SVG_ONLY | sim | `refs/species_icons/armaedron.png` |
| `brachio` | Brachiosaurus | mod | SVG_ONLY | sim | `refs/species_icons/brachio.png` |
| `concavenator` | Concavenator | mod | SVG_ONLY | sim | `refs/species_icons/concavenator.png` |
| `cryolophosaurus` | Cryolophosaurus | mod | SVG_ONLY | sim | `refs/species_icons/cryolophosaurus.png` |
| `deinosuchus` | Deinosuchus | mod | SVG_ONLY | sim | `refs/species_icons/deinosuchus.png` |
| `diru_ya_ku` | Diru-Ya-Ku | mod | SVG_ONLY | sim | `refs/species_icons/diru_ya_ku.png` |
| `dread_wyvern` | Dread Wyvern | mod | SVG_ONLY | sim | `refs/species_icons/dread_wyvern.png` |
| `indominus` | Indominus Rex | mod | SVG_ONLY | sim | `refs/species_icons/indominus.png` |
| `kutsu_ya_ku` | Kutsu-Ya-Ku | mod | SVG_ONLY | sim | `refs/species_icons/kutsu_ya_ku.png` |
| `puretotokage` | Puretotokage | mod | SVG_ONLY | sim | `refs/species_icons/puretotokage.png` |
| `shimosaur` | Shimosaur | mod | SVG_ONLY | sim | `refs/species_icons/shimosaur.png` |
| `xiphactinus` | Xiphactinus | mod | SVG_ONLY | sim | `refs/species_icons/xiphactinus.png` |

## SVG sem WebP (candidatos diretos)

Arquivos `icons/*.svg` cujo `generated/{canonical}.webp` **não existe**:

- `abyss_ankylo_abyssal.svg` → falta `generated/abyss_ankylo_abyssal.webp`
- `abyss_aqualyrium.svg` → falta `generated/abyss_aqualyrium.webp`
- `abyss_barnacle.svg` → falta `generated/abyss_barnacle.webp`
- `abyss_crystallized_wood.svg` → falta `generated/abyss_crystallized_wood.webp`
- `abyss_dakosaurus.svg` → falta `generated/abyss_dakosaurus.webp`
- `abyss_fish_scale.svg` → falta `generated/abyss_fish_scale.webp`
- `abyss_hardened_steel.svg` → falta `generated/abyss_hardened_steel.webp`
- `abyss_homarus.svg` → falta `generated/abyss_homarus.webp`
- `abyss_hover_sail.svg` → falta `generated/abyss_hover_sail.webp`
- `abyss_hover_skiff.svg` → falta `generated/abyss_hover_skiff.webp`
- `abyss_istiophorus.svg` → falta `generated/abyss_istiophorus.webp`
- `abyss_kathreptis.svg` → falta `generated/abyss_kathreptis.webp`
- `abyss_malleocephalus.svg` → falta `generated/abyss_malleocephalus.webp`
- `abyss_manganese.svg` → falta `generated/abyss_manganese.webp`
- `abyss_mantis_shrimp.svg` → falta `generated/abyss_mantis_shrimp.webp`
- `abyss_monodon.svg` → falta `generated/abyss_monodon.webp`
- `abyss_moschops_abyssal.svg` → falta `generated/abyss_moschops_abyssal.webp`
- `abyss_mudpuppy.svg` → falta `generated/abyss_mudpuppy.webp`
- `abyss_ocepechelon.svg` → falta `generated/abyss_ocepechelon.webp`
- `abyss_onchopristis.svg` → falta `generated/abyss_onchopristis.webp`
- `abyss_qarmoutus.svg` → falta `generated/abyss_qarmoutus.webp`
- `abyss_reaper_abyssal.svg` → falta `generated/abyss_reaper_abyssal.webp`
- `abyss_rex_abyssal.svg` → falta `generated/abyss_rex_abyssal.webp`
- `abyss_riftcrawler.svg` → falta `generated/abyss_riftcrawler.webp`
- `abyss_seahorse.svg` → falta `generated/abyss_seahorse.webp`
- `abyss_seaweed.svg` → falta `generated/abyss_seaweed.webp`
- `abyss_seed_cucumis.svg` → falta `generated/abyss_seed_cucumis.webp`
- `abyss_seed_plantspeciesw.svg` → falta `generated/abyss_seed_plantspeciesw.webp`
- `abyss_seed_rice.svg` → falta `generated/abyss_seed_rice.webp`
- `abyss_stego_abyssal.svg` → falta `generated/abyss_stego_abyssal.webp`
- `abyss_stereolepis.svg` → falta `generated/abyss_stereolepis.webp`
- `abyss_takifugu.svg` → falta `generated/abyss_takifugu.webp`
- `abyss_theriz_abyssal.svg` → falta `generated/abyss_theriz_abyssal.webp`
- `abyss_thunnus.svg` → falta `generated/abyss_thunnus.webp`
- `abyss_thyla_abyssal.svg` → falta `generated/abyss_thyla_abyssal.webp`
- `abyss_tiktaalik.svg` → falta `generated/abyss_tiktaalik.webp`
- `abyss_tridacna.svg` → falta `generated/abyss_tridacna.webp`
- `abyss_vulcanite.svg` → falta `generated/abyss_vulcanite.webp`
- `abyss_water_wyvern.svg` → falta `generated/abyss_water_wyvern.webp`
- `abyss_yuty_abyssal.svg` → falta `generated/abyss_yuty_abyssal.webp`
- `acro.svg` → falta `generated/acro.webp`
- `ancient_wyvern.svg` → falta `generated/ancient_wyvern.webp`
- `archelon.svg` → falta `generated/archelon.webp`
- `armaedron.svg` → falta `generated/armaedron.webp`
- `brachio.svg` → falta `generated/brachio.webp`
- `concavenator.svg` → falta `generated/concavenator.webp`
- `cryolophosaurus.svg` → falta `generated/cryolophosaurus.webp`
- `deinosuchus.svg` → falta `generated/deinosuchus.webp`
- `diru_ya_ku.svg` → falta `generated/diru_ya_ku.webp`
- `dread_wyvern.svg` → falta `generated/dread_wyvern.webp`
- `indominus.svg` → falta `generated/indominus.webp`
- `kutsu_ya_ku.svg` → falta `generated/kutsu_ya_ku.webp`
- `puretotokage.svg` → falta `generated/puretotokage.webp`
- `shimosaur.svg` → falta `generated/shimosaur.webp`
- `xiphactinus.svg` → falta `generated/xiphactinus.webp`

---

## Já tem referência salva

| arquivo | espécie provável | já tem WebP? |
|---------|------------------|--------------|
| `achatina.png` | `achatina` | sim |
| `allo.png` | `allo` | sim |
| `amargasaurus.png` | `amargasaurus` | sim |
| `andrewsarchus.png` | `andrewsarchus` | sim |
| `ankylo.png` | `ankylo` | sim |
| `argent.png` | `argent` | sim |
| `astrocetus.png` | `astrocetus` | sim |
| `astrodelphis.png` | `astrodelphis` | sim |
| `baryonyx.png` | `baryonyx` | sim |
| `basilisk.png` | `basilisk` | sim |
| `basilosaurus.png` | `basilosaurus` | sim |
| `beaver.png` | `beaver` | sim |
| `bionicgigant.png` | `bionicgigant` | sim |
| `bionicrex.png` | `bionicrex` | sim |
| `bloodstalker.png` | `bloodstalker` | sim |
| `bronto.png` | `bronto` | sim |
| `carbonemys.png` | `carbonemys` | sim |
| `carcha_femea.png` | `carcha_femea` | sim |
| `carno.png` | `carno` | sim |
| `castoroides.png` | `castoroides` | sim |
| `compy.png` | `compy` | sim |
| `crystalwyvern.png` | `crystalwyvern` | sim |
| `daeodon.png` | `daeodon` | sim |
| `deinonychus.png` | `deinonychus` | sim |
| `deinonychus_femea.png` | `deinonychus_femea` | sim |
| `desmodus.png` | `desmodus` | sim |
| `dimorph.png` | `dimorph` | sim |
| `dinopithecus.png` | `dinopithecus` | sim |
| `diplodocus.png` | `diplodocus` | sim |
| `direwolf.png` | `direwolf` | sim |
| `dodo.png` | `dodo` | sim |
| `doed.png` | `doed` | sim |
| `doedicurus.png` | `doedicurus` | sim |
| `dunkle.png` | `dunkle` | sim |
| `equus.png` | `equus` | sim |
| `fenrir.png` | `fenrir` | sim |
| `ferox.png` | `ferox` | sim |
| `fjordhawk.png` | `fjordhawk` | sim |
| `gacha.png` | `gacha` | sim |
| `gallimimus.png` | `gallimimus` | sim |
| `gasbags.png` | `gasbags` | sim |
| `giga.png` | `giga` | sim |
| `gigant.png` | `gigant` | sim |
| `griffin.png` | `griffin` | sim |
| `iguanodon.png` | `iguanodon` | sim |
| `jerboa.png` | `jerboa` | sim |
| `kairuku.png` | `kairuku` | sim |
| `kaprosuchus.png` | `kaprosuchus` | sim |
| `lionfish_femea.png` | `lionfish_femea` | sim |
| `lionfishlion.png` | `lionfishlion` | sim |
| `lystrosaurus.png` | `lystrosaurus` | sim |
| `maewing.png` | `maewing` | sim |
| `magmasaur.png` | `magmasaur` | sim |
| `mammoth.png` | `mammoth` | sim |
| `managarmr.png` | `managarmr` | sim |
| `mantis.png` | `mantis` | sim |
| `megachelon.png` | `megachelon` | sim |
| `megalodon.png` | `megalodon` | sim |
| `megalosaurus.png` | `megalosaurus` | sim |
| `megalosaurus_aberrant_femea.png` | `megalosaurus_aberrant_femea` | sim |
| `megalosaurus_femea.png` | `megalosaurus_femea` | sim |
| `megatherium.png` | `megatherium` | sim |
| `mosasaurus.png` | `mosasaurus` | sim |
| `otter.png` | `otter` | sim |
| `owl.png` | `owl` | sim |
| `para.png` | `para` | sim |
| `paracer.png` | `paracer` | sim |
| `pelagornis.png` | `pelagornis` | sim |
| `phiomia.png` | `phiomia` | sim |
| `plesiosaur.png` | `plesiosaur` | sim |
| `procoptodon.png` | `procoptodon` | sim |
| `ptera.png` | `ptera` | sim |
| `pulmonoscorpius.png` | `pulmonoscorpius` | sim |
| `purlovia.png` | `purlovia` | sim |
| `quetz.png` | `quetz` | sim |
| `raptor.png` | `raptor` | sim |
| `rex.png` | `rex` | sim |
| `rhynio.png` | `rhynio` | sim |
| `rockdrake.png` | `rockdrake` | sim |
| `sabertooth.png` | `sabertooth` | sim |
| `sarco.png` | `sarco` | sim |
| `sinomacrops.png` | `sinomacrops` | sim |
| `spino.png` | `spino` | sim |
| `stego.png` | `stego` | sim |
| `tapejara.png` | `tapejara` | sim |
| `tekstrider.png` | `tekstrider` | sim |
| `tekstrider_femea.png` | `tekstrider_femea` | sim |
| `theriz.png` | `theriz` | sim |
| `thyla.png` | `thyla` | sim |
| `titanboa.png` | `titanboa` | sim |
| `trike.png` | `trike` | sim |
| `tropeognathus.png` | `tropeognathus` | sim |
| `tuso.png` | `tuso` | sim |
| `velonasaur.png` | `velonasaur` | sim |
| `volcanorex.png` | `volcanorex` | sim |
| `wyvern.png` | `wyvern` | sim |
| `xenomorph.png` | `xenomorph` | sim |
| `xenomorph_femea.png` | `xenomorph_femea` | sim |
| `xenomorphgen2_femea.png` | `xenomorphgen2_femea` | sim |
| `yuty.png` | `yuty` | sim |

## Já aprovados / done na fila

Espécies marcadas como concluídas em `docs/SPECIES_ICON_REGEN_QUEUE.md`:

| species_key | display_name | status atual | WebP |
|-------------|--------------|--------------|------|
| `megalosaurus` | Megalossauro | NEEDS_REGEN | `megalosaurus.webp` |
| `megalosaurus_aberrant_femea` | Megalosaurus Aberrante | NEEDS_REGEN | `megalosaurus.webp` |
| `megalosaurus_femea` | Megalosaurus | NEEDS_REGEN | `megalosaurus.webp` |
| `reaper` | Reaper | HAS_AI_WEBP | `reaper.webp` |
| `tekstrider` | Tek Strider | NEEDS_REGEN | `tekstrider.webp` |
| `tekstrider_femea` | Tek Strider | NEEDS_REGEN | `tekstrider.webp` |
| `xenomorph` | Reaper | HAS_AI_WEBP | `reaper.webp` |
| `xenomorph_femea` | Xenomorph | HAS_AI_WEBP | `reaper.webp` |
| `xenomorphgen2_femea` | Xenomorph Gen2 | HAS_AI_WEBP | `reaper.webp` |

## Fila regen pendente (`generated/manifest.json`)

| # | species_key | nota | ref sugerida | já tem ref salva? |
|---|-------------|------|--------------|-------------------|
| 1 | `mosasaurus` | Muito magro; anatomia incorreta | `refs/species_icons/mosasaurus.png` | sim |
| 2 | `astrocetus` | Ícone ruim | `refs/species_icons/astrocetus.png` | sim |
| 3 | `bloodstalker` | Ícone ruim | `refs/species_icons/bloodstalker.png` | sim |
| 4 | `castoroides` | Duas imagens (alias beaver consolidado) | `refs/species_icons/castoroides.png` | sim |
| 5 | `crystalwyvern` | Ícone ruim | `refs/species_icons/crystalwyvern.png` | sim |
| 6 | `deinonychus` | Duas imagens (variante deinonychus_femea) | `refs/species_icons/deinonychus.png` | sim |
| 7 | `doedicurus` | Duas imagens (alias doed consolidado) | `refs/species_icons/doedicurus.png` | sim |
| 8 | `gacha` | Ícone ruim | `refs/species_icons/gacha.png` | sim |
| 9 | `gasbags` | Ícone ruim | `refs/species_icons/gasbags.png` | sim |
| 10 | `giga` | Duas imagens giganotossauro (giga + gigant) | `refs/species_icons/giga.png` | sim |
| 11 | `megalosaurus` | Duas imagens (variantes _femea) | `refs/species_icons/megalosaurus.png` | sim |
| 12 | `phiomia` | Parece elefante | `refs/species_icons/phiomia.png` | sim |
| 13 | `rhynio` | Parece besouro de esterco (Rhinognatha) | `refs/species_icons/rhynio.png` | sim |
| 14 | `sinomacrops` | Ícone ruim | `refs/species_icons/sinomacrops.png` | sim |
| 15 | `tekstrider` | Ícone ruim (variante tekstrider_femea) | `refs/species_icons/tekstrider.png` | sim |

---

## Fontes auditadas

- `plugin/arkshop_web/static/species/icons/*.svg`
- `plugin/arkshop_web/static/species/icons/generated/*.webp`
- `plugin/arkshop_web/data/species_icons_manifest.json`
- `plugin/arkshop_web/static/species/icons/generated/manifest.json`
- `plugin/arkshop_web/data/market_species_defaults.json`
- `plugin/arkshop_web/data/ark_species_registry.json`
- `plugin/arkshop_web/data/official_vanilla_species.json`
- `plugin/CustomShop/configs/config.json` (Items Type:dino)
- `refs/species_icons/` (referências do usuário)

## Aliases canônicos (1 WebP para várias chaves)

- `beaver` → `castoroides`
- `deinonychus_femea` → `deinonychus`
- `doed` → `doedicurus`
- `giganotosaurus` → `giga`
- `gigant` → `giga`
- `megalosaurus_aberrant_femea` → `megalosaurus`
- `megalosaurus_femea` → `megalosaurus`
- `tekstrider_femea` → `tekstrider`
- `xenomorph` → `reaper`
- `xenomorph_femea` → `reaper`
- `xenomorphgen2_femea` → `reaper`

---

## Referências de recursos (`refs/resource_icons/`)

> Itens `rec_*` sem entrada no DodoDex podem receber referência manual do usuário (não gera ícone de loja automaticamente).

| rec_key | fonte | arquivo | notas |
|---------|-------|---------|-------|
| `rec_HardenedSteelIngot` | usuário | `refs/resource_icons/rec_HardenedSteelIngot.png` | Lingote de Aço Endurecido (mod Abyss) — ausente no DodoDex |
