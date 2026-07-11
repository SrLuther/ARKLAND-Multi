# CATÁLOGO DE DINOS — ANÁLISE DE COBERTURA E PLANO DE EXPANSÃO

> ### 👉 Tabela completa com todos os dinos → [`TABELA_DINOS_COMPLETA.md`](./TABELA_DINOS_COMPLETA.md)
> **191 entradas · 98 BPs verificadas · 93 PENDENTE** · CSV: [`tools/tabela_dinos_completa.csv`](../tools/tabela_dinos_completa.csv)

---

> **Status:** Planejamento ativo — nenhum blueprint inventado neste documento  
> **Versão:** 1.1 — Jul 2026  
> **Relatório de lacunas:** [`tools/gap_report_vanilla_tameables.json`](../tools/gap_report_vanilla_tameables.json)  
> **Fontes de dados:** `plugin/CustomShop/configs/config.json` · `tools/blueprint_catalog_matrix.csv` · `plugin/arkshop_web/data/market_species_defaults.json` · `plugin/arkshop_web/data/ark_species_registry.json`  
> **Referência econômica:** [`ECONOMIA_ARKLAND.md`](./ECONOMIA_ARKLAND.md) · [`TABELA_PRECOS_DINOS.md`](./TABELA_PRECOS_DINOS.md)

---

## 1. Situação Atual (Jul 2026)

### 1.1 Contagem

| Fonte | Total |
|-------|-------|
| Entradas `Type:dino` em `config.json` | **98** (somente L1 femea — migracao Jul/2026; entradas L200 removidas) |
| Espécies únicas no catálogo (`blueprint_catalog_matrix.csv`) | **79** |
| Criaturas domesticáveis estimadas — vanilla ASE + todos os DLCs | **~160–180** |
| Criaturas de mods ativos (Abyss, Additions, Grand Hunt, etc.) | **~80+** |
| **Meta: cobertura total** | **~240–260 espécies** |
| **Gap atual (vanilla/DLC)** | **~146 espécies ausentes** |
| **Gap vanilla/DLC confirmado na amostra** | **91 espécies verificadas** |

> **O catálogo atual cobre ~33% das criaturas vanilla/DLC domesticáveis.**  
> As 79 espécies cobertas são quase todas premium/endgame; criaturas de tier C e B da progressão normal estão ausentes.

### 1.2 Breakdown do Catálogo Atual por Origem

| Origem | Espécies únicas | % do catálogo |
|--------|----------------|---------------|
| Vanilla ASE + DLC (apenas premium) | 14 | 18% |
| Mod **Abyss** | 28 | 35% |
| Mod **SmallBosses** | 20 | 25% |
| Mod **ARK Additions** | 7 | 9% |
| Mod **Grand Hunt** | 4 | 5% |
| Mod **Funny Creatures** | 3 | 4% |
| Mod **Brighamia** | 3 | 4% |
| Mod **Indominus Rex** | 2 | 3% |
| **Total** | **81\*** | 100% |

> \* 81 pela soma acima; 79 únicos no CSV (2 entradas contam como variantes combinadas).

### 1.3 Espécies Vanilla/DLC Já no Catálogo

Estas são as únicas 14 espécies vanilla/DLC atualmente presentes:

| Species Key | Nome | DLC de origem | Tier |
|-------------|------|---------------|------|
| `rex` | Rex | The Island | S |
| `giga` | Giganotosaurus | The Island | S |
| `bionicrex` | Rex Tek | The Island | S+ |
| `bionicgigant` | Giganotossauro Tek | The Island | S+ |
| `carcha` | Carcharodontosaurus | Lost Island | S+ |
| `deinonychus` | Deinonychus | Valguero | A |
| `desmodus` | Desmodus | Fjordur | A |
| `megalosaurus` | Megalosaurus | The Island | A |
| `megalosaurus_aberrant` | Megalosaurus Aberrante | Aberration | A |
| `xenomorph` | Reaper | Aberration | A |
| `xenomorphgen2` | Reaper Gen2 | Genesis 2 | A |
| `volcanorex` | Volcano Rex | Genesis 1 | A |
| `astrodelphis` | Astrodelphis | Genesis 2 | A |
| `lionfish` | Shadowmane | Genesis 2 | S |

