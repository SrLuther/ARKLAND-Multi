# Fila de regeneração — ícones AI de espécies

Workflow **um por vez**: usuário envia referência → agente regenera → usuário aprova → próximo.

## Causa das duplicatas ("duas imagens")

| Causa | Exemplo | Correção |
|-------|---------|----------|
| **Aliases de `species_key`** no registro | `beaver` + `castoroides`, `doed` + `doedicurus` | Ícone canônico único; aliases apontam para o mesmo `.webp` |
| **Variantes de catálogo** (`_femea`, aberrant) | `deinonychus` + `deinonychus_femea`, `giga` + `gigant` | Regenerar o canônico; copiar/sincronizar para variantes |
| **SVG legado + WebP AI** no disco | `icons/castoroides.svg` + `generated/castoroides.webp` | Manifesto (`species_icons_manifest.json`) prioriza WebP — SVG é fallback procedural |
| **Demos de referência** | `demo/mosasaurus.png`, `demo/giganotosaurus.png` | Não servidos na loja; só guias de moldura (não usar como anatomia) |

Aliases `beaver`/`doed` já foram consolidados para `castoroides`/`doedicurus` (arquivos duplicados removidos).

## Fila (reportado pelo usuário)

| # | species_key | Nota do usuário | Duplicata? | Status |
|---|-------------|-----------------|------------|--------|
| 1 | `mosasaurus` | Muito magro / anatomia errada | demo + generated | **pending** — sugerido para começar |
| 2 | `astrocetus` | Ícone ruim | — | **awaiting_review** (ref DodoDex) |
| 3 | `bloodstalker` | Ícone ruim | — | **awaiting_review** (ref DodoDex) |
| 4 | `castoroides` | Duas imagens | alias `beaver` (fixado) | **awaiting_review** (ref DodoDex) |
| 5 | `crystalwyvern` | Ícone ruim | — | pending |
| 6 | `deinonychus` | Duas imagens | `deinonychus_femea` | **awaiting_review** (ref DodoDex) |
| 7 | `doedicurus` | Duas imagens | alias `doed` (fixado) | **awaiting_review** (ref DodoDex) |
| 8 | `gacha` | Ícone ruim | — | **awaiting_review** (ref DodoDex) |
| 9 | `gasbags` | Ícone ruim | — | **awaiting_review** (ref DodoDex) |
| 10 | `giga` | Duas imagens (giganotossauro) | `gigant` (S+ separado) | pending |
| 11 | `megalosaurus` | Duas imagens | `megalosaurus_femea`, `megalosaurus_aberrant_femea` | **done** |
| 12 | `phiomia` | Parece elefante | — | pending |
| 13 | `rhynio` | Parece besouro de esterco (Rhinognatha) | — | **awaiting_review** (ref DodoDex) |
| 14 | `sinomacrops` | Ícone ruim | — | pending |
| 15 | `tekstrider` | Ícone ruim (ex-`tekstrider_femea`) | `tekstrider_femea` | **done** |
| 16 | `reaper` | Duas imagens (ex-xenomorph) | `xenomorph`, `xenomorph_femea`, `xenomorphgen2_femea` | **done** |

Estado também em `static/species/icons/generated/manifest.json` → `regen_queue` e `icons.*.status`.

## Workflow (por espécie)

### 1. Usuário envia referência

Screenshot ou arte mostrando a **anatomia correta** da criatura (in-game, wiki, ou arte própria).
Salvar em `refs/species_icons/{species_key}.png` (ou `.jpg`).

### 2. Gerar prompt com referência

```bash
python tools/generate_ai_species_icons.py --species mosasaurus --reference refs/species_icons/mosasaurus.png
```

O prompt descreve traços anatômicos + instrução de seguir a referência **sem copiar outras criaturas**.

### 3. Regenerar (agente / Cursor GenerateImage)

- Usar o prompt impresso pelo comando acima
- Anexar `reference_image_paths` com a imagem do usuário
- Salvar PNG em `static/species/icons/generated/raw/{species_key}.png`

### 4. Comprimir e publicar

```bash
python tools/generate_ai_species_icons.py --compress-only --force-compress
python tools/sync_ai_icon_manifests.py
```

### 5. Sincronizar variantes/aliases

Após aprovação do canônico:

- **Aliases:** `beaver` → `castoroides`, `doed` → `doedicurus` (automático no manifesto)
- **Variantes `_femea`:** copiar `canonical.webp` → `variant.webp` ou atualizar manifesto
- **`gigant`:** após `giga` aprovado, copiar ou apontar `gigant` para o mesmo ícone

### 6. Usuário aprova → próximo da fila

Atualizar `status` no manifest de `needs_regeneration` → `compressed` e marcar fila como `done`.

## Por onde começar

**Sugestão:** `mosasaurus` — problema claro (muito magro), já houve auditoria anterior, e há demo de moldura em `icons/demo/mosasaurus.png` (usar só moldura, não anatomia).

Alternativa: qualquer espécie da tabela — envie a referência e indique o `species_key`.

## Não fazer em lote

- Não regenerar várias espécies de uma vez sem referência do usuário
- Não usar `rex.png` ou outra criatura como referência de anatomia
- Não remover SVGs procedurais (`icons/*.svg`) — são fallback legal

## ⚠️ Batch DodoDex (subagent 9aeac07c) — PAUSAR

Um batch em `tools/_batch_regen_queue.json` foi iniciado com prompts **antigos** (sem logo ARK, sem nome, sem badge de tier, molduras inconsistentes). **Não continuar** até aprovação da moldura canônica v1.

Após aprovação do usuário nos ícones de prova (`carno`, `rex`, etc.):

1. Regenerar `tools/_batch_regen_queue.json` com o script atualizado:
   ```bash
   python tools/generate_ai_species_icons.py --export-frame-template
   python tools/generate_ai_species_icons.py --species KEY --reference refs/species_icons/KEY.png --frame-reference refs/species_icons/_frame_template_carno.png
   ```
2. Cada prompt agora inclui moldura carno + logo ARK + `{display_name}` + badge `{tier}` (de `market_species_defaults.json` / `official_vanilla_species.json`).
3. Spec completa: `plugin/arkshop_web/data/species_icon_frame_spec.json`
