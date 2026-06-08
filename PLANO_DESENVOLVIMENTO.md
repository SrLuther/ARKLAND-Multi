# ARKLAND-Multi — Plano de Desenvolvimento Completo

> **Gerado em:** 08/06/2026
> **Versão Base:** 1.4.1 (commit `1974153`)
> **Modo Ativo:** TEK (CustomTkinter + Python 3.12)
> **Status:** UI TEK 100% construída, Engine TEK ~60% completa

---

## 1. Ação Imediata — Consolidação da Documentação

### 1.1 Arquivos a Excluir (Desatualizados / Substituídos)

| Arquivo | Motivo da Exclusão |
|---|---|
| `ROADMAP.md` | Versão de 30/05/2026 (v1.3.57), desatualizada em relação aos 11 commits posteriores; todas as especificações técnicas (INI_MAP, CLI flags, dependências, ordem de execução) foram absorvidas neste plano |
| `IMPROVEMENTS_PLAN.md` | Checklist de features com estimativas de tempo e priorização obsoletas; roadmap de 6 meses não reflete o estado real do código (muitos itens marcados como "pendentes" já têm arquivos criados) |
| `OPTIMIZATION_PLAN.md` | Análise de performance datada de 30/05/2026 que não considera refatorações posteriores (pages/ modularizadas, lazy loading das abas, CustomShop teletransportado) |

### 1.2 Arquivos Mantidos (Referências Ativas)

| Arquivo | Motivo da Manutenção |
|---|---|
| `CHANGELOG.md` | Histórico de releases; é fonte de verdade para versionamento |
| `PENDING_ISSUES.md` | Documento de investigação histórica do crash ArkShopUI (T1–T14); contém a causa raiz definitiva e deve ser preservado como referência |
| `DESIGN_SYSTEM.md` | Sistema de cores, tipografia e componentes visuais; ainda é referência ativa para UI |
| `ARK_SERVER_CONFIG_REFERENCE.md` | Referência de campos do ASM original |
| `ARKLAND_TEK.md` | Visão geral da arquitetura TEK |

---

## 2. TEK Core — Funcionalidades Críticas

### 2.1 A1. Per-Level Stats → INI

**Arquivo:** `src/asm_engine/asm_ini_manager.py`
**Prioridade:** 🔴 Alta (sem isso, servidores reais nunca recebem Per-Level Stats)

Os arrays `per_level_player[0..11]` até `per_level_dino_tamed_affinity[0..11]` existem em `AsmServerConfig` e são editáveis na UI (seções 9 e 10), mas `write_ini()` ainda não os grava no `Game.ini`.

**Implementação:**
```python
PERLEVEL_MAP = [
    ("per_level_player",            "PerLevelStatsMultiplier_Player"),
    ("per_level_dino_wild",         "PerLevelStatsMultiplier_DinoWild"),
    ("per_level_dino_tamed",        "PerLevelStatsMultiplier_DinoTamed"),
    ("per_level_dino_tamed_add",    "PerLevelStatsMultiplier_DinoTamed_Add"),
    ("per_level_dino_tamed_affinity", "PerLevelStatsMultiplier_DinoTamed_Affinity"),
]

game_mode_sec = game.setdefault("/Script/ShooterGame.ShooterGameMode", {})
for field_attr, ini_prefix in PERLEVEL_MAP:
    values: list = getattr(cfg, field_attr, [])
    for idx, val in enumerate(values):
        game_mode_sec[f"{ini_prefix}[{idx}]"] = _format_value(val)
```

**Dependências:** nenhuma.
**Nota:** os `_raw_*` (crafting, stack, spawner, supply crate, prevent transfer) já são injetados via `_inject_raw()` — não requerem alteração.

---

### 2.2 A2. AsmSteamCmd — Instalação / Atualização via SteamCMD