---

## 2. Fontes por Grupo

### 2.1 Vanilla ASE + DLC — Beacon

**Bloqueio atual:** O script `tools/sync_dinos_from_beacon.py` só consegue fazer match de espécies que já estão em `market_species_defaults.json` ou `ark_species_registry.json`. Como nenhuma das ~146 criaturas vanilla ausentes tem entrada nessas fontes, o sync Beacon atual não as adicionará automaticamente.

**Solução:** Expansão das fontes em duas etapas:

| Etapa | Ação | Ferramenta |
|-------|------|------------|
| A | Adicionar as ~91 espécies ausentes ao `market_species_defaults.json` com `blueprint_path` vazio (será preenchido pelo Beacon) | Manual / script |
| B | Executar `sync_dinos_from_beacon.py` — o script fará match Beacon e preencherá blueprints + adicionará ao `config.json` | `python tools/sync_dinos_from_beacon.py` |

**Dados necessários para etapa A:** `species_key`, `display_name`, `tier`, `dino_role`, `root_value` (ver Seção 4 — Precificação).

> ⚠️ **Não inventar blueprint paths.** O campo `blueprint_path` deve ser deixado vazio ou preenchido apenas com valor confirmado do Beacon, DevKit ou ARK wiki oficial.

### 2.2 Mod Abyss — Registry Overlay

Cobertura **completa**: 28 espécies únicas já no `ark_species_registry.json` com blueprints verificados e no `config.json`.

Ferramenta: `tools/sync_abyss_shop_catalog.py`

### 2.3 Mods Ativos (ARK Additions, Grand Hunt, Funny Creatures, Brighamia, Indominus Rex, SmallBosses)

Cobertura **completa** para as espécies definidas em `market_species_defaults.json`.

Para adicionar novas espécies desses mods: adicionar entrada em `market_species_defaults.json` com `blueprint_path` verificado.

### 2.4 Outros Mods (não cobertos)

Mods ativos no servidor mas sem entrada no catálogo devem ser investigados:
- Ver ARK species registry de cada mod no Steam Workshop
- Confirmar se criaturas são cryopodable (`_Character_BP` + aceita cryo)
- Adicionar ao `ark_species_registry.json` se forem do mod Abyss ou ao `market_species_defaults.json` para demais mods

---

## 3. Plano de Expansão por Fases

### Fase 1 — Beacon Multi-pack: Vanilla/DLC de Alta Demanda (~36 espécies)

**Objetivo:** Adicionar espécies Tier A e B mais procuradas, todas com blueprint esperado no Beacon.

**Critério:** `tier` A ou B + `cryopodable: true` + demanda de jogadores comprovada.

**Espécies prioritárias (amostra):**

