# Projeto ARKLAND Multi — Plano Mestre (TEK v2 + ArkUtils)

> **Status:** Em implementação — Fases 0 e 1 iniciadas (piloto TEK).  
> **Última atualização:** 2025-06-09  
> **Repositório alvo:** `arkland-multi`  
> **Referências externas analisadas:**
> - ASM original: `C:\Users\Ciano\Documents\_asm_src`
> - ARKLAND SM: `C:\Users\Ciano\Documents\ARKLAND SM`
> - ArkUtils (SpawnExact): `C:\Users\Ciano\Documents\arkutils-website-main`

---

## 1. Visão geral

Unificar em **um único projeto** (`arkland-multi`) três frentes de trabalho:

| Frente | Objetivo |
|--------|----------|
| **A — TEK Completo** | Layout confortável, traduções PT+EN, paridade ASM/SM |
| **B — SpawnExact (ArkUtils)** | Gerador admin de dinos (stats, cores, imprint) + uso na loja |
| **C — Integração operacional** | RCON, CustomShop, presets reutilizáveis |

**Resultado final esperado:** administrador configura servidor, gera comando de spawn preciso, entrega via RCON ou cadastra como material de kit na CustomShop — tudo dentro do app TEK, com a mesma identidade visual.

---

## 2. Decisões já confirmadas

| Tema | Decisão |
|------|---------|
| Layout TEK | **Híbrido D** — formulário aprimorado + cards duplos em seções longas |
| Multiplicadores | Entry + **slider condicional** (≥ 1200px) |
| Navegação TEK | **7 grupos** com separadores (não lista plana de 24) |
| Entrega UI/i18n | **Somente TEK** — interface definitiva para o usuário final |
| Interface primitiva | Código legado interno (`tab_general_prim`, `tab_advanced_prim`, etc.) — mantido apenas para manutenibilidade do TEK, sem UI acessível ao usuário, **não recebe novas funcionalidades** |
| Inspiração SM | Cards, busca, modified+reset, accordion per-level, tooltips |
| ArkUtils | Portar lógica **SpawnExactDino** para Python/CustomTkinter (não embutir Svelte) |
| Commits/releases | Somente quando solicitado explicitamente |
| **Meta catálogo de dinos** | **79 espécies (Jul 2026) é subconjunto inicial** — meta = todos os domesticáveis vanilla ASE+DLC+mods (~240–260). Ver [`docs/CATALOGO_DINOS_COMPLETO.md`](./CATALOGO_DINOS_COMPLETO.md) |

### Pendente de confirmação neste documento

- [ ] Incluir busca global na nav (recomendado: **sim**)
- [ ] Incluir indicador modified + reset (recomendado: **sim**)
- [ ] Per-level em accordion (recomendado: **sim**)
- [ ] Fases 3–5 (CLI ASM + editores + extensões SM)
- [ ] Fase 6 (ArkUtils) — prioridade após piloto TEK ou em paralelo?

---

## 3. Análise — ArkUtils (`arkutils-website-main`)

### 3.1 O que é

Site **SvelteKit** (Apache 2.0) com utilitários para ARK ASE/ASA. A ferramenta relevante é:

**`/tools/spawnexact`** — Gerador do comando admin `SpawnExactDino`.

### 3.2 Como funciona (lógica central)

Arquivo: `src/routes/(pages)/tools/spawnexact/+page.svelte`

O comando é montado reativamente:

```
cheat SpawnExactDino "Blueprint'<species_path>'" ""
  0 <sumWild> <sumTamed>
  "<wild_stats>,0" "<tamed_stats>,0"
  "Generated" 0 0 "" ""
  <imprintName_json> <imprintID_hex> <imprint_float>
  "<colors_or_empty_if_wild>"
  0 0 0 20 20
```

**Entradas do usuário:**

