# Diagnóstico: evento de Páscoa (Easter) e dinos coloridos

**Data:** 09/07/2026  
**Investigação:** subagente read-only `f38e1d9c` (ASM `_asm_src` + ARKLAND `arkland-multi`)  
**Sintoma reportado:** evento de Páscoa configurado, mas nenhum dino colorido apareceu no mapa.

---

## Resumo executivo

**Hipótese principal:** o evento de Páscoa provavelmente **não foi aplicado via `ActiveEvent`**, ou foi aplicado mas o servidor **não reiniciou** / os dinos **não respawnaram**. O ASM original **não implementa** eventos oficiais — isso é feature do ARKLAND TEK. A aba **“Eventos Sazonais”** (buff de rates) **não** gera dinos coloridos.

**O que fazer agora:**

1. Ativar em **TEK → Administração → Evento sazonal ARK → Easter**
2. **Salvar + reiniciar** o mapa (não apenas reconectar ao processo)
3. Rodar **`DestroyWildDinos`** via RCON após o reinício
4. Se houver buffs agendados, verificar se um restore de INI **não apagou** o Easter

---

## 1. Como o ASM aplica eventos (fonte `_asm_src`)

### Conclusão principal

**O ARK Server Manager original não tem suporte nativo a eventos sazonais oficiais (Páscoa, Halloween, etc.).** Não há campo `ActiveEvent` em nenhum `.cs` do ASM.

### O que o ASM faz de fato

| Mecanismo | Onde (`_asm_src`) | Função |
|-----------|-------------------|--------|
| **`AdditionalArgs`** | `ARK Server Manager/Lib/ServerProfile.cs` (~L692–698, ~L3282–3288) | Único jeito “oficial” no ASM de passar `?ActiveEvent=Easter` na linha de comando |
| **`GetServerArgs()`** | `ServerProfile.cs` (~L3242–3288) | Monta `Map?listen?Port=...?QueryPort=...` — **sem** `ActiveEvent` automático |
| **`IniFileEntry` → GUS** | `ServerProfile.cs` (dezenas de campos) | Grava `GameUserSettings.ini` — **nenhum** campo `ActiveEvent` |
| **Branches Steam** | `GameData/SurvivalEvolved.gamedata` (~L12976–12986) | `halloween`, `holidayevent` = branches de **download** do servidor, não toggle de evento em runtime |
| **Extinction Event** | `ServerSettingsControl.xaml` (~L1201+) | Evento do mapa Extinction, não Páscoa |
| **SOTF events** | `ServerSettingsControl.xaml` (~L4965+) | Survival of the Fittest apenas |

### Mecanismo exato no ASM (Páscoa manual)

1. Campo **“Additional Args”** no perfil ASM
2. Valor: `?ActiveEvent=Easter`
3. ASM concatena em `GetServerArgs()` antes dos flags `-server`
4. **Não** grava `ActiveEvent=` no `GameUserSettings.ini` automaticamente

> **ASM tem NO native ActiveEvent** — apenas via `AdditionalArgs=?ActiveEvent=Easter` inserido manualmente pelo operador.

---

## 2. Como o ARKLAND aplica eventos

### Dois sistemas distintos (fonte de confusão)

| Sistema | UI | Campo / módulo | O que faz | Ativa dinos coloridos? |
|---------|-----|----------------|-----------|------------------------|
| **Evento sazonal ARK** | TEK → Administração → **“Evento sazonal ARK”** | `active_event` | `ActiveEvent=Easter` no GUS + `?ActiveEvent=Easter` na CLI | **Sim** |
| **Eventos Sazonais** | Menu **“⚡ Eventos Sazonais”** | `BuffManager` | Multiplicadores temporários de XP/Doma/Breeding/Farm | **Não** |

A Web Store expõe `seasonal_event_active` / `seasonal_event_name` a partir do **BuffManager** (`server_config_snapshot.py`), **não** do `active_event`. Isso pode dar a impressão de que “há um evento ativo” quando na verdade só há buff de rates — sem Páscoa no `ActiveEvent`.

### Fluxo TEK para Páscoa (`active_event`)

1. **UI:** `src/asm_ui/asm_server_panel.py` (~L1155–1156) — combo `_event_combo_entry`
2. **Valores:** `src/ui_constants.py` (~L215–226) — `("Easter", "Easter — Páscoa / Eggcellent Adventure 🐣")`
3. **Normalização:** `ARKEaster` → `Easter` (`ui_constants.py` ~L228–246; fix em v1.10.x)
4. **INI:** `src/asm_engine/asm_ini_manager.py` (~L51) — mapeamento `ServerSettings` / `ActiveEvent` (só se `active_event` não vazio)
5. **Remoção quando vazio:** `asm_ini_manager.py` (~L668–671) — se `active_event=""`, remove `ActiveEvent` do GUS
6. **CLI:** `asm_ini_manager.py` (~L1006–1009) — `?ActiveEvent=Easter` em `_launch_url_params`
7. **Persistência:** `_asm_persist_server` em `src/app_tek.py` (~L990–1032) — widgets → JSON → `write_ini` → start
8. **Start:** `src/asm_engine/asm_server_manager.py` (~L310–350) — `write_ini` + `build_launch_args` antes de subir o processo