| Nome | Mapa origem | Tier | Papel | Motivo da prioridade |
|------|-------------|------|-------|----------------------|
| Therizinossauro | The Island | A | utilitario | Top coleta; breeding meta |
| Quetzal | The Island | A | locomocao | Plataforma voadora; muito pedido |
| Mosassauro | The Island | A | ataque | Top aquático; plataforma |
| Tusoteuthis | The Island | A | ataque | Coleta óleo profundo; único |
| Managarmr | Extinction | A | ataque | Top PvP mobility; meta |
| Velonasauro | Extinction | A | ataque | Torreta biológica; muito pedido |
| Snow Owl (Coruja da Neve) | Extinction | A | utilitario | Freeze + cura; meta PvP |
| Bloodstalker | Genesis 1 | A | locomocao | Swing unique; muito pedido |
| Magmasauro | Genesis 1 | A | ataque | Fogo + minério; meta |
| Noglin | Genesis 2 | A | ataque | Mind control; PvP meta |
| Wyvern Fogo | Scorched Earth | A | ataque | Clássico; muito pedido |
| Wyvern Relâmpago | Scorched Earth | A | ataque | Clássico; muito pedido |
| Wyvern Venenosa | Scorched Earth | A | ataque | Clássico; muito pedido |
| Karkinos | Aberration | A | utilitario | Vertical transport; Aberration |
| Fênix | Scorched Earth | A | ataque | Rara; procurada |
| Ankylosaurus | The Island | B | utilitario | Coleta metal; essencial |
| Argentavis | The Island | B | locomocao | Transporte padrão; universal |
| Doedicurus | The Island | B | utilitario | Top coleta pedra |
| Stegosaurus | The Island | B | utilitario | Coleta berries/feno |
| Tapejara | The Island | B | locomocao | PvP voador; 3 riders |
| Daeodon | The Island | B | utilitario | Cura de grupo; raid support |
| Mantis | Scorched Earth | B | utilitario | Coleta com ferramenta |
| Thylacoleo | The Island | B | ataque | Escala paredes; combate |
| Direwolf | The Island | B | ataque | Pack; neve |
| Spinossauro | The Island | B | ataque | Buff aquático; raid entry |
| Dinopithecus | Lost Island | B | ataque | Pack; muito pedido |
| Andrewsarchus | Fjordur | B | locomocao | Motocicleta; turret |
| Ravager | Aberration | B | ataque | Pack; Aberration |
| Gacha | Extinction | B | utilitario | Loot box vivo; premium |
| Maewing | Genesis 2 | B | utilitario | Amamenta criaturas |
| Amargassauro | Gen2/Lost Island | B | ataque | Espinhos + plataforma |
| Mosassauro | The Island | A | ataque | Aquático top tier |
| Megalodonte | The Island | B | ataque | Pack aquático |
| Plesiossauro | The Island | B | ataque | Aquático + plataforma |
| Basilisco | Aberration | B | ataque | Veneno; Aberration |
| Woolly Rhino | The Island | B | ataque | Charge; PvP |

**Bloqueio técnico:** Essas espécies precisam ser adicionadas ao `market_species_defaults.json` antes do sync.

**Ação concreta:**
```bash
# 1. Adicionar espécies ao market_species_defaults.json
# 2. Executar sync:
python tools/sync_dinos_from_beacon.py
```

---

### Fase 2 — Vanilla/DLC de Média Demanda (~30 espécies)

Tier B/C com demanda menor ou nicho específico:

Baryonyx, Castoroides, Direbear, Kaprosuchus, Mammoth, Allosaurus, Carnotaurus, Raptor, Stegosaurus, Triceratops, Argentavis (aberrant), Sarco, Spinossauro (aberrant), Pachyrhinosaurus, Gallimimus, Terror Bird, Sinomacrops, Fjordhawk, Gasbags, Ferox, Rock Elemental, Roll Rat, Moschops, Pelagornis, Beelzebufo, Equus, Ichthyosaurus, Manta, Megaloceros, Dilophosaur.

---

### Fase 3 — Nicho / Questões Abertas (~10 espécies)

Criaturas com mecanismo especial ou que não vão a cryo:

| Espécie | Issue |
|---------|-------|
| Besouro do Esterco (Dung Beetle) | Não aceita cryopod vanilla |
| Abelha Gigante (Giant Bee) | Hive mechanic; não cryo normalmente |
| Titanossauro | Não come; não aceita cryo |
| Liopleurodon | Apenas 30 min após domar |
| Troodon | Sacrifício para domar |
| Parasaur | Muito básico; low value |
| Lystrosaurus | XP buff; low value |
| Kairuku | Nicho |
| Mesopithecus | Nicho |
| Dimorphodon | Swarm; questão de comportamento na loja |

---

## 4. Estratégia de Precificação para Novas Entradas

### 4.1 Regra Geral

Usar `species_root_ladder.json` como referência de `root_value` (R) por papel/tier:

| Tier | Papel | R sugerido (Âmbar) |
|------|-------|-------------------|
| S+ | boss / raid | 25.000 – 95.000 |
| S | raid / ataque | 18.000 – 22.500 |
| A | ataque / locomocao | 6.500 – 16.000 |
| B | utilitario / ataque | 2.500 – 5.000 |
| C | utilitario / locomocao | 600 – 1.500 |

### 4.2 Fórmula de Mercado P2P (referência)

```
Mercado_254 = min(R + B × Q^γ, 150.000)
```
onde `γ = 0.82`, `B = premium_budget`, `Q` = índice de qualidade do dino anunciado.

### 4.3 Para o Catálogo (loja estática)

A loja CustomShop usa apenas o Nível 1 (`Price = R`). O modelo floor_quality se aplica ao Mercado P2P.

