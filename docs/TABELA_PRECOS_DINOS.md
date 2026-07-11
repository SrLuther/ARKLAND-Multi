# TABELA COMPLETA DE PREÇOS — DINOS ARKLAND

> **Tipo:** Referência de Precificação (Documentação)  
> **Status:** Proposta — não aplicar sem aprovação admin  
> **Versão:** 1.0 — Jul 2026  
> **Fontes:** `plugin/CustomShop/configs/config.json` · `tools/blueprint_catalog_matrix.csv` · `plugin/arkshop_web/data/market_species_defaults.json` · [`PROJETO_ECONOMIA_IDEAL.md`](./PROJETO_ECONOMIA_IDEAL.md)  
> **Referência cruzada:** [`ECONOMIA_ARKLAND.md`](./ECONOMIA_ARKLAND.md)

---

## Parâmetros do Modelo (floor_quality)

| Parâmetro | Valor atual | Descrição |
|-----------|------------|-----------|
| `gamma` (γ) | **0.82** | Curvatura de retornos decrescentes do índice Q |
| `market_absolute_max` | **150.000 Â** | Teto global de anúncio no Mercado P2P |
| `encomenda_absolute_max` | **275.000 Â** | Teto global de encomenda customizada |
| `encomenda_alpha` (α) | **0.25** | Taxa base de serviço sobre R |
| `encomenda_beta` (β) | **0.35** | Taxa sobre valor de mercado |
| `pts_reference` | **254** | Pontos de referência (máximo breedável) |

**Fórmulas-chave:**

```
Mercado(Q) = min(R + B × Q, 150.000)   — Q∈[0,1], γ=0.82
Encomenda   = clamp(Mercado + R×α + Mercado×β,  max(Mercado, R),  275.000)
Encomenda_L1 = R × 1.60   (sem stats, sem cores)
Encomenda_254 ≈ Mercado_254 × 1.35 + R × 0.25
```

---

## Legenda

| Símbolo | Significado |
|---------|-------------|
| **=** | R proposto idêntico ao atual |
| **≈** | Diferença < 2% (ajuste mínimo) |
| **↑** | R proposto maior que o atual |
| **↓** | R proposto menor que o atual |
| `catalog_only` | Não disponível no Mercado P2P |
| `market_p2p` | Disponível no Mercado P2P |

**Tiers:** S+ (apex/boss/tek) · S (apex PvP) · A (meta breeding) · B (intermediário) · C (entrada)  
**Papéis:** `boss` · `raid` · `ataque` · `locomocao` · `utilitario`

---

## Rationale — Por que 95.000 era Absurdo e Como Chegamos ao Novo Valor

### O Problema com R = 95.000

| Perfil de jogador | Tempo p/ Armaedron **antes** (95k) | Tempo p/ Armaedron **depois** (35k) | Redução |
|-------------------|-------------------------------------|--------------------------------------|---------|
| Default (50 Â/h · 2h/dia) | 1.900h = **950 dias** (~31 meses) | 700h = **350 dias** (~12 meses) | −63% |
| Gamma (100 Â/h · 2h/dia) | 950h = **475 dias** (~16 meses) | 350h = **175 dias** (~6 meses) | −63% |
| Alfa (200 Â/h · 4h/dia) | 475h = **118 dias** (~4 meses) | 175h = **43 dias** (~1,5 mês) | −63% |

**Problemas identificados com o valor de 95.000:**

1. **Paridade absurda com licenças:** A Licença Alfa custa 100.000 Â. O dino apex do catálogo era praticamente equivalente ao tier de assinatura máxima — isso cria uma inversão de percepção: "por que comprar um dino se ele custa como uma licença vitalícia?".
2. **Escala Armaedron/Rex = 5.3×:** Diferença excessiva. O jogador que evolui de Rex para Armaedron enfrenta uma barreira de 77.000 Â (95k − 18k) para um único step de tier. Comparar: Kit Rex 10× custa 37.500 — metade de UM Armaedron.
3. **Cluster S+ colapsado:** IndoRaptor, Dread e Ancient Wyvern estavam todos em ~90k, virtualmente no mesmo preço que o Armaedron (95k). Isso elimina a percepção hierárquica dentro do tier.
4. **Horizon de progressão quebrado:** Um jogador Default novo levaria quase 3 anos jogando 2h/dia para alcançar o apex. Em um servidor de ARK, isso é inviável — a maioria abandona antes.