| Campo | Detalhe |
|-------|---------|
| Espécie | Blueprint path (ex: `/Game/PrimalEarth/Dinos/...`) |
| Mod | Lista de mods via Obelisk ASB |
| Stats Wild | 7 valores: Health, Stamina, Oxygen, Food, Weight, Melee, Speed (0–255) |
| Stats Tamed | Mesmos 7 stats |
| Cores | 6 regiões de cor OU wild colors (string vazia) |
| Imprint | 0.0–1.0 + nome do imprinter + Ark ID (hex, máx 32 chars) |
| Atalhos | Presets wild/tamed: 0, 1, 35, 60, 100, 254, 255 |

### 3.3 Dados externos (Obelisk)

ArkUtils **não embute** a lista de dinos — busca online:

| Recurso | URL base |
|---------|----------|
| Manifest | `https://raw.githubusercontent.com/arkutils/Obelisk/master/data` |
| ASB (species) | `.../asb/values.json` (oficial) + `{modid}-{tag}.json` (mods) |
| Cores | `asb.ts` → definições RGBA por mod |

Módulos-chave:
- `src/lib/obelisk/core.ts` — fetch manifest
- `src/lib/obelisk/asb.ts` — espécies, cores, multiplicadores
- `src/lib/obelisk/types.ts` — tipos

### 3.4 Outras ferramentas no repo (fora do escopo imediato)

| Ferramenta | Uso potencial futuro |
|------------|---------------------|
| `colorids` | Referência de IDs de cor para loja |
| `wildstats` | Calculadora de stats selvagens por nível |
| `boss` | Info de bosses (não prioritário) |
| `incubator` / `reapercalculator` | Breeding (futuro) |

### 3.5 Situação atual no ARKLAND Multi

| Item | Estado |
|------|--------|
| CustomShop kits com dino | Campo manual: Blueprint + Level + Gender (`customshop_panel.py`) |
| RCON cheatsheet | Entrada simplificada: `spawnexactdino <Blueprint> {level} 0 0` |
| SpawnExact completo | **Não existe** |
| Lista de espécies/mods | **Não existe** (depende de digitar blueprint) |
| Integração Obelisk | **Não existe** |

**Gap:** a loja e o admin só suportam spawn **simplificado**; ArkUtils gera o comando **completo** necessário para dinos com stats/cores customizados para venda.

---

## 4. Proposta de integração — ArkUtils no app

### 4.1 Abordagem técnica (recomendada)

**Não** embutir o site Svelte no app. **Portar** para Python:

```
src/
  spawn_tools/
    __init__.py
    spawn_exact.py          # build_spawn_exact_command() — porte da fórmula Svelte
    obelisk_client.py       # fetch + cache manifest/ASB (opcional offline)
    species_cache/          # JSON cache local (mods do servidor)
    color_defs.py           # cores ASE (cache Obelisk ou embutido mínimo)
  pages/
    spawn_exact_panel.py    # UI CustomTkinter (TEK)
  asm_ui/
    asm_spawn_panel.py      # Variante no contexto servidor TEK (opcional alias)
```

**Licença:** Apache 2.0 — manter atribuição em `spawn_exact.py` (baseado em arkutils-website).

### 4.2 UI proposta — painel "Gerador de Dino"

Nova seção no app (acesso sugerido):

- Menu lateral TEK: grupo **Ferramentas** ou **Admin**
- Atalho na aba **CustomShop** → "Gerar spawn para kit"
- Atalho no **Console RCON** → "Inserir comando gerado"

**Layout (inspirado SM + ArkUtils, widgets da Fase 0):**

```
┌─ Espécie ─────────────────────────────────────────┐
│  [Mod: Oficial ▼]  [Espécie: Rex ▼]  [🔍 busca]   │
├─ Stats ───────────────┬─ Cores ───────────────────┤
│  Wild | Tamed (7)     │  [ ] Cores selvagens       │
│  atalhos 0/35/255...  │  Região 0–5 + preview     │
├─ Imprint ─────────────┴─ Preview comando ──────────┤
│  % | Nome | Ark ID    │  [copiar] [enviar RCON]   │
│                       │  [→ adicionar ao kit]     │
└───────────────────────────────────────────────────┘
```