**Regra prática:**
- Dinos novos entram como `Level: 200` (padrão Comércio) ou `Level: 1` (se fêmea)
- `Price = root_value` estimado pelo tier/papel acima
- `Category = "Comércio"` (padrão)
- `ForceTame: true`, `Neutered: false`

### 4.4 Não aplicar preços em massa

> ⚠️ Não aplicar centenas de entradas ao `config.json` sem blueprints verificados.  
> O fluxo correto é: **documentar → adicionar ao registry/defaults → sync via Beacon → validar no servidor teste**.

---

## 5. Relação com Beacon e /bp scan

### 5.1 Beacon

O Beacon contém os blueprints de todas as criaturas vanilla ASE (incluindo DLCs na mesma instalação). O campo `path` do cache Beacon é a única fonte confiável de blueprint path para vanilla.

**Limitações:**
- Mods não estão no Beacon (Abyss, ARK Additions, etc.)
- Só contém criaturas do pack instalado no servidor mestre que sincronizou

**Para sincronizar o Beacon:**
1. Abrir Beacon no Server Manager
2. Garantir que o cache está atualizado (`beacon_blueprints_cache.json`)
3. Executar `python tools/sync_dinos_from_beacon.py`

### 5.2 /bp scan (blueprint scan)

O `/bp scan` (dinolab-blueprint-scan) varre os blueprints carregados no servidor em tempo real. É a fonte mais precisa para mods ativos no servidor.

**Relação com o catálogo:**
- Blueprints confirmados pelo /bp scan podem ser adicionados diretamente ao `market_species_defaults.json` ou `ark_species_registry.json`
- Ver [`docs/DINO_LAB_SPEC.md`](./DINO_LAB_SPEC.md) para especificação do scan

---

## 6. Perguntas em Aberto (Decisão do Admin)

| # | Questão | Impacto |
|---|---------|---------|
| 1 | Criaturas não-cryopodable devem ser excluídas do catálogo? | Dung Beetle, Giant Bee, Titanosaur, Liopleurodon |
| 2 | Variantes aberrant e X-creatures listadas separado ou agrupadas? | +20–30 entradas se separado |
| 3 | Outros TEK variants além de BionicRex/BionicGigant? | Tek Parasaur, Tek Raptor, Tek Stego — baixa demanda |
| 4 | Política Macho vs Fêmea para novos dinos? | Manter o padrão atual (ambos se breeding-relevante) |
| 5 | Wyverns — spawn com blueprint de adult ou via ovo? | Afeta como entram na loja |
| 6 | Bosses de mods adicionais (além SmallBosses) a adicionar? | Depende de mods futuros |
| 7 | Criaturas de mods não mapeados no servidor — quais mods estão ativos? | Necessário para Fase 3+ |

---

## 7. Próximas Ações Concretas

### Imediato (sem risco)
- [ ] Revisar e aprovar lista de Fase 1 (~36 espécies)
- [ ] Adicionar entradas de Fase 1 ao `market_species_defaults.json` (blueprint_path vazio)
- [ ] Executar `sync_dinos_from_beacon.py` em modo dry-run (adicionar flag `--dry-run` ao script)

### Curto prazo
- [ ] Verificar cache Beacon atualizado para todas as criaturas vanilla/DLC
- [ ] Validar blueprints retornados pelo sync em servidor de teste
- [ ] Adicionar espécies confirmadas ao catálogo de produção

### Médio prazo
- [ ] Fase 2: espécies B/C restantes após validar pipeline da Fase 1
- [ ] Mapear mods adicionais ativos no servidor e criaturas domesticáveis
- [ ] Resolver questões abertas (Seção 6)

---

## 8. Inventário dos 6 Mods de Criaturas (2026-07-10)

> Auditoria completa realizada com coleta de spawn codes oficiais do Steam Workshop.  
> Fonte de blueprints: spawn codes discussion + `config.json` em produção.  
> Inventário completo: [`tools/mod_creatures_bp_inventory.json`](../tools/mod_creatures_bp_inventory.json)

### MOD 1 — BigAL's Collection (Meraxes) `2879943314`

