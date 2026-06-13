# Projeto de Performance da Interface — ARKLAND Server Manager

> **Status:** Concluído (Fase 0–5) — release 1.8.2 (2026-06-13)  
> **Data:** 2026-06-12  
> **Problema:** Carregamento de páginas e seções extremamente lento, degradando a experiência do usuário  
> **Objetivo:** Tornar a navegação fluida, previsível e responsiva em máquinas típicas de administração de servidor ARK

---

## 1. Resumo executivo

A interface já possui **cache de frames** (`show_frame_tek.py`) e **lazy loading por seção** (`asm_server_panel.py`), mas a percepção de lentidão continua alta porque:

1. O **shell do painel de servidor** cria **31 `CTkScrollableFrame` vazios** antes de mostrar qualquer conteúdo.
2. A **primeira seção (Administração)** é construída de forma **síncrona e massiva** (campos + mods + threads de disco).
3. O `after(16)` atual **só adia 1 frame** — não fragmenta o trabalho pesado.
4. Seções densas (Regras, Jogador/Dino, INI, Agregados) criam **centenas de widgets** em uma única passada.
5. Páginas globais (Loja, Banco de Dados) constroem **toda a UI** na primeira visita.

**Meta do projeto:** reduzir o tempo até a interface ficar interativa em **≥70%** nas operações críticas, com UI nunca congelada por mais de **200 ms** consecutivos.

---

## 2. Diagnóstico técnico

### 2.1 Arquitetura atual

```
Navegação sidebar
  └─ show_frame_tek (cache por cache_key)
       ├─ Dashboard        → rebuild parcial frequente
       ├─ Loja / DB / etc. → build completo na 1ª visita
       └─ server_panel     → build_asm_server_panel
            ├─ [PROBLEMA] loop: 31× CTkScrollableFrame (eager)
            ├─ loading_overlay + after(16)
            ├─ _ensure_section("Administração") — builder síncrono
            └─ troca de seção → builder síncrono na 1ª visita
```

### 2.2 O que já funciona bem

| Mecanismo | Arquivo | Efeito |
|-----------|---------|--------|
| Cache de frames top-level | `show_frame_tek.py` | Revisitar páginas = instantâneo |
| Lazy por seção TEK | `asm_server_panel.py` | Conteúdo só na 1ª visita à seção |
| Lazy por aba (modo legado) | `server_panel.py` | Só "Geral" no open |
| Chunking comprovado | `tab_game.py` | Lotes de 6 widgets via `after(0)` |
| Accordion colapsado | `server_field_widgets.py` | Stats per-level ocultos até expandir |
| Busca Workshop em thread | `asm_server_panel.py` | Rede não bloqueia UI |

### 2.3 Gargalos principais (ordenados por impacto)

| # | Gargalo | Impacto | Evidência |
|---|---------|---------|-----------|
| 1 | 31 scroll frames criados upfront | **Crítico** | `asm_server_panel.py` L356–362 |
| 2 | Administração como seção default gigante | **Crítico** | `_build_administracao` ~50 campos + mods |
| 3 | Mods: N linhas + N threads `Path.exists()` | **Alto** | `_add_mod_row` na abertura |
| 4 | `after(16)` sem chunking real | **Alto** | Builder inteiro em 1 callback |
| 5 | Regras / Jogador / Dino: 40+ sliders | **Alto** | `build_cards_layout` + `add_float_field` |
| 6 | Editor INI: widget por par chave=valor | **Alto** | `_build_ini_editor` |
| 7 | Listas agregadas: widget por item | **Médio–Alto** | `tek_list_editor.py` |
| 8 | Loja / DB sem lazy interno | **Médio** | `customshop_panel`, `db_manager_panel` |
| 9 | Dashboard/sidebar rebuild destrutivo | **Médio** | `_refresh_asm_dashboard`, `rebuild_server_sidebar_tek` |
| 10 | Startup empilha tarefas (scan, webstore, sync) | **Médio** | `app_tek.py` after(500ms–3s) |

### 2.4 Métricas alvo (antes → depois)