### Nova Escada de Âncoras (antes → depois)

| Âncora | R antes | R depois | Δ | Ratio | Horas Default (50Â/h) |
|--------|---------|----------|---|-------|----------------------|
| **Armaedron** | 95.000 | **35.000** | −60.000 | 0.37× | 700h (~12 meses a 2h/dia) |
| **Indominus Rex** | 70.000 | **28.000** | −42.000 | 0.40× | 560h (~9 meses a 2h/dia) |
| **Carcharodontosaurus** | 25.000 | **25.000** | — | 1.00× | 500h (âncora mantida) |
| **Rex** | 18.000 | **18.000** | — | 1.00× | 360h (âncora mantida) |

**Hierarquia preservada:** Armaedron (35k) > Indominus (28k) > Carcha (25k) > Rex (18k) ✓

### Por que 35.000 especificamente?

- **Premium sem absurdo:** 35k coloca o Armaedron como alvo de ~12 meses para jogador casual (2h/dia sem licença), ou ~1,5 mês para um jogador dedicado com Alfa — ambos parecem desafiadores mas atingíveis.
- **Spread de breeding ampliado:** Com mercado_254 = 150.000 inalterado, o spread de valor pela qualidade de breeding passa de 55.000 (antes, 58% de premium) para **115.000 (329% de premium)**. O Armaedron 254pts agora vale 4.3× um L1 de catálogo — muito mais incentivo para breed.
- **Razão Armaedron/Rex = 1.9×** (era 5.3×) — escala de progressão muito mais natural.
- **35k ≈ Licença Gamma × 0.70** — sinaliza que o apex é um objeto de jogo premium, mas acessível para quem já tem alguma progressão.

### B values novos (breeding premium budget)

Com R reduzido e teto de mercado (150k) mantido, o **B** aumenta — recompensando muito mais o breeding:

| Espécie | R antes | R depois | B antes | B depois | Variação B |
|---------|---------|----------|---------|----------|------------|
| Armaedron | 95.000 | 35.000 | 55.000 | **115.000** | +109% |
| Indominus Rex | 70.000 | 28.000 | 80.000 | **122.000** | +53% |
| Giga Tek | 46.464 | 22.000 | 103.536 | **128.000** | +24% |

---

## Tabela Principal — 79 Espécies (ordenadas por R proposto ↓)

> **Colunas:** `R atual` = preço L1 no catálogo = piso do mercado (floor). `Mercado 254pts` = valor máximo com dino totalmente breedado (254 pts). `Enc. max` = encomenda máxima (254 pts, sem cor, arredondado). `Prest.` = prestige_rank (0–100).