### 4.3 Fluxos de uso

#### Fluxo A — Admin spawn imediato
1. Seleciona servidor TEK ativo
2. Configura dino no gerador
3. **Enviar RCON** → `asm_player_list` / console RCON existente
4. Opcional: salvar como preset local

#### Fluxo B — Material para CustomShop
1. Gera comando SpawnExact completo
2. **Adicionar ao kit** → preenche entrada tipo `dino` em `customshop_panel.py`:
   - `Blueprint` = path da espécie
   - Campos estendidos: stats, cores, imprint (novo schema no config.json se plugin suportar)
   - Ou: campo `SpawnCommand` raw se CustomShop aceitar comando completo
3. Sincroniza plugin nos servidores

> **Nota:** validar com `CustomShop` se entrega usa `SpawnExactDino` completo ou só blueprint+nível. Para **dinos com cores exatas via admin web**, ver [`docs/DINO_LAB_SPEC.md`](DINO_LAB_SPEC.md) (canônico; legado técnico: [`dino_custom_colors_delivery_spec.md`](dino_custom_colors_delivery_spec.md)) — plugin **`CustomDinoDeliver`** + área **Dino Lab** (separado do CustomShop). Para **mercado genético / certificados cryopod**, ver [`docs/GENOMA_ARKLAND_SPEC.md`](GENOMA_ARKLAND_SPEC.md).

#### Fluxo C — Preset / biblioteca
- Salvar dinos frequentes (nome, comando, thumbnail cor)
- Exportar/importar JSON para equipe
- Futuro: vincular a produtos da loja web

### 4.4 Dados Obelisk — estratégia offline

| Opção | Prós | Contras |
|-------|------|---------|
| **A — Online sempre** | Lista sempre atualizada | Requer internet |
| **B — Cache local + refresh** | Funciona offline após 1º download | Manutenção de cache |
| **C — Só mods do servidor** | Lista enxuta, relevante | Setup inicial |

**Recomendado:** **B + C** — ao abrir painel, carregar `active_mods` do `AsmServerConfig` e buscar ASB só desses mods + oficial; cache em `%APPDATA%/ARKLAND-ServerManager/obelisk_cache/`.

### 4.5 Escopo ASE vs ASA

ArkUtils suporta ASE e ASA. **ARKLAND Multi é ASE** — implementar **somente ASE** na Fase 6; filtrar mods ASA do manifest.

---

## 5. Projeto TEK v2 — Fases (frente A)

### Fase 0 — Infraestrutura UI + i18n (2–3 dias)

**Novos módulos:**
- `src/ui/server_field_labels.py` — catálogo PT + EN + hint + tipo + min/max
- `src/ui/server_field_widgets.py` — DualLabel, FieldCard, NumericCard, ToggleCard, FieldTooltip, ModifiedBadge
- `src/ui/responsive.py` — breakpoint 1200px
- `scripts/check_field_labels.py` — cobertura 100%

**Fontes:** `asm_ini_manager.INI_MAP`, `asm_server_panel.py`, ASM `ServerProfile.cs`, SM `ASEConfigEditor.tsx`

---

### Fase 1 — Piloto visual + nav (3–4 dias) — **GATE de aprovação**

**TEK piloto:** Jogador, Dino, Reprodução  
**Clássico piloto:** `tab_game_prim.py`

**Inclui:**
- Nav agrupada (7 grupos, 240px)
- Cards 2 colunas, dual-label, tooltips
- Slider condicional, checkboxes 2 colunas
- Accordion per-level (substitui grade 12×N)
- Busca global (piloto nas 3 seções)
- Modified + reset
- `minsize` 1100×700

**Critério:** OK explícito do usuário antes da Fase 2.

---

### Fase 2 — Layout + traduções TEK completo (4–5 dias)