| Operação | Hoje (estimado) | Meta |
|----------|-----------------|------|
| Abrir painel servidor (1ª vez) | 2–8 s | **< 800 ms** até shell interativo |
| Seção Administração (1ª vez) | 1–4 s | **< 1,5 s** com progresso visível |
| Trocar seção já visitada | < 100 ms | Manter |
| Trocar seção pesada (1ª vez) | 1–5 s | **< 2 s** com chunking |
| Abrir Loja / DB (1ª vez) | 1–3 s | **< 1 s** até primeira aba |
| Freeze perceptível (UI travada) | 500 ms–3 s | **Nunca > 200 ms** |

*Medição: instrumentar com `time.perf_counter()` + log em `docs/perf_baseline.json` na Fase 0.*

---

## 3. Visão da solução

### Princípios

1. **Shell imediato, conteúdo progressivo** — usuário vê nav + skeleton em < 300 ms.
2. **Chunking universal** — todo builder pesado usa o padrão de `tab_game.py`.
3. **Criar widgets sob demanda** — nunca alocar containers para seções não visitadas.
4. **Virtualizar listas longas** — INI, mods, agregados não escalam O(n) em widgets.
5. **I/O e rede fora do main thread** — filesystem, Steam API, DB só em background.
6. **Medir antes de otimizar** — baseline numérico, não achismo.

### Arquitetura proposta

```
build_asm_server_panel (novo)
  ├─ Fase A — Shell instantâneo (< 300 ms)
  │    ├─ Header + botões Start/Stop/Salvar
  │    ├─ Nav lateral (31 botões)
  │    ├─ 1× content_host (frame único, sem 31 scrolls)
  │    └─ Skeleton + "Carregando seção…"
  │
  ├─ Fase B — Seção sob demanda (chunked)
  │    ├─ _ensure_section(name):
  │    │    ├─ cria CTkScrollableFrame só aqui
  │    │    ├─ ChunkedSectionBuilder (lotes de 8–12 widgets)
  │    │    └─ progress bar / contador "12/48 campos"
  │    └─ cache em section_built (mantém)
  │
  ├─ Fase C — Listas virtualizadas
  │    ├─ Mods: tabela paginada ou lazy rows
  │    ├─ INI: editor texto + painel estruturado opcional
  │    └─ Agregados: VirtualListEditor (só linhas visíveis)
  │
  └─ Fase D — Preload inteligente (opcional, idle)
       └─ after(3000): pré-aquecer Administração + Regras em background
```

---

## 4. Plano de implementação em fases

### Fase 0 — Baseline e instrumentação (1 dia)

**Entregas:**
- Módulo `src/ui/perf_monitor.py` com decorators `@timed_section` e `@timed_build`
- Log estruturado: `{operation, ms, widgets_created, section}`
- Script `scripts/perf_report.py` para comparar antes/depois
- Tabela de baseline em `docs/perf_baseline.json`

**Critério de aceite:** conseguir medir tempo de abertura do painel e de cada seção com precisão de ±10 ms.

---

### Fase 1 — Quick wins críticos (2–3 dias)

Impacto imediato na percepção do usuário.

#### 1.1 Eliminar 31 scroll frames upfront

**Arquivo:** `asm_server_panel.py`

**Mudança:**
```python
# ANTES: loop cria 31 CTkScrollableFrame
# DEPOIS: 1 content_host; scroll frame criado em _ensure_section(name)
```

**Ganho estimado:** 40–60% menos tempo ao abrir painel servidor.

#### 1.2 ChunkedSectionBuilder (padrão reutilizável)

**Novo arquivo:** `src/ui/chunked_builder.py`

**API:**
```python
class ChunkedSectionBuilder:
    def __init__(self, parent, chunk_size=10, on_progress=None): ...
    def add_task(self, fn: Callable[[], None]) -> None: ...
    def run(self) -> None: ...  # after(0) entre chunks
```

**Portar para:**
- `_build_administracao` (prioridade máxima)
- `build_cards_layout` / seções Regras, Jogador, Dino
- `customshop_panel` (tabs internas)
- `db_manager_panel` (tabs internas)