| # | ID Catálogo | Nome | Blueprint (short) | Role | Tier | Prest. | R atual | R proposto | Δ | Merc. 254pts | Enc. max | Canal | Notas |
|---|-------------|------|-------------------|------|------|--------|---------|------------|---|-------------|---------|-------|-------|
| 1 | `armaedron` | Armaedron | Armaedron_Character_BP | boss | S+ | 98 | 95.000 | **35.000** | ↓ | 150.000 | **211.250** | market_p2p | ↓ Recalibrado Jul/2026 — 35k=700h default; spread breeding ×3.3 |
| 2 | `dread_wyvern` | Dread Wyvern | Wyvern_Character_BP_Dread | boss | S+ | 90 | 91.464 | **33.000** | ↓ | 150.000 | **210.750** | market_p2p | ↓ Alinhar com prestige_rank 90 |
| 3 | `ancient_wyvern` | Ancient Wyvern | Wyvern_Character_BP_Ancient | boss | S+ | 88 | 90.757 | **32.000** | ↓ | 150.000 | **210.500** | market_p2p | ↓ Alinhar com prestige_rank 88 |
| 4 | `indoraptor` | IndoRaptor | NewIndoRaptor_Character_BP | boss | S+ | 87 | 90.404 | **32.000** | ↓ | 150.000 | **210.500** | market_p2p | ↓ Alinhar com prestige_rank 87 |
| 5 | `indominus` | Indominus Rex | IndominusRex_Character_BP | boss | S+ | 92 | 70.000 | **28.000** | ↓ | 150.000 | **209.500** | market_p2p | ↓ Recalibrado Jul/2026 — boss S+ âncora; mantém hierarquia Armaedron>Indominus>Carcha |
| 6 | `sb_hydra` | Small Hydra | SmallHydra_Character_BP | boss | S | 74 | 52.121 | **24.000** | ↓ | 150.000 | **208.500** | market_p2p | Único boss tier S |
| 7 | `bionicgigant` | Giganotossauro Tek | BionicGigant_Character_BP | ataque | S+ | 86 | 46.464 | **22.000** | ↓ | 150.000 | **208.000** | market_p2p | Aceitável — Bionic Giga |
| 8 | `bionicrex` | Rex Tek | BionicRex_Character_BP | ataque | S+ | 84 | 45.959 | **21.000** | ↓ | 150.000 | **207.750** | market_p2p | Aceitável — Bionic Rex |
| 9 | `lionfish` | Shadowmane | LionfishLion_Character_BP | raid | S | 78 | 35.555 | **22.000** | ↓ | 130.000 | **181.000** | market_p2p | Aceitável — teto raid S=130k |
| 10 | `tekstrider` | Tek Strider | TekStrider_Character_BP | boss | S+ | 85 | 35.000 | **26.000** | ↓ | 150.000 | **209.000** | **catalog_only** | Apenas catálogo — sem mercado P2P |
| 11 | `sb_volcano_dragon` | Volcano Small Dragon | Volcano_SmallDragon_Character_BP | boss | A | 72 | 25.757 | **26.000** | ↑ | 120.000 | 168.439 | market_p2p | ↑ Leve ajuste — topo A boss |
| 12 | `sb_small_dragon` | Small Dragon | SmallDragon_Character_BP | boss | A | 70 | 25.454 | **25.500** | ≈ | 120.000 | 168.364 | market_p2p | Aceitável |
| 13 | `sb_broodmother` | Small Broodmother | SmallBroodmother_Character_BP | boss | A | 68 | 25.151 | **25.000** | ≈ | 120.000 | 168.288 | market_p2p | Aceitável ¹ |
| 14 | `sb_fire_elemental` | Fire Elemental | FireElemental_Character_BP | boss | A | 68 | 25.151 | **25.000** | ≈ | 120.000 | 168.288 | market_p2p | Aceitável |
| 15 | `sb_fire_elemental_tame` | Fire Elemental Domável | FireElemental_Character_BP_Tameable | boss | A | 68 | 25.151 | **25.000** | ≈ | 120.000 | 168.288 | market_p2p | Variante domável — mesmo R ¹ |
| 16 | `carcha` | Carcharodontosaurus | Carcha_Character_BP | raid | S+ | 88 | 25.000 | **25.000** | = | 150.000 | 208.750 | market_p2p | Âncora raid S+ — imutável |
| 17 | `sb_crystal_queen` | Crystal Wyvern Queen | CrystalWyvern_Character_BP_Queen | boss | A | 67 | 25.000 | **25.000** | = | 120.000 | 168.250 | market_p2p | Aceitável |
| 18 | `sb_desert_titan` | Small Desert Titan | DesertTitan_Character_BP_SB | boss | A | 67 | 25.000 | **25.000** | = | 120.000 | 168.250 | market_p2p | Aceitável |
| 19 | `sb_dodoreaper` | Small Dodoreaper | SmallDodoreaper_Character_BP | boss | A | 66 | 24.848 | **25.000** | ↑ | 120.000 | 168.212 | market_p2p | ↑ Arredondamento — uniformidade |
| 20 | `sb_dodorex` | Small DodoRex | SmallDodoRex_Character_BP | boss | A | 66 | 24.848 | **25.000** | ↑ | 120.000 | 168.212 | market_p2p | ↑ Arredondamento — uniformidade |
| 21 | `sb_manticore` | Small Manticore | SmallManticore_Character_BP | boss | A | 65 | 24.696 | **24.500** | ↓ | 120.000 | 168.174 | market_p2p | ↓ Leve ajuste pelo prestige_rank |
| 22 | `sb_megapithecus` | Small Megapithecus | SmallGorilla_Character_BP | boss | A | 64 | 24.545 | **24.500** | ≈ | 120.000 | 168.136 | market_p2p | Aceitável |
| 23 | `sb_cyclops` | Small Cyclops | SmallCyclops_Character_BP | boss | A | 62 | 24.242 | **24.000** | ↓ | 120.000 | 168.060 | market_p2p | ↓ Leve ajuste pelo prestige_rank |
| 24 | `giga` | Giganotosaurus | Gigant_Character_BP | ataque | S | 82 | 22.636 | **22.500** | ≈ | 108.000 | 151.459 | market_p2p | Aceitável — teto ataque S=108k |
| 25 | `acro` | Acrocantossauro | Acrocanthosaurus_Character_BP | ataque | S | 80 | 22.373 | **22.000** | ≈ | 108.000 | 151.393 | market_p2p | Aceitável — ARK Additions |
| 26 | `rex` | Rex | Rex_Character_BP | ataque | S | 75 | 18.000 | **18.000** | = | 108.000 | 150.300 | market_p2p | Âncora ataque S — imutável |
| 27 | `abyss_rex_abyssal` | Rex Abissal | Rex_Character_BP_Abyssal | raid | A | 72 | 16.606 | **16.500** | ≈ | 90.000 | 125.652 | market_p2p | Aceitável — Mod Abyss |
| 28 | `abyss_reaper_abyssal` | Reaper Abissal | Reaper_Character_BP_Male_Abyssal | raid | A | 70 | 16.363 | **16.000** | ≈ | 90.000 | 125.591 | market_p2p | Aceitável — Mod Abyss |
| 29 | `xenomorphgen2` | Reaper Gen2 | Xenomorph_Character_BP_Male_Gen2_Summoned | raid | A | 69 | 16.242 | **16.000** | ≈ | 90.000 | 125.560 | market_p2p | Aceitável — Genesis 2 |
| 30 | `xenomorph` | Reaper | Xenomorph_Character_BP_Male | raid | A | 68 | 16.121 | **16.000** | ≈ | 90.000 | 125.530 | market_p2p | Aceitável — Aberration |
| 31 | `sb_drake_fire` | Small Drake Fogo | SmallDrake_Character_BP_Fire | raid | A | 63 | 15.515 | **15.500** | ≈ | 90.000 | 125.379 | market_p2p | Aceitável |
| 32 | `sb_crystal_blood` | Crystal Wyvern Blood | CrystalWyvern_Character_BP_Descendant_Blood | raid | A | 60 | 15.151 | **15.000** | ≈ | 90.000 | 125.288 | market_p2p | Aceitável — Crystal Queen desc. |
| 33 | `sb_crystal_ember` | Crystal Wyvern Ember | CrystalWyvern_Character_BP_Descendant_Ember | raid | A | 60 | 15.151 | **15.000** | ≈ | 90.000 | 125.288 | market_p2p | Aceitável — Crystal Queen desc. |
| 34 | `abyss_yuty_abyssal` | Yutyrannus Abissal | Yutyrannus_Character_BP_Abyssal | ataque | A | 68 | 9.737 | **10.000** | ↑ | 75.000 | 103.684 | market_p2p | ↑ Alinhar teto A/ataque=75k |
| 35 | `volcanorex` | Volcano Rex | Volcano_Rex_Character_BP | ataque | A | 66 | 9.595 | **9.500** | ≈ | 75.000 | 103.649 | market_p2p | Aceitável — Genesis |
| 36 | `deinonychus` | Deinonychus | Deinonychus_Character_BP | ataque | A | 65 | 9.525 | **9.500** | ≈ | 75.000 | 103.631 | market_p2p | Aceitável — Fjordur |
| 37 | `puretotokage` | Puretotokage | Puretotokage_Character_BP | ataque | A | 65 | 9.525 | **9.500** | ≈ | 75.000 | 103.631 | market_p2p | Aceitável — Grand Hunt |
| 38 | `shimosaur` | Shimosaur | Shimosaur_Character_BP | ataque | A | 64 | 9.454 | **9.500** | ↑ | 75.000 | 103.614 | market_p2p | ↑ Brighamia — leve ajuste |
| 39 | `megalosaurus_aberrant` | Megalosaurus Aberrante | Megalosaurus_Character_BP_Aberrant | ataque | A | 64 | 9.454 | **9.500** | ↑ | 75.000 | 103.614 | market_p2p | ↑ Aberração — uniformidade |
| 40 | `megalosaurus` | Megalosaurus | Megalosaurus_Character_BP | ataque | A | 62 | 9.313 | **9.000** | ↓ | 75.000 | 103.578 | market_p2p | ↓ Escalar com prestige_rank 62 |
| 41 | `astrodelphis` | Astrodelphis | SpaceDolphin_Character_BP | locomocao | A | 72 | 6.868 | **7.000** | ↑ | 42.000 | 58.417 | market_p2p | ↑ Flyer raro — escassez justifica |
| 42 | `desmodus` | Desmodus | Desmodus_Character_BP | locomocao | A | 70 | 6.787 | **7.000** | ↑ | 42.000 | 58.397 | market_p2p | ↑ Flyer Fjordur — mesma lógica |
| 43 | `abyss_water_wyvern` | Wyvern Aquática | Wyvern_Character_BP_Water | locomocao | A | 62 | 6.464 | **6.500** | ≈ | 42.000 | 58.316 | market_p2p | Aceitável — Mod Abyss |
| 44 | `sb_hippocampus` | Small Hippocampus | SmallHippocampus_Character_BP | locomocao | A | 58 | 6.303 | **6.500** | ↑ | 42.000 | 58.276 | market_p2p | ↑ Uniformidade A/locomocao |
| 45 | `sb_dodowyvern` | Small Dodowyvern | SmallDodowyvern_Character_BP | raid | B | 58 | 5.878 | **6.000** | ↑ | 45.000 | 62.220 | market_p2p | ↑ Piso B/raid recomendado |
| 46 | `sb_moeder` | Small Moeder | SmallMoeder_Character_BP | boss | B | 55 | 5.000 | **5.000** | = | 25.000 | 35.000 | market_p2p | Aceitável — boss B |
| 47 | `abyss_dakosaurus` | Dakosaurus | Dakosaurus_Character_BP | ataque | B | 52 | 3.545 | **3.500** | ≈ | 35.000 | 48.136 | market_p2p | Aceitável — Mod Abyss |
| 48 | `deinosuchus` | Deinosuchus | Deinosuchus_Character_BP | ataque | B | 50 | 3.484 | **3.500** | ≈ | 35.000 | 48.121 | market_p2p | Aceitável — ARK Additions |
| 49 | `abyss_vulcanite` | Vulcanita | Vulcanite_Character_BP | ataque | B | 50 | 3.484 | **3.500** | ≈ | 35.000 | 48.121 | market_p2p | Aceitável — Mod Abyss |
| 50 | `sb_crystal_tropical` | Crystal Wyvern Tropical | CrystalWyvern_Character_BP_Descendant_Tropical | ataque | B | 50 | 3.484 | **3.500** | ≈ | 35.000 | 48.121 | market_p2p | Aceitável — Crystal Queen desc. |
| 51 | `xiphactinus` | Xiphactinus | Xiph_Character_BP | ataque | B | 50 | 3.484 | **3.500** | ≈ | 35.000 | 48.121 | market_p2p | Aceitável — ARK Additions |
| 52 | `abyss_riftcrawler` | Rift Crawler | RiftCrawler_Character_BP | ataque | B | 48 | 3.424 | **3.500** | ↑ | 35.000 | 48.106 | market_p2p | ↑ Unificar piso B/ataque=3.500 |
| 53 | `abyss_thyla_abyssal` | Thylacoleo Abissal | Thylacoleo_Character_BP_Abyssal | ataque | B | 48 | 3.424 | **3.500** | ↑ | 35.000 | 48.106 | market_p2p | ↑ Unificar piso B/ataque=3.500 |
| 54 | `concavenator` | Concavenator | Concavenator_Character_BP | ataque | B | 48 | 3.424 | **3.500** | ↑ | 35.000 | 48.106 | market_p2p | ↑ ARK Additions — unificar |
| 55 | `cryolophosaurus` | Cryolophosaurus | Cryolophosaurus_Character_BP | ataque | B | 45 | 3.333 | **3.500** | ↑ | 35.000 | 48.083 | market_p2p | ↑ ARK Additions — piso B ataque |
| 56 | `kutsu_ya_ku` | Kutsu-Ya-Ku | KutsuYaKu_Character_BP | ataque | B | 45 | 3.333 | **3.500** | ↑ | 35.000 | 48.083 | market_p2p | ↑ Grand Hunt — piso B ataque |
| 57 | `brachio` | Brachiosaurus | Brachiosaurus_Character_BP | utilitario | B | 55 | 2.318 | **2.500** | ↑ | 15.000 | 20.830 | market_p2p | ↑ Piso B/utilitario recomendado |
| 58 | `abyss_theriz_abyssal` | Therizinosaur Abissal | Therizino_Character_BP_Abyssal | utilitario | B | 52 | 2.272 | **2.500** | ↑ | 15.000 | 20.818 | market_p2p | ↑ Uniformidade B/utilitario |
| 59 | `archelon` | Archelon | Archelon_Character_BP | utilitario | B | 48 | 2.212 | **2.500** | ↑ | 15.000 | 20.803 | market_p2p | ↑ ARK Additions — piso B util. |
| 60 | `diru_ya_ku` | Diru-Ya-Ku | DiruYaKu_Character_BP | ataque | C | 38 | 1.311 | **1.500** | ↑ | 15.000 | 20.578 | market_p2p | ↑ Mínimo C=1.500 recomendado |
| 61 | `abyss_mantis_shrimp` | Camarão-mantis | MantisShrimp_Character_BP | ataque | C | 32 | 1.244 | **1.500** | ↑ | 15.000 | 20.561 | market_p2p | ↑ Mínimo C=1.500 recomendado |
| 62 | `abyss_onchopristis` | Onchopristis | Onchopristis_Character_BP | ataque | C | 30 | 1.222 | **1.200** | ≈ | 15.000 | 20.556 | market_p2p | Aceitável |
| 63 | `abyss_istiophorus` | Marlim (Istiophorus) | Istiophorus_Character_BP | locomocao | C | 30 | 1.005 | **1.000** | ≈ | 12.000 | 16.451 | market_p2p | Aceitável — C/locomocao |
| 64 | `abyss_stego_abyssal` | Stegossauro Abissal | Stego_Character_BP_Abyssal | utilitario | C | 40 | 696 | **800** | ↑ | 8.000 | 10.974 | market_p2p | ↑ Piso C/utilitario = 800 |
| 65 | `abyss_stereolepis` | Stereolepis | Stereolepis_Character_BP | utilitario | C | 38 | 686 | **800** | ↑ | 8.000 | 10.972 | market_p2p | ↑ Piso C/utilitario = 800 |
| 66 | `abyss_tiktaalik` | Tiktaalik | Tiktaalik_Character_BP | utilitario | C | 35 | 671 | **800** | ↑ | 8.000 | 10.968 | market_p2p | ↑ Piso C/utilitario = 800 |
| 67 | `abyss_tridacna` | Tridacna | Tridacna_Character_BP | utilitario | C | 35 | 671 | **800** | ↑ | 8.000 | 10.968 | market_p2p | ↑ Piso C/utilitario = 800 |
| 68 | `abyss_thunnus` | Atum (Thunnus) | Thunnus_Character_BP | utilitario | C | 32 | 656 | **700** | ↑ | 8.000 | 10.964 | market_p2p | ↑ Leve ajuste acima de 636 |
| 69 | `abyss_ankylo_abyssal` | Anquilossauro Abissal | Ankylo_Character_BP_Abyssal | utilitario | C | 30 | 646 | **700** | ↑ | 8.000 | 10.962 | market_p2p | ↑ Leve ajuste |
| 70 | `abyss_qarmoutus` | Qarmoutus | Qarmoutus_Character_BP | utilitario | C | 28 | 636 | **700** | ↑ | 8.000 | 10.959 | market_p2p | ↑ Unificar C/util. ≥700 |
| 71 | `abyss_ocepechelon` | Ocepechelon | Ocepechelon_Character_BP | utilitario | C | 28 | 636 | **700** | ↑ | 8.000 | 10.959 | market_p2p | ↑ Unificar C/util. ≥700 |
| 72 | `abyss_malleocephalus` | Malleocephalus | Malleocephalus_Character_BP | utilitario | C | 28 | 636 | **700** | ↑ | 8.000 | 10.959 | market_p2p | ↑ Unificar C/util. ≥700 |
| 73 | `abyss_kathreptis` | Kathreptis | Kathreptis_Character_BP | utilitario | C | 28 | 636 | **700** | ↑ | 8.000 | 10.959 | market_p2p | ↑ Unificar C/util. ≥700 |
| 74 | `abyss_homarus` | Lagosta (Homarus) | Homarus_Character_BP | utilitario | C | 28 | 636 | **700** | ↑ | 8.000 | 10.959 | market_p2p | ↑ Unificar C/util. ≥700 |
| 75 | `abyss_takifugu` | Baiacu (Takifugu) | Takifugu_Character_BP | utilitario | C | 25 | 621 | **700** | ↑ | 8.000 | 10.955 | market_p2p | ↑ Uniformidade |
| 76 | `abyss_mudpuppy` | Mudpuppy | Mudpuppy_Character_BP | utilitario | C | 22 | 606 | **650** | ↑ | 8.000 | 10.952 | market_p2p | ↑ Piso mínimo C |
| 77 | `abyss_seahorse` | Cavalo-marinho | Seahorse_Character_BP | utilitario | C | 20 | 595 | **650** | ↑ | 8.000 | 10.949 | market_p2p | ↑ Piso mínimo C |
| 78 | `abyss_monodon` | Narval (Monodon) | Monodon_Character_BP | utilitario | C | 18 | 585 | **600** | ↑ | 8.000 | 10.946 | market_p2p | ↑ Piso mínimo C |
| 79 | `abyss_moschops_abyssal` | Moschops Abissal | Moschops_Character_BP_Abyssal | utilitario | C | 18 | 585 | **600** | ↑ | 8.000 | 10.946 | market_p2p | ↑ Piso mínimo C |