- 21 seções restantes com mesmo padrão
- Cards duplos: Regras, Meio Ambiente (se densas)
- Abas internas Config | Stats onde houver per-level
- Header com menu `⋯` em telas estreitas
- `check_field_labels.py` → 0 pendências

---

### Fase 3 — Paridade ASM: flags CLI (3–4 dias)

Portar para `AsmServerConfig` + `build_launch_args()` o que já existe em `server_config.py`:

- BattlEye, VAC, anti-speedhack, raw sockets, net threading
- Force respawn, auto-destroy structures, no fish loot
- Flyer explosives, crate spawns on structures
- Admin logs, web alarm, notify admin commands
- Performance flags (dx10, sm4, lowmemory, nomansky, ansel, nodinos, etc.)

UI: seção **Administração → Avançado (linha de comando)**

---

### Fase 4 — Editores agregados ASM (4–5 dias)

| Editor | ASM | SM |
|--------|-----|-----|
| HarvestResourceItemAmountClassMultipliers | ✅ | ✅ |
| PerDinoClassResistanceMultipliers | ✅ (lista maior) | ✅ |
| DinoClassDamageMultipliers | ✅ | — |
| DinoSpawnWeightMultipliers | ✅ | — |
| PreventDinoTameClassNames | ✅ | — |

Melhorar editores raw existentes (crafting, stack, spawner, supply crate, engrams).

---

### Fase 5 — Extensões SM + clássico + polimento (3–4 dias, opcional)

Campos SM sem equivalente ASM original:
- `ItemStackSizeMultiplier`, `BabyImprintAmountMultiplier`, `MaxDifficulty`
- `MaxTributeDinos/Items/Characters`, `EnableCreativeMode`
- Mutagen, filtros bad-word, crossplay/Vivox, mapas específicos

Alinhar `tab_general_prim.py`, `tab_advanced_prim.py` aos novos widgets.

---

## 6. Fase 6 — ArkUtils SpawnExact (3–5 dias)

**Dependência:** Fase 0 (widgets) recomendada; pode iniciar em paralelo após Fase 0.

| Etapa | Entrega |
|-------|---------|
| 6.1 | `spawn_exact.py` — fórmula do comando + testes unitários |
| 6.2 | `obelisk_client.py` — fetch manifest, cache, lista espécies por mod |
| 6.3 | `spawn_exact_panel.py` — UI completa (espécie, stats, cores, imprint) |
| 6.4 | Integração RCON — botão "Executar no servidor" |
| 6.5 | Integração CustomShop — "Adicionar ao kit" / export preset |
| 6.6 | Presets locais + histórico recente |

**Critérios de aceite:**
- Comando gerado **byte-a-byte igual** ao ArkUtils para mesmos inputs
- Lista de espécies: oficial + mods do servidor ativo
- Copiar e enviar RCON funcionando
- Pelo menos um fluxo de kit CustomShop documentado e testado

---

## 7. Navegação TEK unificada (pós-implementação)

```
Servidor       → Administração, Auto, Detalhes, Arquivos
Regras         → Regras, Transferências, Chat, HUD
Gameplay       → Jogador, Dino, Reprodução, Meio Ambiente
Construção     → Estruturas, Engramas
Substituições  → Crafting, Stack, Spawner, Supply Crate, Impedir Transfer.
INI            → Custom GUS, Custom Game, PGM
Integrações    → Discord, Mods, CustomShop
Ferramentas    → 🦕 Gerador SpawnExact, Console RCON, Jogadores  ← NOVO
```

---

## 8. Arquitetura unificada

```
server_field_labels.py ──┬── asm_server_panel.py (TEK config)
                         ├── tab_*_prim.py (clássico)
                         └── spawn_exact_panel.py (labels PT/EN)

spawn_exact.py ──────────┬── spawn_exact_panel.py
                         ├── customshop_panel.py (kits)
                         └── rcon_client.py (execução)

asm_server_config.py ────┬── asm_ini_manager.py (INI + launch args)
                         └── obelisk_client.py (mods → espécies)
```