**Arquivo a criar:** `src/asm_engine/asm_steamcmd.py`
**Referência:** `Lib/ServerApp.cs` (source ASM C#)
**Prioridade:** 🔴 Alta

```python
class AsmSteamCmd:
    """Gerencia install/update/validate de servidores ARK via SteamCMD."""
    APP_ID = "376030"

    def __init__(self, steamcmd_path: str,
                 on_log: Callable[[str], None] = None) -> None: ...

    def install_server(self, install_dir: str, branch: str = "",
                       branch_password: str = "",
                       on_done: Callable[[bool, str], None] = None) -> None:
        """Comando: steamcmd.exe +login anonymous
                              +force_install_dir <install_dir>
                              +app_update 376030 [-beta <branch> -betapassword <pwd>]
                              +quit  (em thread separada, log via on_log)"""

    def validate_server(self, install_dir: str,
                        on_done: Callable[[bool, str], None] = None) -> None:
        """app_update 376030 validate"""

    def download_mod(self, mod_id: str, install_dir: str,
                     on_done: Callable[[bool, str], None] = None) -> None:
        """+workshop_download_item 346110 <mod_id> → copia de
        Steam\steamapps\workshop\content\346110\<mod_id>\ para
        <install_dir>\ShooterGame\Content\Mods\<mod_id>\"""

    def get_steamcmd_path(self) -> Optional[str]:
        """1. Registro: HKCU\Software\Valve\Steam\SteamPath\\steamcmd
            2. Padrão: C:\\steamcmd\\steamcmd.exe
            3. Configurado em config.json"""
```

**Caminhos críticos:**
- SteamCMD padrão: `C:\steamcmd\steamcmd.exe`
- ARK Server App ID: `376030`
- ARK Workshop ID: `346110`

---

### 2.3 A3. Botões de Ação no Painel Administração

**Arquivo:** `src/asm_ui/asm_server_panel.py` — `_build_administracao()`
**Depende de:** A2 (`asm_steamcmd.py`)
**Prioridade:** 🔴 Alta

Botões a adicionar na seção Administração (row ~30+):
```python
ctk.CTkButton(sf, text="⬇  Instalar / Atualizar Servidor",  command=_do_install)
ctk.CTkButton(sf, text="📦  Baixar / Atualizar Mods",        command=_do_mods)
ctk.CTkButton(sf, text="✅  Validar Arquivos",               command=_do_validate)
```

**Callbacks:** os três instanciam `AsmSteamCmd` passando `app.config_manager.steamcmd_path` e exibem resultado via toast/dialog ao final da thread.

---

### 2.4 A4. read_ini() — Leitura do INI → AsmServerConfig

**Arquivo:** `src/asm_engine/asm_ini_manager.py`
**Prioridade:** 🟡 Média (pré-requisito para importar servidor existente)

```python
def read_ini(cfg: AsmServerConfig) -> None:
    """Lê GameUserSettings.ini e Game.ini e popula cfg.
    - Inverte campos com inverted=True
    - Converte tipos: str→bool, str→int, str→float
    - Lê PerLevelStatsMultiplier_Player[N] via regex
    """
```

**Lógica de inversão:** `ServerPVE=True → enable_pvp = False`
**Leitura de per-level:** regex `r'PerLevelStatsMultiplier_(\w+)\[(\d+)\]'`
**UI:** botão "Importar do INI" nas seções Custom GUS / Custom Game do painel.

---

### 2.5 A5. restart() + RCON DoExit no AsmServerManager

**Arquivo:** `src/asm_engine/asm_server_manager.py`
**Prioridade:** 🟡 Média

```python
def restart(self, server_id: str, use_rcon: bool = True,
            on_done: Optional[Callable[[bool, str], None]] = None) -> None:
    """1. Envia RCON 'DoExit' se use_rcon=True
        2. Aguarda status STOPPED (timeout 60s)
        3. Chama self.start(cfg, on_done)"""
```

**Integração:** `app_tek.py` obtém `_asm_restart_server(srv)`.

---

## 3. Janelas Auxiliares TEK

### 3.1 A6. Console RCON TEK

**Arquivo:** `src/asm_ui/asm_rcon_window.py`
**Usa:** `src/rcon_client.py` (já existente)
**Prioridade:** 🟡 Média

Open: `open_asm_rcon_window(app, srv: AsmServerConfig)`
- Autoconecta usando `srv.server_ip`, `srv.rcon_port`, `srv.admin_password`
- TopBar com status ✅/❌
- Log scrollable (CTkTextbox, readonly, fonte Consolas, fundo escuro)
- Input de comando + botão "Enviar" + histórico (↑↓ navegação)
- Atalhos rápidos: `ListPlayers`, `SaveWorld`, `DoExit`, `Broadcast <msg>`

---

### 3.2 A7. Lista de Jogadores TEK

**Arquivo:** `src/asm_ui/asm_player_list.py`
**Usa:** `src/rcon_client.py`
**Prioridade:** 🟡 Média

Open: `open_asm_player_list(app, srv: AsmServerConfig)`
- RCON `ListPlayers` → parse de `"0. Nome, SteamID"`
- Refresh automático a cada 30s via `app.after()`
- Ações por jogador: Kick, Ban, Whitelist, Admin

**RCON commands usados:**
- `ListPlayers`
- `KickPlayer <steamid>`
- `Ban <nome>`
- `Cheat AddToWhitelist <steamid>`
- `Cheat AllowPlayerToJoinNoCheck <steamid>`

---

### 3.3 A8. Backup / Restore de Saves TEK

**Arquivo:** `src/asm_ui/asm_save_restore.py`
**Prioridade:** 🟢 Baixa

Open: `open_asm_save_restore(app, srv: AsmServerConfig)`
- Pasta monitorada: `{install_dir}/ShooterGame/Saved/SavedArks/`
- Arquivos: `.ark`, `.arktribe`, `.arkprofile`, `.bak`
- Botão "Backup agora" → cópia para `{install_dir}/ARKLAND_Backups/YYYY-MM-DD_HH-MM-SS/`
- Botão "Restaurar" → stop → substitui arquivos → restart

---

### 3.4 A9. Agendador de Tarefas TEK

**Arquivos:** novo `asm_scheduler_ui.py` + lógica em `app_tek.py`
**Prioridade:** 🟢 Baixa

Loop de tick em `app_tek.py` (chamado a cada 60s):
```python
def _asm_scheduler_tick(self) -> None:
    for srv in self.asm_config_manager.servers:
        if srv.enable_auto_restart and now.strftime("%H:%M") == srv.auto_restart_time:
            self.asm_server_manager.restart(srv.id, use_rcon=True)
        if srv.enable_auto_update_check:
            # verifica há quanto tempo desde a última checagem
            # chama AsmSteamCmd.check_update() se passou o intervalo
```

**Campos já existentes em `AsmServerConfig`:** `enable_auto_restart`, `auto_restart_time`, `restart_countdown_minutes`, `enable_auto_update_check`, `auto_update_check_minutes`.

---

### 3.5 A10. Workshop Browser TEK

**Arquivo:** `src/asm_ui/asm_workshop.py`
**Reutiliza:** `src/dialogs/mod_search_dialog.py`
**Prioridade:** 🟢 Baixa

Open: `open_asm_workshop(app, srv: AsmServerConfig)`
- Busca Steam Workshop por nome/ID
- Lista com thumbnail, nome, rating
- Botão ➕ Adicionar → adiciona à `srv.active_mods`
- Botão 📦 Baixar Todos → `AsmSteamCmd.download_mod()` para cada novo
- API: `https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/`

---

## 4. Ferramentas de Operação

### 4.1 S2.1. Gerenciador de Arquivos do Servidor

**Arquivo:** `src/asm_ui/asm_file_manager.py`
**Prioridade:** 🔴 Alta

Navegador de arquivos dentro do diretório de instalação do servidor:
- Breadcrumb + listagem com ícones por tipo (pasta, .ini, .ark, .dll, .txt)
- Atalhos rápidos: `GUS.ini`, `Game.ini`, `Logs`, `Plugins`, `SavedArks`, `Mods`
- Abrir arquivo de texto em editor inline
- Botão "Abrir no Explorer"

```python
SHORTCUTS = {
    "⚙ GUS.ini":   "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini",
    "🎮 Game.ini": "ShooterGame/Saved/Config/WindowsServer/Game.ini",
    "📋 Logs":     "ShooterGame/Saved/Logs/",
    "🔌 Plugins":  "ShooterGame/Binaries/Win64/ArkApi/Plugins/",
    "💾 Saves":    "ShooterGame/Saved/SavedArks/",
    "🧩 Mods":     "ShooterGame/Content/Mods/",
}
```

---

### 4.2 S2.2. CPU Affinity e Prioridade de Processo

**Arquivo:** `src/asm_engine/asm_server_manager.py`
**Prioridade:** 🟡 Média

Novos campos em `AsmServerConfig`:
```python
cpu_affinity_cores: List[int] = field(default_factory=list)  # [] = todos
process_priority:   str  = "normal"  # normal | above_normal | high | realtime
```

Após o subprocesso iniciar, ajusta via `psutil.Process(pid)`:
- `cpu_affinity(cores)`
- `nice(NORMAL_PRIORITY_CLASS | ABOVE_NORMAL | HIGH | REALTIME)`

---

### 4.3 S2.3. Verificador de Regras de Firewall

**Arquivo:** `src/asm_engine/asm_firewall.py`
**Prioridade:** 🟡 Média

```python
def check_firewall_rules(srv: AsmServerConfig) -> list[dict]: ...
def create_firewall_rules(srv: AsmServerConfig) -> None: ...
```

Usa `netsh advfirewall` para verificar/criar regras:
- Porta do servidor (`srv.server_port`, UDP)
- Query port (`srv.query_port`, UDP)
- RCON port (`srv.rcon_port`, TCP)

---

### 4.4 S2.4. Gráfico de Performance em Tempo Real

**Arquivo:** `src/asm_ui/asm_perf_chart.py`
**Prioridade:** 🟢 Baixa

Widget `AsmPerfChart` (CTkFrame → tkinter Canvas):
- Histórico de 60 pontos (últimos 5 min)
- Linhas: CPU%, RAM%, Players online
- Tick a cada 5s via `app.after(5000, self._tick)`
- Posicionado na parte inferior do server card (expandível via botão "📊")

---

## 5. Organização e Fluxo de Trabalho

### 5.1 S3.1. Pastas de Servidores (Grupos)

**Arquivo novo:** `src/asm_engine/asm_folder_manager.py`
**UI:** `src/asm_ui/asm_dashboard.py` + sidebar TEK
**Prioridade:** 🔴 Alta

```python
class AsmFolderManager:
    """Dados salvos em %APPDATA%\ARKLAND-ServerManager\asm_folders.json"""
    def get_folders(self) -> list[str]: ...
    def add_folder(self, name: str) -> None: ...
    def rename_folder(self, old: str, new: str) -> None: ...
```

Novo campo em `AsmServerConfig`: `folder: str = ""`
- Dashboard: server cards agrupados por pasta com header e botão "▶ Iniciar Todos"
- Sidebar: estrutura em árvore (pasta → servidores)
- Drag-and-drop entre pastas

---

### 5.2 S3.2. Ações em Lote (Bulk Actions)

**Arquivos:** `src/app_tek.py` + `src/asm_ui/asm_dashboard.py`
**Prioridade:** 🟡 Média

Toolbar de seleção múltipla:
```
[ ☐ Selecionar Todos ]  [ ▶ Iniciar Selecionados ]
[ ⏹ Parar Selecionados ]  [ 🔄 Reiniciar ]
```

Estado mantido em `app._asm_selected_servers: set[str]`
- `start_all()` / `stop_all()` via `threading.Thread` para cada
- `update_mods_selected()` → `AsmSteamCmd.download_mod()` paralelizado

---

### 5.3 S3.3. Presets de Configuração

**Arquivo:** `src/asm_engine/asm_preset_manager.py`
**Prioridade:** 🟡 Média

Salvo em `%APPDATA%\ARKLAND-ServerManager\presets/` como `.arkpreset`:
```json
{
  "name": "PvP Hardcore x5",
  "categories": ["players", "dinos", "rules"],
  "fields": { "xp_multiplier": 5.0, "enable_pvp": true, ... }
}
```

Categorias: `players`, `dinos`, `breeding`, `environment`, `structures`, `rules`, `full`
UI: botão "📋 Presets" no header do painel de configuração.

---

### 5.4 S3.4. Exportar / Importar / Clonar Perfil

**Arquivo:** `src/asm_engine/asm_config_manager.py`
**Prioridade:** 🟢 Baixa

```python
def export_server(self, server_id: str, path: str) -> None:   # → .arkprofile
def import_server(self, path: str) -> AsmServerConfig:       # ← .arkprofile (novo UUID)
def clone_server(self, server_id: str, new_name: str) -> AsmServerConfig:
    """Novo UUID, novo nome, install_dir vazio, preserva restante"""
```

Formato `.arkprofile`:
```json
{
  "version": "1.0",
  "created_at": "2026-06-08T...",
  "created_by": "ARKLAND-Multi 1.4.1",
  "server": { ...AsmServerConfig.to_dict()... }
}
```

---

## 6. Dados Avançados e Importação

### 6.1 S4.1. Tribe Log Viewer

**Arquivo:** `src/asm_ui/asm_tribe_log.py`
**Prioridade:** 🔴 Alta

Open: `open_asm_tribe_log(app, srv: AsmServerConfig)`
- Fonte: `{install_dir}/ShooterGame/Saved/Logs/TribeLog.log`
- Filtros: Kill, Estrutura, Admin, Tame, Todos
- Tail automático a cada 5s
- Destaca admin/wipe/ban em vermelho
- Exportar para `.txt` ou `.csv`

```
Day 123, 14:30:00: <NomeTribo> - Jogador destroyed an enemy structure!
Day 123, 14:31:05: <NomeTribo> - Jogador (Admin) Admin Command: ...
```

---

### 6.2 S4.2. Importar Servidor Existente

**Arquivo:** `src/asm_ui/asm_add_server_dialog.py`
**Depende de:** A4 (`read_ini`)
**Prioridade:** 🔴 Alta

Modo "Importar existente" no dialog de adicionar servidor:
```python
def import_existing_server(install_dir: str) -> AsmServerConfig:
    """1. Verifica ShooterGameServer.exe
        2. Lê GUS.ini → popula Administration, Rules, etc.
        3. Lê Game.ini → popula Players, Dinos, etc.
        4. Lê RunServer.cmd → detecta mapa, ports, args extras
        5. Retorna AsmServerConfig preenchido"""
```

Detecção automática de portas a partir do `RunServer.cmd`:
```
ShooterGameServer.exe TheIsland?listen?Port=7777?QueryPort=27015?MaxPlayers=70
```

---

### 6.3 S4.3. Editor Visual de Engramas

**Arquivo:** `src/asm_ui/asm_engram_editor.py`
**Prioridade:** 🟡 Média

Substituição do raw editor da seção 14 por interface visual:
- Tabela com colunas: Engram, Pontos, Nível, Esconder, Forçar
- Filtro de texto em tempo real
- Checkbox "Apenas modificados"
- Fonte de dados: `engrams.json` embutido com ~500 engramas
- Gera no Game.ini:
```ini
OverrideNamedEngramEntries=(EngramClassName="EngramEntry_Crossbow_C",EngramLevelRequirement=10,EngramPointsCost=9,bCanUnlockItem=True)
```

---

### 6.4 S4.4. Calculadora de Ascensão (Upgrade)

**Arquivo:** `src/asm_ui/asm_server_panel.py` — seção 16
**Prioridade:** 🟡 Média

Melhorias sobre a calculadora inline já existente:
1. Preview de tabela antes de aplicar (10 primeiras e últimas linhas)
2. Modo fórmula custom (expressão Python segura)
3. Presets de tabelas populares: Official (70 lvls), Hard (150), Custom
4. Mini gráfico da curva XP via tk Canvas

---

### 6.5 S4.5. Editor Visual de Spawner

**Arquivo:** `src/asm_ui/asm_spawner_editor.py`
**Prioridade:** 🟢 Baixa

Substituição do raw editor da seção 19:
- Árvore de containers (`DinoSpawnEntries_Island_C`)
- Entradas por container: blueprint, peso, limite
- Gera no Game.ini:
```ini
ConfigAddNPCSpawnEntriesContainer=(NPCSpawnEntriesContainerClassString="DinoSpawnEntries_Island_C",...)
```

---

## 7. Cloud, Monitoramento e IA

### 7.1 S5.1. Backup em Nuvem (S3 / Backblaze B2)

**Arquivo:** `src/asm_engine/asm_cloud_backup.py`
**Dependência nova:** `boto3`
**Prioridade:** 🟡 Média

```python
class AsmCloudBackup:
    def upload_backup(self, local_path: Path, server_name: str) -> None:
        """S3 key: arkland-backups/{server_name}/{data}/{arquivo}.zip"""
    def list_remote_backups(self, server_name: str) -> list[dict]: ...
    def download_backup(self, remote_key: str, local_path: Path) -> None: ...
```

**Novos campos em `AsmServerConfig`:**
```python
cloud_backup_enabled:   bool = False
cloud_backup_provider:  str  = "s3"   # s3 | b2 | gcs
cloud_backup_bucket:    str  = ""
cloud_backup_prefix:    str  = ""
```

**Credenciais:** armazenadas em `%APPDATA%\ARKLAND-ServerManager\credentials.json` —
**NUNCA** no `asm_servers.json` (evitar leak).
**Depende de:** A8 (backup local funcional primeiro).

---

### 7.2 S5.2. Assistente IA para Configuração

**Arquivo:** `src/asm_ui/asm_ai_assistant.py`
**Dependência nova:** `openai`
**Prioridade:** 🟢 Baixa

Chat contextual que conhece o config atual do servidor:
- "Configure para server PvE casual com breeding x10"
- Responde com sugestões de valores + botão `[✅ Aplicar sugestões]`

**Contexto injetado no prompt:**
```python
context = f"""
Servidor ARK: {srv.name}
Modo: {"PvP" if srv.enable_pvp else "PvE"}
Mapa: {srv.server_map}
Max Players: {srv.max_players}
XP: x{srv.xp_multiplier}, Taming: x{srv.taming_speed_multiplier}, ...
"""
```

---

### 7.3 S5.3. Monitor de Desempenho Avançado

**Arquivo:** `src/asm_ui/asm_monitor_window.py`
**Dependências:** `psutil` ✅
**Prioridade:** 🟡 Média

Dashboard de monitoramento em tempo real com 24h de histórico:
- CPU%, RAM%, Players online (últimas 24h)
- Alertas configuráveis: CPU > 80%, RAM > 90%, Players = 0 por 2h
- Ações de alerta: enviar Discord webhook, reiniciar servidor

---

## 8. Integração com Dashboard e Server Cards

### 8.1 B1. Botões Rápidos no Server Card

**Arquivo:** `src/asm_ui/asm_server_card.py`
**Prioridade:** 🟡 Média

Botões no footer do card (além de ▶ ⏹ 🔄):
- `🖥 RCON` → `open_asm_rcon_window(app, srv)`
- `👥 Players` → `open_asm_player_list(app, srv)`
- `💾 Backup` → `open_asm_save_restore(app, srv)`

**Condição:** `srv.rcon_enabled = True` **e** `status == RUNNING`.

---

### 8.2 B2. Indicadores Ricos de Status

**Arquivo:** `src/asm_ui/asm_server_card.py`
**Prioridade:** 🟡 Média

Novos indicadores atualizados automaticamente via `app.after()`:
- **👥 Players** — contagem via RCON `ListPlayers` a cada 30s
- **🕐 Uptime** — calculado a partir da mudança de status para RUNNING
- **💾 RAM** — `psutil.Process(pid).memory_info().rss`
- **📋 Versão** — lê de `{install_dir}/version.txt`

Formato:
```
● ONLINE  |  👥 12/70  |  🕐 2h 34min  |  RAM: 4.2 GB
```

---

## 9. Ordem de Execução Recomendada

```
A1  → A2  → A3  → A4  → A5
         ↓
        A6  +  A7  (podem ir em paralelo)
         ↓
        A8  → A9  → A10
         ↓
S2.1  → S2.2  → S2.3  → S2.4
         ↓
S3.1  → S3.2  → S3.3  → S3.4
         ↓
S4.1  → S4.2  → S4.3  → S4.4  → S4.5
         ↓
S5.1  → S5.2  → S5.3
         ↓
B1  +  B2  (integração final com dashboard)
```

**Caminho crítico:** A1 → A2 → A3 → A4 → A5
**A1 é crítico** — sem ele, Per-Level Stats nunca chegam ao servidor real.
**A2 + A3** liberam o fluxo completo de instalação.
**A4** é pré-requisito para S4.2 (importar servidor existente lê INI).

---

## 10. Referências Técnicas

### 10.1 Tabela de Dependências por Feature

| Feature | Python existente | Dependências externas | Requer A2+ |
|---|---|---|---|
| A1 — per_level INI | `asm_ini_manager.py` | nenhuma | Não |
| A2 — SteamCMD | `asm_steamcmd.py` (novo) | nenhuma | — |
| A3 — Botões install | `asm_server_panel.py` | nenhuma | A2 |
| A4 — read_ini | `asm_ini_manager.py` | nenhuma | Não |
| A5 — restart/RCON | `asm_server_manager.py` + `rcon_client.py` | nenhuma | Não |
| A6 — RCON Window | `asm_rcon_window.py` (novo) | `rcon_client.py` ✅ | A5 |
| A7 — Player List | `asm_player_list.py` (novo) | `rcon_client.py` ✅ | A5 |
| A8 — Save Restore | `asm_save_restore.py` (novo) | nenhuma | Não |
| A9 — Scheduler | `app_tek.py` + `asm_scheduler_ui.py` | nenhuma | Não |
| A10 — Workshop | `asm_workshop.py` | `mod_search_dialog.py` ✅ | A2 |
| S2.1 — File Manager | `asm_file_manager.py` (novo) | nenhuma | Não |
| S2.2 — CPU Affinity | `asm_server_manager.py` | psutil ✅ | Não |
| S2.3 — Firewall | `asm_firewall.py` (novo) | subprocess (netsh) ✅ | Não |
| S2.4 — Perf Chart | `asm_perf_chart.py` (novo) | psutil ✅ | Não |
| S3.1 — Pastas | `asm_folder_manager.py` (novo) | nenhuma | Não |
| S3.2 — Bulk Actions | `app_tek.py` + `asm_dashboard.py` | nenhuma | Não |
| S3.3 — Presets | `asm_preset_manager.py` (novo) | nenhuma | Não |
| S3.4 — Export/Import | `asm_config_manager.py` | nenhuma | Não |
| S4.1 — Tribe Log | `asm_tribe_log.py` (novo) | nenhuma | Não |
| S4.2 — Import Existente | `asm_add_server_dialog.py` + A4 | nenhuma | A4 |
| S4.3 — Engram Editor | `asm_engram_editor.py` (novo) | engrams.json embutido | Não |
| S4.4 — XP Calc | `asm_server_panel.py` | nenhuma | Não |
| S4.5 — Spawner Visual | `asm_spawner_editor.py` (novo) | nenhuma | Não |
| S5.1 — Cloud Backup | `asm_cloud_backup.py` (novo) | boto3 (novo) | A8 |
| S5.2 — IA Assistant | `asm_ai_assistant.py` (novo) | openai (novo) | Não |
| S5.3 — Monitor | `asm_monitor_window.py` (novo) | psutil ✅ | Não |

### 10.2 Formato da Linha de Comando TEK (Fiel ao ASM)

```
{exe} {map_id}?listen?Port={port}?QueryPort={qport}?MaxPlayers={max_players}
    [?AltSaveDirectoryName={dir}]
    [?MultiHome={ip}]
    [?clusterid={cluster_id}]
    [?ClusterDirOverride={cluster_dir}]
    -nosteamclient -game -server -log
    [-ForceAllowCaveFlyers]
    [-exclusivejoin]
    [{additional_args}]
```

**Nunca inclui na CLI** (vai apenas no INI):
- `?SessionName=` → `[SessionSettings] SessionName`
- `?ServerPassword=` → `[ServerSettings] ServerPassword`
- `?ServerAdminPassword=` → `[ServerSettings] ServerAdminPassword`
- `?RCONEnabled=` → `[ServerSettings] RCONEnabled`
- `?RCONPort=` → `[ServerSettings] RCONPort`
- `?GameModIds=` → `[ServerSettings] ActiveMods`

### 10.3 Variáveis de Ambiente Seguras para o Servidor

```python
env = os.environ.copy()
env.pop("__COMPAT_LAYER", None)   # evita shim → crash ArkShopUI
meipass = getattr(sys, "_MEIPASS", None)
if meipass:
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep)
        if not p.startswith(meipass) and p.strip()
    )
```

### 10.4 Causa Raiz do Crash ArkShopUI (Referência Histórica)

> O crash `ArkShopUI.dll!CheckOnTimerCallbacks` (~5 min após jogador conectar) foi resolvido em **26/05/2026**. A causa raiz identificada foi **conflito de banco MySQL entre ArkShop e Permissions** (ambos usando `MysqlDB: "arkshop"`).
> Fix definitivo: alterar `Permissions/config.json → MysqlDB: "ark_permission"`.
> As correções T1–T14 (remoção de `_MEIPASS`, `__COMPAT_LAYER`, `.mod` files, `?GameModIds=`, etc.) foram investigações paralelas que melhoraram a estabilidade geral, mas não eram a causa raiz do crash.

---

> **Nota:** Este plano é a fonte de verdade única. Os arquivos `ROADMAP.md`, `IMPROVEMENTS_PLAN.md` e `OPTIMIZATION_PLAN.md` serão removidos após aprovação deste documento para evitar divergência de especificações.