**Referência existente:** `tab_game.py` L1012–1024 (`_CHUNK = 6`).

#### 1.3 Adiar lista de mods na Administração

**Mudança:**
- Mostrar skeleton "Carregando mods…" + contador
- `_add_mod_row` em lotes de 5 via `after(0)`
- `_check_status` (filesystem) só ao expandir seção Mods ou após idle

**Ganho estimado:** Administração deixa de escalar linearmente com quantidade de mods.

#### 1.4 Debounce de refresh dashboard/sidebar

**Arquivos:** `app_tek.py`, `rebuild_server_sidebar_tek.py`

**Mudança:** coalescer múltiplos `_refresh_asm_dashboard` em janela de 500 ms; não destruir/recriar cards se dados não mudaram.

**Critério de aceite Fase 1:**
- Painel servidor interativo (nav clicável) em **< 500 ms**
- Nenhum freeze > 300 ms ao trocar seção (medido por perf_monitor)

---

### Fase 2 — UX de carregamento e preload (2 dias)

#### 2.1 Skeleton screens

Substituir "Carregando configuração…" estático por:
- Barra de progresso determinística (campos construídos / total)
- Nome da seção + ETA aproximado
- Nav lateral **sempre** clicável (fila de seções se usuário trocar durante build)

#### 2.2 Fila de builds cancelável

Se usuário clica outra seção durante chunking:
- Cancelar chunk atual (flag `_build_cancelled`)
- Iniciar build da nova seção
- Evitar trabalho desperdiçado

#### 2.3 Preload idle (opcional, configurável)

Após 3 s sem interação no painel servidor:
- Pré-construir em background (chunked): **Regras** + **Jogador**
- Desligável em Configurações → Performance

**Critério de aceite Fase 2:**
- Usuário sempre vê feedback de progresso
- Troca de seção durante load não trava nem corrompe estado

---

### Fase 3 — Virtualização de listas longas (3–5 dias)

#### 3.1 Mods — tabela compacta

- Substituir N frames por `CTkScrollableFrame` com rows reutilizáveis
- Status de arquivo: ícone cacheado, refresh manual ou a cada 60 s
- Bulk add permanece; render incremental

#### 3.2 Editor INI — modo híbrido

**Problema:** `_build_ini_editor` cria 2 entries + botão por linha.

**Solução:**
- **Modo rápido (default):** `CTkTextbox` monolítico para edição em massa
- **Modo estruturado:** parse lazy + virtual list (só 20 linhas visíveis)
- Toggle "Modo avançado" para quem precisa de UI por campo

#### 3.3 Agregados (`tek_list_editor`)

- `VirtualListEditor`: mantém pool de ~15 row widgets, recicla ao scroll
- Aplicar em: Harvest, DinoClass, SpawnWeight, PreventTame, etc.

**Critério de aceite Fase 3:**
- INI com 200+ linhas: abertura **< 1 s**
- Lista com 100+ itens: scroll fluido, memória estável

---

### Fase 4 — Páginas globais e startup (2 dias)

#### 4.1 Lazy interno — Loja e Banco de Dados

Mesmo padrão de `server_panel.py`:
- Criar tabs vazias + placeholder
- Construir conteúdo na primeira visita à aba
- Cache por aba (`_built_shop_tabs`)

#### 4.2 Startup escalonado

**Arquivo:** `app_tek.py`

| Tarefa | Hoje | Proposto |
|--------|------|----------|
| Watermark | 150 ms | Manter |
| Auto-start sync/remoto | 500 ms | 2000 ms ou após 1ª interação |
| Scan processos ARK | 600 ms | Thread + debounce |
| Webstore auto-start | 3000 ms | Após painel estável ou manual |
| Status tick dashboard | 30 s | 60 s se janela inativa |

#### 4.3 Cache de índice de busca

`section_search_index()` → módulo singleton, calculado 1× no boot.

**Critério de aceite Fase 4:**
- 1ª abertura Loja/DB: primeira aba **< 1 s**
- Boot do app: dashboard utilizável antes de qualquer auto-start pesado

---