---

## 9. Cronograma consolidado

| Fase | Conteúdo | Dias | Acumulado |
|------|----------|------|-----------|
| 0 | Infraestrutura UI/i18n | 2–3 | 3 |
| 1 | Piloto TEK + nav (**gate**) | 3–4 | 7 |
| 2 | TEK layout+i18n completo | 4–5 | 12 |
| 3 | Flags CLI ASM | 3–4 | 16 |
| 4 | Editores agregados | 4–5 | 21 |
| 5 | Extensões SM (opcional) | 3–4 | 25 |
| 6 | ArkUtils SpawnExact | 3–5 | **~30 dias** |

Fases 6.1–6.3 podem começar após Fase 0 se desejar priorizar ferramenta admin/loja.

---

## 10. Análise comparativa resumida (referência)

### INI gameplay (ASM ∩ SM)
- **~99% coberto** no TEK via `AsmServerConfig` — manter e validar

### Lacunas TEK vs ASM ∩ SM
- **Flags CLI** (~25) — clássico tem, TEK não → Fase 3
- **Editores agregados** — ASM tem, TEK só raw → Fase 4
- **Extensões SM** — só SM → Fase 5 opcional

### Lacunas vs ArkUtils
- **SpawnExact completo** — Fase 6
- **Obelisk species DB** — Fase 6
- **CustomShop** — spawn simplificado hoje → estender na 6.5

---

## 11. Riscos

| Risco | Mitigação |
|-------|-----------|
| Regressão INI | Testes round-trip GUS/Game por seção |
| SessionName na CLI | Manter regra: só INI, nunca `?SessionName=` |
| Obelisk offline | Cache local obrigatório |
| CustomShop não aceita spawn full | Investigar plugin na 6.5 antes de UI kit |
| Escopo 30 dias | Gates na Fase 1; Fase 5 opcional |
| Apache 2.0 ArkUtils | Atribuição no código portado |

---

## 12. Fora de escopo

- Reescrever app em React/Tauri (SM)
- Embedar site Svelte no Python
- Ferramentas ArkUtils não relacionadas (boss, incubator, etc.) — salvo pedido futuro
- ASA / mapas `_WP`
- Releases automáticos

---

## 13. Como aprovar

Responder com uma das opções:

| Opção | Significado |
|-------|-------------|
| **A** | Aprovado completo — começar Fase 0 |
| **B** | Aprovado Fases 0–2 (UI+i18n), depois 3–6 |
| **C** | Aprovado Fases 0 + 6 primeiro (SpawnExact prioritário) |
| **D** | Aprovado com ajustes: _(descrever)_ |

### Checklist de ajustes opcionais

- [ ] Nomes dos 7 grupos da nav
- [ ] Breakpoint 1200 vs 1280px
- [ ] Prioridade: SpawnExact antes ou depois do piloto visual?
- [ ] Incluir Fase 5 (extensões SM)?
- [ ] Onde colocar painel SpawnExact (menu Ferramentas vs dentro da Loja)

---

## 14. Referências de arquivos

### arkland-multi (alterações previstas)
- `src/asm_ui/asm_server_panel.py`
- `src/asm_engine/asm_server_config.py`
- `src/asm_engine/asm_ini_manager.py`
- `src/ui/server_field_labels.py` *(novo)*
- `src/ui/server_field_widgets.py` *(novo)*
- `src/spawn_tools/spawn_exact.py` *(novo)*
- `src/pages/spawn_exact_panel.py` *(novo)*
- `src/pages/customshop_panel.py` *(integração)*

### ArkUtils (leitura / porte)
- `src/routes/(pages)/tools/spawnexact/+page.svelte` — fórmula do comando
- `src/lib/obelisk/asb.ts` — dados de espécies
- `src/lib/StatEntry.svelte` — 7 stats
- `src/lib/ColorRegions.svelte` — 6 regiões de cor
- `LICENSE` — Apache 2.0