### `buff_manager.py` e Easter

- **Não** toca em `active_event` / `ActiveEvent` ao aplicar buffs
- `_backup_ini` (`buff_ini_backups.py`) faz zip de `GameUserSettings.ini` + `Game.ini` **antes** do buff
- Ao encerrar buff (`stop_active_event`, ~L632+): restaura o zip antigo via `restore_ini_from_backup`
- `_sync_profile_from_ini` (~L722–745) re-lê INI após restaurar backup — se o backup **não tinha** Easter, **apaga** `active_event` do perfil JSON
- **Risco:** se o usuário ativou Páscoa **depois** que um buff criou o backup, o restore ao fim do buff **reverte** `ActiveEvent` no GUS e no perfil

---

## 3. Gap analysis ASM vs ARKLAND

| Aspecto | ASM | ARKLAND TEK |
|---------|-----|-------------|
| Campo dedicado `ActiveEvent` | ❌ | ✅ `active_event` |
| Grava GUS.ini | ❌ (manual) | ✅ automático |
| Parâmetro CLI | Só via `AdditionalArgs` | ✅ automático |
| UI de seleção de evento | ❌ | ✅ combo na Administração |
| Normalização `ARKEaster` | N/A | ✅ (desde ~v1.10.x) |
| Buff de rates | ❌ | ✅ (sistema separado) |
| Web Store `seasonal_event_active` | N/A | ⚠️ Reflete **BuffManager**, não `ActiveEvent` |

**ARKLAND não “sobrescreve” o ASM** no sentido de apagar `AdditionalArgs` — mas se o perfil TEK tem `active_event=""`, o `write_ini` **remove** `ActiveEvent` do GUS (`asm_ini_manager.py` ~L668–671).

---

## 4. Causas raiz (ordenadas por probabilidade)

### 1. Confusão entre os dois “eventos” — **muito provável**

Criar evento em **“Eventos Sazonais”** só altera rates (XP, doma, breeding, farm). Dinos coloridos exigem **“Evento sazonal ARK” → Easter** na aba Administração do servidor TEK.

### 2. Servidor não reiniciado após ativar — **muito provável**

`ActiveEvent` só vale no **startup**. Se o TEK reconecta a processo já rodando (`asm_server_manager.py` ~L321–327), mostra aviso mas **não aplica** a nova config na sessão em curso.

### 3. Dinos já spawnados não mudam de cor — **muito provável**

Mesmo com Easter ativo, dinos **já existentes** não ficam coloridos. É preciso:

- `DestroyWildDinos` via RCON, **ou**
- `-ForceRespawnDinos` no próximo start, **ou**
- explorar áreas novas e aguardar respawn natural

### 4. BuffManager restaurou backup sem Easter — **provável** (clusters com buffs)

Se um buff sazonal terminou **depois** de você ativar Páscoa, o restore do zip antigo pode ter removido `ActiveEvent` do INI e do JSON do perfil.

### 5. ID legado `ARKEaster` — **menos provável** em v1.10.16+

Versões antigas gravavam valor inválido. Corrigido em v1.10.x — valor correto é **`Easter`**.

### 6. Configurou só no ASM sem `AdditionalArgs` — **se usa ASM puro**

ASM **não tem** UI de Páscoa. Sem `?ActiveEvent=Easter` em Additional Args, nada acontece.

### 7. Branch Steam errada — **improvável** para Páscoa

`halloween` / `holidayevent` são branches de instalação, não substituem `ActiveEvent=Easter`.

### 8. Janela de datas — **improvável** em servidor dedicado

Em servidor privado com `ActiveEvent` forçado, o evento **não depende** do calendário oficial da Wildcard.

---

## 5. Correções recomendadas no ARKLAND

| Prioridade | Correção | Motivo |
|------------|----------|--------|
| Alta | **Separar `active_event` de `seasonal_event_active` na Web Store** | Evitar falsa impressão de “evento Páscoa ativo” quando só há buff de rates |
| Alta | **Preservar `ActiveEvent` no restore do BuffManager** | Ao restaurar backup, manter `ActiveEvent` do GUS atual ou excluir essa chave do zip de restore |
| Média | **UX ao salvar `active_event`:** avisar “Reinicie o servidor e rode DestroyWildDinos” | Reduzir expectativa de dinos coloridos sem respawn |
| Baixa | **Documentar** que ASM puro exige `AdditionalArgs=?ActiveEvent=Easter` | Operadores que ainda usam ASM standalone |