### Fase 5 — Consolidação e polish (1–2 dias)

- Remover código morto do modo PRIMITIVE se TEK for 100% default
- Unificar padrão lazy (seção TEK = aba PRIMITIVE = tab Loja)
- Documentar em `docs/UI_PATTERNS.md` para novos painéis
- Entrada no CHANGELOG + release minor (ex: 1.8.2 ou 1.9.0)

---

## 5. Componentes novos (design)

### 5.1 `ChunkedSectionBuilder`

```
src/ui/chunked_builder.py
  ├─ ChunkedSectionBuilder
  ├─ BuildTask (callable + label opcional)
  └─ ProgressReporter (callback para overlay)
```

**Regras:**
- `chunk_size` default: 10 (ajustável por seção)
- Entre chunks: `parent.update_idletasks()` + `after(0, ...)`
- Exceções em task: log + continua (não aborta seção inteira)

### 5.2 `VirtualListEditor`

```
src/ui/virtual_list.py
  ├─ VirtualListEditor(parent, item_height=32, visible_count=15)
  ├─ set_items(items: list)
  ├─ on_render_row(index, row_frame) → callback
  └─ scroll → recicla row widgets
```

### 5.3 `SectionShell`

```
src/ui/section_shell.py
  ├─ 1 content_host por painel servidor
  ├─ get_or_create_scroll_frame(section_name) → lazy
  └─ show_skeleton(section_name)
```

---

## 6. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Chunking quebra ordem de `grid` | Tasks ordenadas; testes visuais por seção |
| Cancelamento de build deixa vars_ref inconsistente | Build atômico por seção; rollback em erro |
| Virtual list perde edição em andamento | Flush on blur antes de reciclar row |
| Preload consome CPU em máquina fraca | Toggle em configurações; default off |
| Regressão em Salvar/Carregar config | Teste manual checklist por seção após cada fase |

---

## 7. Checklist de validação (test plan)

### Por fase

- [ ] Abrir painel servidor 10× — mediana de tempo registrada
- [ ] Navegar todas as 31 seções — sem crash, sem widget órfão
- [ ] Servidor com 30+ mods — Administração abre sem freeze longo
- [ ] INI grande (importado) — editor utilizável
- [ ] Salvar + reiniciar app — valores persistidos corretamente
- [ ] Trocar seção durante carregamento — comportamento correto
- [ ] 2ª visita a qualquer seção — instantânea (< 100 ms)
- [ ] Loja + DB — lazy tabs funcionando

### Máquina de referência

- Windows 10/11, 4 cores, 8 GB RAM, HDD (pior caso)
- Se fluir no HDD, SSD será excelente

---

## 8. Cronograma sugerido

| Fase | Duração | Impacto UX | Prioridade |
|------|---------|------------|------------|
| 0 — Baseline | 1 dia | Diagnóstico | P0 |
| 1 — Quick wins | 2–3 dias | **Muito alto** | P0 |
| 2 — UX + fila | 2 dias | Alto | P1 |
| 3 — Virtualização | 3–5 dias | Alto (casos extremos) | P1 |
| 4 — Páginas globais | 2 dias | Médio | P2 |
| 5 — Consolidação | 1–2 dias | Manutenção | P2 |

**Total estimado:** 11–15 dias de desenvolvimento focado.

**Recomendação:** implementar **Fase 0 + Fase 1** imediatamente — maior retorno com menor risco.

---

## 9. Ordem de execução recomendada (próximo passo)

1. Criar `perf_monitor.py` e medir baseline atual
2. Refatorar `asm_server_panel.py`: 1 `content_host`, scroll lazy
3. Extrair `ChunkedSectionBuilder` de `tab_game.py`
4. Aplicar chunking em `_build_administracao`
5. Adiar render de mods
6. Validar com usuário → continuar Fases 2–4

---

## 10. Referências no código