### ASM / SM (referência layout e campos)
- `_asm_src/.../ServerProfile.cs`
- `ARKLAND SM/src/ase/pages/ASEConfigEditor.tsx`
- `ARKLAND SM/src/components/settings/SettingsSlider.tsx`

### Web Store (ecossistema — fora do escopo TEK)

- [`docs/SORTEIO_DOACOES_SPEC.md`](SORTEIO_DOACOES_SPEC.md) — Sorteio promocional vinculado a doações PIX/cartão: R$5 = 1 número (100–999), auto-encadeamento pós-sorteio, prêmio em Âmbares com rollover, trilha de auditoria pública (discussão).

### Portal e Tribo

- [`docs/PROJETO_AREA_TRIBO.md`](PROJETO_AREA_TRIBO.md) — Área de Tribo na Minha Área: **modelo "uma tribo por mapa"** (princípio central de design), painel agregado com abas independentes por servidor, logs espelhados e sync automática de membros por mapa (MVP ~8–11 dias). **§17** documenta a política Tribo Principal + Fobs: definições, cenários de membership, 3 opções de design (Cluster Group / Naming Convention / Plugin tipo), implicações de UI, Cluster View de logs — ✅ decisões administrativas registradas em §17.7 (10/07/2026): fob sem split, restrição same-map, visibilidade tribe-only, nomenclatura livre, vínculo exige aprovação do owner principal. **§18** resume os princípios de repartição de ganhos do mercado (ver arquivo dedicado abaixo). **§19** especifica o Regulamento Interno da Tribo: conteúdo autoral do owner, hierarquia principal + adendos de fob, visibilidade, versionamento, moderação e modelo de dados.

- [`docs/TRIBO_REPARTICAO_MERCADO.md`](TRIBO_REPARTICAO_MERCADO.md) — **§18 Repartição de ganhos do mercado:** ✅ decisões administrativas registradas em 10/07/2026. Regra relativa de floor (gap mínimo de 10 p.p. acima do próximo membro, sem piso fixo), cooldown 48h somente em alterações, opt-out imediato com reentrada em 45h + aprovação do owner, mínimo de venda 1.000 Âmbares, limite de 10 membros, split exclusivo da tribo principal (fobs sem split), sem vínculo com encomendas. Auditoria por venda, 25 edge cases, fases MVP.

### Economia — Documentação Completa

- [`docs/ECONOMIA_ARKLAND.md`](ECONOMIA_ARKLAND.md) — Bíblia completa da economia: moeda Âmbar, catálogo, mercado P2P (floor_quality), encomendas, kits, licenças, ganhos, ferramentas admin.
- [`docs/TABELA_PRECOS_DINOS.md`](TABELA_PRECOS_DINOS.md) — **Tabela completa de 79 dinos:** preço atual vs proposto, mercado 254pts, encomenda máxima, âncoras e ajustes do rebalanceamento.
- [`docs/PROJETO_ECONOMIA_IDEAL.md`](PROJETO_ECONOMIA_IDEAL.md) — Projeto de economia ideal: princípios, tabela R/B proposta, taxa P2P, ajuste de parâmetros, sumidouros, plano de migração faseado.
- [`docs/LICENCAS_PRECOS_PROPOSTA.md`](LICENCAS_PRECOS_PROPOSTA.md) — **✅ Direção aprovada — 12 tiers de licença** (Delta→Exótico) baseada no mod ItensAlfa: preços **6k–230k Âmbar** *(v3.0 — escada de subscrição TEK; Gama 50k / Beta 75k / Alfa 100k / Exótico 230k)*, bônus /30min (30→225 total), acesso a armadura/armas/selas TEK por tier (180→23.500 pts armor). Implementação pendente.

---

*Documento vivo — atualizar conforme aprovações e decisões do usuário.*