> ¹ **sb_broodmother** e **sb_fire_elemental_tame** não aparecem na tabela do `PROJETO_ECONOMIA_IDEAL.md` — R proposto inferido por analogia com as demais criaturas boss tier A (R=25.000).

---

## Estatísticas Resumidas

### Totais e Contagem

| Métrica | Valor |
|---------|-------|
| **Total de dinos únicos no catálogo (L1)** | **79** |
| Dinos na matriz `blueprint_catalog_matrix.csv` | 79 |
| Dinos no `market_species_defaults.json` | 78 |
| Dinos no `PROJETO_ECONOMIA_IDEAL.md` tabela | 77 (2 ausentes: ver nota ¹) |
| Canal `catalog_only` | 1 (Tek Strider) |
| Canal `market_p2p` | 78 |

### Faixas de Preço por Tier

> **v2 Jul/2026:** S+ e S topo recalibrados. A, B, C inalterados.

| Tier | Qtd. | R mín. atual | R máx. atual | R mín. proposto | R máx. proposto | Mediana proposta |
|------|------|-------------|-------------|----------------|----------------|-----------------|
| **S+** | 9 | 25.000 | 95.000 | 21.000 | **35.000** | 26.000 |
| **S** | 5 | 18.000 | 52.121 | 18.000 | **24.000** | 22.000 |
| **A** | 31 | 1.005 | 16.606 | 1.000 | 16.500 | 9.500 |
| **B** | 13 | 2.212 | 5.878 | 2.500 | 6.000 | 3.500 |
| **C** | 21 | 585 | 1.311 | 600 | 1.500 | 700 |