| Criatura | Catalog ID | Blueprint Path | Status |
|----------|-----------|----------------|--------|
| Meraxes | `meraxes_femea` | `/Game/Mods/Meraxes/Dino/Meraxes_Character_BP.Meraxes_Character_BP` | ✅ Adicionado |
| Meraxes Scorched | `meraxes_scorched_femea` | `.../SE/ScorchedMeraxes_Character_BP.ScorchedMeraxes_Character_BP` | ✅ Adicionado |
| Meraxes Rockwell | `meraxes_rockwell_femea` | `.../Rockwell/RockwellMeraxes_Character_BP.RockwellMeraxes_Character_BP` | ✅ Adicionado |
| Meraxes X-Snow | `meraxes_snow_femea` | `.../X-Snow/SnowMeraxes_Character_BP.SnowMeraxes_Character_BP` | ✅ Adicionado |

**Resumo:** 4 encontradas / 0 já no catálogo / **4 adicionadas** / 0 pendentes

---

### MOD 2 — ARK Additions: The Collection `1522327484`

| Criatura | Catalog ID | Status |
|----------|-----------|--------|
| Acrocanthosaurus (F) | `acrocanto_femea` | ✅ Já presente |
| Archelon | `archelon` | ✅ Já presente |
| Brachiosaurus | `brachio` | ✅ Já presente |
| Concavenator | `concavenator` | ✅ Já presente |
| Cryolophosaurus | `cryolophosaurus` | ✅ Já presente |
| Deinosuchus | `deinosuchus` | ✅ Já presente |
| Xiphactinus | `xiphactinus` | ✅ Já presente |

**Resumo:** 7 encontradas / **7 já no catálogo** / 0 adicionadas / 0 pendentes

---

### MOD 3 — Additional Creatures: Grand Hunt `2110243671`

| Criatura | Catalog ID | Status |
|----------|-----------|--------|
| Armaedron | `armaedron` | ✅ Já presente |
| Diru-Ya-Ku | `diru_ya_ku` | ✅ Já presente |
| Kutsu-Ya-Ku | `kutsu_ya_ku` | ✅ Já presente |
| Puretotokage | `puretotokage` | ✅ Já presente |
| Lukastiblos | — | ⚠️ Pendente — sem BP path verificado |
| Emalroth | — | ⚠️ Pendente — sem BP path verificado |

> **Nota:** Mod abandonado (autor Shadlos confirmou encerramento em Apr/2025). Lukastiblos e Emalroth são mencionados na descrição mas nunca receberam spawn codes públicos — possivelmente nunca lançados.

**Resumo:** 6 encontradas / **4 já no catálogo** / 0 adicionadas / **2 pendentes sem path**

---

### MOD 4 — Brighamia Creatures `3550298419`