### Implementação sugerida (Buff restore)

Ao chamar `restore_ini_from_backup` no fim de um buff:

1. Ler `ActiveEvent` atual do GUS **antes** do restore
2. Restaurar o zip do backup
3. Se havia `ActiveEvent` no GUS pré-restore e o backup não continha a chave (ou tinha valor vazio), **reaplicar** o valor preservado

Alternativa: excluir `ServerSettings/ActiveEvent` do escopo do backup de buff (backup só de rates, não de evento oficial).

### Implementação sugerida (Web Store)

Em `server_config_snapshot.py` e `plugin/arkshop_web/app.py`, expor campos adicionais:

- `ark_active_event` — valor de `active_event` normalizado (`Easter`, `FearEvolved`, etc.)
- `ark_active_event_label` — rótulo legível para o painel

Manter `seasonal_event_active` exclusivamente para o BuffManager.

---

## 6. Checklist de verificação no servidor

```text
[ ] TEK → servidor → Administração → "Evento sazonal ARK" = "Easter — Páscoa..."
[ ] Salvar perfil + Reiniciar (não só "reconectar")
[ ] GameUserSettings.ini contém: ActiveEvent=Easter  (seção [ServerSettings])
[ ] RunServer.cmd / linha de comando contém: ?ActiveEvent=Easter
[ ] Valor é "Easter" (não ARKEaster)
[ ] Nenhum buff sazonal ativo que possa ter restaurado backup antigo
[ ] Após reinício: RCON → DestroyWildDinos → aguardar respawn
[ ] Procurar Bunny Dodo / Oviraptor colorido em zonas novas
[ ] Se usa ASM puro: AdditionalArgs = ?ActiveEvent=Easter
```

### Comandos PowerShell de inspeção

```powershell
# GUS.ini
Select-String -Path "C:\caminho\ShooterGame\Saved\Config\WindowsServer\GameUserSettings.ini" -Pattern "ActiveEvent"

# RunServer.cmd (se existir)
Select-String -Path "C:\caminho\ShooterGame\Binaries\Win64\RunServer.cmd" -Pattern "ActiveEvent"
```

### O que esperar in-game (Easter)

- Variantes coloridas de espécies vanilla (ex.: Bunny Dodo, Oviraptor festivo)
- Loot temático de ovos / itens do Eggcellent Adventure
- **Não** é garantido em dinos que já existiam antes do evento — respawn é obrigatório

---

## 7. Referências no código ARKLAND

| Arquivo | Trecho | Papel |
|---------|--------|-------|
| `src/ui_constants.py` | ~L215–246 | IDs oficiais + normalização `ARKEaster` → `Easter` |
| `src/asm_engine/asm_ini_manager.py` | ~L51, ~L668–671, ~L1006–1009 | Mapeamento INI, remoção condicional, parâmetro CLI |
| `src/asm_ui/asm_server_panel.py` | ~L878–912, ~L1155, ~L1349 | UI “Evento sazonal ARK” |
| `src/buff_manager.py` | ~L711–762, ~L1028–1032 | Backup/restore INI dos buffs |
| `src/buff_ini_backups.py` | ~L46–120 | Zip GUS + Game.ini |
| `src/server_config_snapshot.py` | ~L179–216 | `seasonal_event_active` (BuffManager only) |
| `plugin/arkshop_web/static/index.html` | ~L18841 | Badge de evento na Web Store (buff) |

---

## 8. Diff resumido ASM vs ARKLAND

| | ASM | ARKLAND TEK |
|---|-----|-------------|
| Ativar Páscoa | Manual: `AdditionalArgs=?ActiveEvent=Easter` | UI: Administração → Evento sazonal ARK → Easter |
| INI `ActiveEvent` | Não grava automaticamente | Grava em `[ServerSettings]` |
| CLI `?ActiveEvent=` | Só se operador colocou em Additional Args | Automático no `build_launch_args` |
| Dinos coloridos | Mesmo mecanismo ARK (`ActiveEvent`) | Mesmo mecanismo ARK (`ActiveEvent`) |
| Buff de rates | Não existe | Sistema separado — **não** ativa cores |
| Risco de revert | N/A | Buff restore pode apagar Easter |

---

## Histórico

| Data | Autor | Nota |
|------|-------|------|
| 2026-07-09 | Investigação `f38e1d9c` | Diagnóstico inicial ASM vs ARKLAND; arquivo criado a partir do relatório read-only |