### Preços por Papel (R proposto — mediana)

| Papel | Qtd. | R mín. | R máx. | Mediana | Teto Mercado 254 |
|-------|------|--------|--------|---------|-----------------|
| `boss` | 21 | 5.000 | **35.000** | 25.000 | 120k–150k |
| `raid` | 12 | 1.200 | **25.000** | 15.000 | 90k–150k |
| `ataque` | 31 | 700 | **22.000** | 3.500 | 15k–150k |
| `locomocao` | 5 | 650 | 7.000 | 6.500 | 8k–42k |
| `utilitario` | 10 | 600 | 2.500 | 700 | 8k–15k |

### Distribuição de Ajuste Proposto (Δ) — v2 Jul/2026

| Símbolo | Qtd. | % |
|---------|------|---|
| = (idêntico) | 8 | 10,1% |
| ≈ (< 2% var.) | 32 | 40,5% |
| ↑ (aumento) | 30 | 38,0% |
| ↓ (redução) | **17** | **21,5%** |

> **Resumo v2:** Recalibração Jul/2026 aumenta reduções de 7 para 17 espécies — concentradas no S+ boss cluster (−63%) e S tier topo (−38% a −54%). Tier A, B e C inalterados. Hierarquia preservada: Armaedron (35k) > Indominus (28k) > Carcha (25k) > Rex (18k).