| Criatura | Catalog ID | Blueprint (resumido) | Status |
|----------|-----------|----------------------|--------|
| Dread Wyvern | `dread_wyvern` | `.../DreadWyvern/Wyvern_Character_BP_Dread` | ✅ Já presente |
| Ancient Wyvern | `ancient_wyvern` | `.../AncientWyvern/Wyvern_Character_BP_Ancient` | ✅ Já presente |
| Shimosaur | `shimosaur` | `.../Shimosaur/Shimosaur_Character_BP` | ✅ Já presente |
| Titan Wyvern | `brighamia_titan_wyvern` | `.../TitanWyvern/Wyvern_Character_BP_Titan` | ✅ Adicionado |
| Gold Fire Wyvern (NoEgg) | `brighamia_wyvern_gold` | `.../NoEggWyv/Wyvern_Character_BP_Fire_NoEgg` | ✅ Adicionado |
| Red Lightning Wyvern (NoEgg) | `brighamia_wyvern_red` | `.../NoEggWyv/Wyvern_Character_BP_Lightning_NoEgg` | ✅ Adicionado |
| B Quetzal | `brighamia_b_quetzal` | `.../BuffedQuetz/B_Quetz_Character_BP` | ✅ Adicionado |
| B Liopleurodon | `brighamia_b_liopleurodon` | `.../B-Liopleurodon/B_Liopleurodon_Character_BP` | ✅ Adicionado |
| B Ammonite | `brighamia_b_ammonite` | `.../B_Ammonite/B_Ammonite_Character` | ✅ Adicionado |
| B Compy | `brighamia_b_compy` | `.../YipeeCompy/Compy_Character_BP_YIpee` | ✅ Adicionado |
| Jagged Rock Golem | `brighamia_jagged_golem` | `.../JaggedRockGolem/JaggedRockGolem_Character_BP` | ✅ Adicionado |
| Ancient Rock Golem | `brighamia_ancient_golem` | `.../JaggedRockGolem/Farum/JaggedRockGolem_Character_BP_Farum` | ✅ Adicionado |
| Possessed Onyc | `brighamia_poss_onyc` | `.../MushroomCreatures/Bat/Bat_Character_BP_Mush` | ✅ Adicionado |
| Possessed Karkinos | `brighamia_poss_karkinos` | `.../MushroomCreatures/Crab/Crabulon_Character_BP_Mush` | ✅ Adicionado |
| Possessed Pulmonoscorpius | `brighamia_poss_scorpion` | `.../MushroomCreatures/Scorp/Scorpion_Character_BP_Aberrant_Mush` | ✅ Adicionado |
| Possessed Achatina | `brighamia_poss_achatina` | `.../MushroomCreatures/Snail/Achatina_Character_BP_Aberrant_Mush` | ✅ Adicionado |
| Possessed Araneo | `brighamia_poss_araneo` | `.../MushroomCreatures/Spider/SpiderS_Character_BP_Aberrant_Mush` | ✅ Adicionado |
| Possessed Trilobite | `brighamia_poss_trilobite` | `.../MushroomCreatures/Trilo/Trilobite_Character_Aberrant_Mush` | ✅ Adicionado |

**Resumo:** 18 encontradas / 3 já no catálogo / **15 adicionadas** / 0 pendentes

---

### MOD 5 — Small Bosses `2380466974`

Cobertura **completa** — 20 criaturas todas já no catálogo:

Small Broodmother · Crystal Wyvern (Blood/Ember/Queen/Tropical) · Small Cyclops · Small Desert Titan · Small Dodoreaper · Small DodoRex · Small Dodowyvern · Small Dragon · Volcano Small Dragon · Small Drake (Fire) · Small Hippocampus · Small Hydra · Small Manticore · Small Megapithecus · Small Moeder · Fire Elemental · Fire Elemental (Domável)

**Resumo:** 20 encontradas / **20 já no catálogo** / 0 adicionadas / 0 pendentes

---

### MOD 6 — Moro's Indomitable Duo `2932656301`

| Criatura | Catalog ID | Status |
|----------|-----------|--------|
| Indominus Rex (F) | `indominus_femea` | ✅ Já presente |
| IndoRaptor (F) | `indoraptor_femea` | ✅ Já presente |

**Resumo:** 2 encontradas / **2 já no catálogo** / 0 adicionadas / 0 pendentes

---

### Totais desta auditoria

| Mod | Encontradas | Já no catálogo | Adicionadas | Pendentes s/ path |
|-----|-------------|---------------|-------------|-------------------|
| BigAL's (Meraxes) | 4 | 0 | **4** | 0 |
| ARK Additions | 7 | 7 | 0 | 0 |
| Grand Hunt | 6 | 4 | 0 | **2** |
| Brighamia Creatures | 18 | 3 | **15** | 0 |
| Small Bosses | 20 | 20 | 0 | 0 |
| Moro's Indomitable Duo | 2 | 2 | 0 | 0 |
| **TOTAL** | **57** | **36** | **19** | **2** |

**Arquivos modificados:**
- `plugin/CustomShop/configs/config.json` — +19 entradas dino (451 items total)
- `plugin/arkshop_web/data/mod_catalog_verified.json` — +19 entries verificadas
- `tools/mod_creatures_bp_inventory.json` — inventário completo criado

---

## 9. Histórico

| Data | Evento |
|------|--------|
| Jul 2026 | Catálogo atual: 79 espécies únicas, foco em premium/endgame |
| Jul 2026 | Este documento criado — análise de lacunas, meta = cobertura total |
| Jul 2026 | Auditoria dos 6 mods: +19 criaturas adicionadas (Meraxes x4, Brighamia x15) |
| — | Fase 1 a ser executada (aguardando aprovação admin) |