| Padrão bom (reutilizar) | Arquivo |
|-------------------------|---------|
| Chunking | `src/pages/tab_game.py` |
| Lazy tabs | `src/pages/server_panel.py` |
| Cache frames | `src/pages/show_frame_tek.py` |
| Lazy seções | `src/asm_ui/asm_server_panel.py` |
| Custo por campo | `src/ui/server_field_widgets.py` |
| Listas agregadas | `src/ui/tek_list_editor.py` |
| Editor INI | `src/asm_ui/asm_server_panel.py` → `_build_ini_editor` |

---

## 11. Progresso de implementação

### Concluído (Fase 0 + Fase 1 parcial)

| Item | Arquivo | Status |
|------|---------|--------|
| `PerfMonitor` + `timed_build` | `src/ui/perf_monitor.py` | ✅ |
| `ChunkedSectionBuilder` | `src/ui/chunked_builder.py` | ✅ |
| Scroll frames lazy (1 por seção) | `asm_server_panel.py` | ✅ |
| Loading com nome da seção + progress bar | `asm_server_panel.py` | ✅ |
| Mods populados em lotes de 5 | `asm_server_panel.py` | ✅ |
| Status de mods adiado 120 ms | `asm_server_panel.py` | ✅ |
| Debounce sidebar/dashboard (400 ms) | `app_tek.py` | ✅ |

### Concluído (Fase 2 parcial)

| Item | Arquivo | Status |
|------|---------|--------|
| `build_cards_layout_chunked` + `run_ui_tasks_chunked` | `server_field_widgets.py` | ✅ |
| Chunking: Regras, Jogador, Dino | `asm_server_panel.py` | ✅ |
| Fila cancelável ao trocar seção durante build | `asm_server_panel.py` | ✅ |
| Lazy tabs na Loja (só Config no open) | `customshop_panel.py` | ✅ |

### Concluído (Fase 3 parcial)

| Item | Arquivo | Status |
|------|---------|--------|
| Listas agregadas em lotes (6 linhas/chunk) | `tek_list_editor.py` | ✅ |
| Seções agregadas chunked (harvest/dino/spawn) | `tek_aggregated_sections.py` | ✅ |
| Chunking: Coleta, Mult. Classe, Spawn, Custom INI | `asm_server_panel.py` | ✅ |
| Render incremental itens INI (12/chunk) | `asm_server_panel.py` | ✅ |

### Concluído (Fase 4 parcial)

| Item | Arquivo | Status |
|------|---------|--------|
| Lazy browser Banco de Dados (`after(0)`) | `db_manager_panel.py` | ✅ |
| Startup escalonado (auto-start 2s/5s) | `app_tek.py` | ✅ |
| Status tick 60s se janela inativa | `app_tek.py` | ✅ |
| Lazy tabs na Loja (só Config no open) | `customshop_panel.py` | ✅ |

### Concluído (Fase 2 — expandido)

| Item | Arquivo | Status |
|------|---------|--------|
| Chunking: Meio Ambiente, Estruturas | `asm_server_panel.py` | ✅ |
| Progress bar determinística (X/Y) | `asm_server_panel.py`, `server_field_widgets.py` | ✅ |
| Baseline `docs/perf_baseline.json` | `perf_monitor.py` | ✅ |
| Auto-save medições ao concluir seção | `asm_server_panel.py` | ✅ |

### Concluído (Fase 5)

| Item | Arquivo | Status |
|------|---------|--------|
| Admin: tail (CLI/ações/help) adiado após mods | `asm_server_panel.py` | ✅ |
| Chunking Engramas | `asm_server_panel.py` | ✅ |
| Cache `section_search_index` | `server_field_labels.py` | ✅ |
| Documentação `docs/UI_PATTERNS.md` | — | ✅ |

### Banco de dados (1.8.2)

| Item | Arquivo | Status |
|------|---------|--------|
| Assistente guiado 3 passos | `db_setup_wizard.py` | ✅ |
| SQL embutido/cópia APPDATA + PyInstaller | `db_setup_resources.py`, `.spec` | ✅ |
| Retry conexão sem database (1049) | `db_manager_panel.py` | ✅ |
| `setup_db.sql` no instalador Inno Setup | `setup.iss` | ✅ |
| Prefs `shop_db` para Loja | `db_setup_resources.py`, `shop_integration.py` | ✅ |

---