---

## Âncoras Canônicas (v2 Jul/2026)

> Âncoras recalibradas. Carcha e Rex inalterados. Armaedron e Indominus com novos valores.

| Espécie | Papel | Tier | prestige_rank | R antes | **R depois** | Δ | Justificativa |
|---------|-------|------|---------------|---------|-------------|---|---------------|
| **Armaedron** | boss | S+ | 98 | 95.000 | **35.000** | −63% | Apex — premium mas atingível em ~12 meses default |
| **Indominus Rex** | boss | S+ | 92 | 70.000 | **28.000** | −60% | Boss S+ âncora; mantém Armaedron>Indominus>Carcha |
| **Carcharodontosaurus** | raid | S+ | 88 | 25.000 | **25.000** | = | Âncora raid S+ — mantida |
| **Rex** | ataque | S | 75 | 18.000 | **18.000** | = | Âncora ataque universal — mantida |
| **Tek Strider** | boss | S+ | 85 | 35.000 | **26.000** | −26% | catalog_only — ligeiramente acima do Carcha |

---

## Espécies Ausentes do PROJETO_ECONOMIA_IDEAL

As 2 espécies presentes no catálogo mas ausentes da tabela proposta (`docs/PROJETO_ECONOMIA_IDEAL.md` §10):

| ID Catálogo | Nome | R atual | R proposto inferido | Tier | Justificativa |
|-------------|------|---------|-------------------|------|---------------|
| `sb_broodmother` | Small Broodmother | 25.151 | **25.000** | A/boss | Mesma lógica dos demais boss tier A com prestige_rank 68 |
| `sb_fire_elemental_tame` | Fire Elemental Domável | 25.151 | **25.000** | A/boss | Variante domável do Fire Elemental — mesmo blueprint tier |

> **Recomendação:** Incluir essas 2 espécies na tabela do `PROJETO_ECONOMIA_IDEAL.md` na próxima revisão.

---

## Cruzamento: Catálogo × Matriz × Market Defaults

| Fonte | Contagem | Status |
|-------|---------|--------|
| `config.json` (L1 dinos) | **79** | ✅ Referência principal |
| `blueprint_catalog_matrix.csv` | **79** | ✅ Alinhado |
| `market_species_defaults.json` | **78** | ⚠️ Faltando `abyss_moschops_abyssal` — verificar |
| `PROJETO_ECONOMIA_IDEAL.md` §10 | **77** | ⚠️ Faltando `sb_broodmother` e `sb_fire_elemental_tame` |

> **Nota sobre market_species_defaults.json:** O arquivo referenciado em `ECONOMIA_ARKLAND.md` como "55 espécies" está desatualizado — a contagem real é 78 (inclui todas as espécies Abyss, Grand Hunt e Brighamia adicionadas após a migração). Recomenda-se atualizar a menção no documento.

---

## Referências e Próximos Passos

### Para aplicar os preços propostos:
1. Atualizar `root_value` em `market_species_defaults.json` por espécie
2. Executar `tools/sync_market_species_to_shop_catalog.py` para propagar para `config.json`
3. Anunciar com 7 dias de antecedência (ver Fase 3 do plano em `PROJETO_ECONOMIA_IDEAL.md`)

### Ferramentas disponíveis:
- `tools/recalibrate_market_economy.py` — recalibra R/B e gera CSV atualizado
- `tools/sync_market_species_to_shop_catalog.py` — sincroniza defaults → config.json
- `tools/sync_abyss_shop_catalog.py` — sincroniza espécies Abyss especificamente

### Links internos:
- [PROJETO_ECONOMIA_IDEAL.md](./PROJETO_ECONOMIA_IDEAL.md) — proposta completa de economia
- [ECONOMIA_ARKLAND.md](./ECONOMIA_ARKLAND.md) — bíblia técnica do sistema atual

---

*Tabela gerada em Jul/2026 — baseada em dados reais de produção. Valores propostos são recomendações, não aplicados automaticamente.*  
*Nenhum preço em `config.json` foi alterado por este documento.*
