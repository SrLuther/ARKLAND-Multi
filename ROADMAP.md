# ARKLAND-Multi — Roadmap & Planejamento Técnico Completo

> Documento gerado em: **30/05/2026**
> Versão atual do produto: **1.3.57**
> Modo ativo: **TEK** (reimplementação do ASM em Python/CustomTkinter)
> Autor do planejamento: GitHub Copilot (Claude Sonnet 4.6)

---

## Índice

1. [Estado Atual da Base de Código](#1-estado-atual-da-base-de-código)
2. [Arquitetura TEK — O que foi implementado](#2-arquitetura-tek--o-que-foi-implementado)
3. [Fase A — Pendências TEK Core (importação do ASM)](#3-fase-a--pendências-tek-core-importação-do-asm)
4. [Fase B — Janelas Auxiliares TEK (ASM-fiel)](#4-fase-b--janelas-auxiliares-tek-asm-fiel)
5. [Sprint 2 — Ferramentas de Operação](#5-sprint-2--ferramentas-de-operação)
6. [Sprint 3 — Organização e Fluxo de Trabalho](#6-sprint-3--organização-e-fluxo-de-trabalho)
7. [Sprint 4 — Dados Avançados e Importação](#7-sprint-4--dados-avançados-e-importação)
8. [Sprint 5 — Cloud e IA](#8-sprint-5--cloud-e-ia)
9. [Referências Técnicas](#9-referências-técnicas)

---

## 1. Estado Atual da Base de Código

### 1.1 Stack Técnico

| Item | Valor |
|---|---|
| Linguagem | Python 3.12.13 (`.venv/`) |
| UI | CustomTkinter + tkinter |
| Empacotamento | PyInstaller 6.20.0 onefile → `dist/ARKLAND-Multi.exe` |
| Instalador | Inno Setup (`setup.iss`) |
| Persistência | JSON em `%APPDATA%\ARKLAND-ServerManager\` |
| Release | `_release.ps1 -Version "X.Y.Z"` → git push + GitHub Release API |
| Tema TEK | `get_theme("tek")` — `accent=#22c55e`, `bg=#060d14`, `card_bg=#0d1b2a` |

### 1.2 Estrutura de Diretórios

```
src/
├── app_tek.py                   # Classe principal ARKServerManagerApp (TEK-only)
├── app.py                       # PRIMITIVE (legado, não usado no build TEK)
├── breeding_calculator.py       # open_breeding_calculator(parent, gs, widgets, on_apply)
├── config_manager.py            # AppConfig — configurações globais
├── server_config.py             # ServerConfig PRIMITIVE (legado)
├── server_manager.py            # ServerManager PRIMITIVE (legado)
├── ark_ini.py                   # IniManager PRIMITIVE (legado)
│
├── asm_engine/                  # Engine backend TEK
│   ├── asm_server_config.py     # AsmServerConfig dataclass (~300 campos)
│   ├── asm_ini_manager.py       # INI_MAP declarativo + write_ini() + build_launch_args()
│   ├── asm_server_manager.py    # AsmServerManager — start/stop/restart/monitor
│   └── asm_config_manager.py   # AsmConfigManager — CRUD JSON
│
├── asm_ui/                      # UI TEK
│   ├── asm_dashboard.py         # Dashboard — TopBar, stats cards, scroll de server cards
│   ├── asm_server_card.py       # Card individual com rename, cor, tags, ⚡ no-mods
│   ├── asm_server_panel.py      # Painel 24 seções — nav lateral + conteúdo dinâmico
│   └── asm_add_server_dialog.py # Dialog "Adicionar Servidor TEK"
│
├── pages/                       # Módulos de páginas PRIMITIVE (~130 arquivos)
├── dialogs/                     # Dialogs PRIMITIVE
└── ui_constants.py              # get_theme() — todos os temas e constantes de cor
```

### 1.3 Persistência de Dados

| Arquivo | Caminho | Formato |
|---|---|---|
| Servidores TEK | `%APPDATA%\ARKLAND-ServerManager\asm_servers.json` | JSON — lista de `AsmServerConfig.to_dict()` |
| Config global | `%APPDATA%\ARKLAND-ServerManager\config.json` | JSON — `ConfigManager` |
| GameUserSettings.ini | `{install_dir}\ShooterGame\Saved\Config\WindowsServer\GameUserSettings.ini` | INI |
| Game.ini | `{install_dir}\ShooterGame\Saved\Config\WindowsServer\Game.ini` | INI |

### 1.4 Paths Críticos do ARK

```python
exe     = "{install_dir}/ShooterGame/Binaries/Win64/ShooterGameServer.exe"
gus_ini = "{install_dir}/ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini"
game_ini= "{install_dir}/ShooterGame/Saved/Config/WindowsServer/Game.ini"
```

### 1.5 Referência ASM Importada

**Path local ASM source:** `C:\Users\Ciano\Documents\_asm_src\ARK Server Manager\`

| Arquivo ASM (C#) | Equivalente Python | Status |
|---|---|---|
| `Lib/ServerProfile.cs` | `asm_server_config.py` | ✅ Completo (~300 campos) |
| `Lib/ServerRuntime.cs` | `asm_server_manager.py` | ✅ Start/stop/monitor |
| `Lib/ServerApp.cs` | `asm_steamcmd.py` | ❌ Não implementado |
| `Lib/ServerRCON.cs` | `asm_rcon_window.py` | ❌ Não implementado |
| `Lib/ServerManager.cs` | `asm_dashboard.py` | ✅ Dashboard completo |
| `Windows/ServerSettingsControl.xaml` | `asm_server_panel.py` | ✅ 24 seções |
| `Windows/RCONWindow.xaml` | — | ❌ Não implementado |
| `Windows/PlayerListWindow.xaml` | — | ❌ Não implementado |
| `Windows/WorkshopFilesWindow.xaml` | — | ❌ Não implementado |
| `Windows/WorldSaveRestoreWindow.xaml` | — | ❌ Não implementado |
| `Windows/ScheduledTasksWindow.xaml` | — | ❌ Não implementado |

---

## 2. Arquitetura TEK — O que foi implementado

### 2.1 AsmServerConfig — `src/asm_engine/asm_server_config.py`

Dataclass com **306 campos** mapeando o `ServerProfile.cs` do ASM original.

#### Categorias de campos

| Categoria | Campos | Destino INI |
|---|---|---|
| **Identificação** | `id`, `name` | Apenas JSON |
| **Localização** | `install_dir`, `server_exe` | Apenas JSON |
| **Administration** | 25 campos (sessão, rede, RCON, mods, saves, branch, cluster) | GUS + CLI |
| **Rules** | 22 campos (PvP/PvE, dificuldade, tribos, downloads) | GUS + Game |
| **ChatAndNotifications** | 4 campos | GUS |
| **HudAndVisuals** | 6 campos | GUS |
| **Players** | 11 campos (XP, dano, resistência, drains) | GUS |
| **Dinos** | 24 campos (dano, resist, taming, breeding, imprinting) | GUS + Game |
| **Environment** | 15 campos (dia/noite, spoiling, recursos, temperatura) | GUS + Game |
| **Structures** | 14 campos (dano, decay, limites, torretas) | GUS + Game |
| **Administration Extras** | 10 campos (tribos, extinção, respawn dinos) | GUS + Game |
| **Rules Extras** | 28 campos (PvP respawn, auto-PvE, recipes, stasis, alianças) | GUS + Game |
| **Dinos Extras** | 13 campos (food/stamina drain, max pessoal, torpor) | GUS + Game |
| **Environment Extras** | 12 campos (XP por tipo, ovos, fezes, recursos) | Game |
| **Structures Extras** | 10 campos (PvP decay, zona PvP, fast decay, torretas) | GUS + Game |
| **Engrams** | 3 campos (`only_allow_specified`, `auto_unlock_all`, `engram_entries_raw`) | Game |
| **Levels** | 2 campos (`player_level_stats_raw`, `dino_level_stats_raw`) | Game |
| **Per-Level Stats** | 5 listas de 12 floats (player, wild, tamed, tamed_add, tamed_affinity) | Game |
| **Substituições Avançadas** | 5 raw strings (crafting, stack, spawner, supply crate, transfer) | Game / GUS |
| **Arquivos do Servidor** | 3 listas (admin_ids, whitelist_ids, exclusive_join_ids) | AllowedCheaterSteamIDs.txt, etc. |
| **Gerenciamento Automático** | 6 campos (auto-restart, auto-update, notify discord) | Apenas JSON |
| **Discord Bot** | 5 campos (webhook_url, notificações de eventos) | Apenas JSON |
| **PGM** | 3 campos (pgm_enabled, pgm_name, pgm_terrain_string) | Game |
| **Custom INI livre** | 3 raw strings (GUS, Game, Engine) | Direto nos INIs |
| **Metadados** | `notes`, `color`, `tags` | Apenas JSON |

#### Per-Level Stats (índices 0–11)

```python
_STAT_INDEX = [
    # idx  stat              INI_key_player            INI_key_dino_wild
    (0,  "Vida",            "PerLevelStatsMultiplier_Player[0]",  "PerLevelStatsMultiplier_DinoWild[0]"),
    (1,  "Stamina",         "PerLevelStatsMultiplier_Player[1]",  "PerLevelStatsMultiplier_DinoWild[1]"),
    (2,  "Torpor",          "PerLevelStatsMultiplier_Player[2]",  "PerLevelStatsMultiplier_DinoWild[2]"),
    (3,  "Oxigênio",        "PerLevelStatsMultiplier_Player[3]",  "PerLevelStatsMultiplier_DinoWild[3]"),
    (4,  "Comida",          "PerLevelStatsMultiplier_Player[4]",  "PerLevelStatsMultiplier_DinoWild[4]"),
    (5,  "Água",            "PerLevelStatsMultiplier_Player[5]",  "PerLevelStatsMultiplier_DinoWild[5]"),
    (6,  "Temperatura",     "PerLevelStatsMultiplier_Player[6]",  "PerLevelStatsMultiplier_DinoWild[6]"),
    (7,  "Peso",            "PerLevelStatsMultiplier_Player[7]",  "PerLevelStatsMultiplier_DinoWild[7]"),
    (8,  "Dano Corpo",      "PerLevelStatsMultiplier_Player[8]",  "PerLevelStatsMultiplier_DinoWild[8]"),
    (9,  "Velocidade",      "PerLevelStatsMultiplier_Player[9]",  "PerLevelStatsMultiplier_DinoWild[9]"),
    (10, "Fortitude",       "PerLevelStatsMultiplier_Player[10]", "PerLevelStatsMultiplier_DinoWild[10]"),
    (11, "Crafting",        "PerLevelStatsMultiplier_Player[11]", "PerLevelStatsMultiplier_DinoWild[11]"),
]
```

Padrões dos campos:
- `per_level_player[i]` = `1.0` (jogador — pts por nível aplicado)
- `per_level_dino_wild[i]` = `1.0` (dino selvagem)
- `per_level_dino_tamed[i]` = `1.0` (dino domado base)
- `per_level_dino_tamed_add[i]` = `0.14` (bônus fixo por nível pós-tame)
- `per_level_dino_tamed_affinity[i]` = `0.44` (bônus de afinidade pós-tame)

### 2.2 INI_MAP — `src/asm_engine/asm_ini_manager.py`

Sistema declarativo de mapeamento campo Python ↔ chave INI. ~150 entradas.

```python
INI_MAP: dict[str, tuple] = {
    # (campo_python): (arquivo, seção, chave_ini, opções)
    "session_name": ("GUS", "SessionSettings", "SessionName", {}),
    # ...
    "enable_pvp":   ("GUS", "ServerSettings", "ServerPVE", {"inverted": True}),
    # ...
}
```

**Opções disponíveis:**
- `"inverted": True` — grava `not valor` (ex: `ServerPVE = not enable_pvp`)
- `"conditional_on": "campo"` — só grava se `getattr(cfg, campo)` for truthy
- `"always_write": True` — grava mesmo que seja o valor padrão
- `"use_field": "campo"` — usa o valor de outro campo (ex: `ban_list_url`)
- `"list_sep": ","` — separador para `List[str]`
- `"cli_only": True` — não vai ao INI, apenas na linha de comando

**`write_ini(cfg)`** → escreve GUS + Game.ini. Injeta raw strings (`custom_gus_ini_raw`, `custom_game_ini_raw`, `engram_entries_raw`, etc.) direto no arquivo.

**`build_launch_args(cfg)`** → monta lista de argumentos CLI fiel ao ASM:
```
TheIsland?listen?Port=7777?QueryPort=27015?MaxPlayers=70
    -nosteamclient -game -server -log
```
Nunca coloca `?SessionName=`, `?ServerPassword=`, `?RCONPort=` na CLI — esses vão apenas no INI, diferente do modo PRIMITIVE antigo que duplicava.

### 2.3 AsmServerManager — `src/asm_engine/asm_server_manager.py`

| Método | Descrição |
|---|---|
| `start(cfg, on_done)` | Thread → `write_ini()` → `Popen` → monitor de processo |
| `stop(server_id, on_done)` | `proc.terminate()` → wait 10s → `proc.kill()` |
| `get_status(server_id)` | `ASM_STATUS_STOPPED / STARTING / RUNNING / STOPPING / CRASHED` |
| `get_instance(server_id)` | Retorna `AsmServerInstance` com `.pid`, `.is_running` |

Monitor de processo: thread daemon que chama `proc.poll()` a cada 5s; se o processo encerrar inesperadamente, muda status para `ASM_STATUS_CRASHED` e dispara `on_status_change`.

### 2.4 AsmConfigManager — `src/asm_engine/asm_config_manager.py`

```
%APPDATA%\ARKLAND-ServerManager\asm_servers.json
```
- `load()` — carrega a lista ao iniciar
- `save()` — escrita atômica via `.tmp` → `replace()`
- `add_server(srv)` / `update_server(srv)` / `remove_server(id)` — CRUD
- `from_dict()` filtra campos desconhecidos → **retrocompatível com dados antigos**

### 2.5 Dashboard TEK — `src/asm_ui/asm_dashboard.py`

- **TopBar** — saudação por horário + contagem de servidores online + botão "＋ Novo Servidor"
- **Stats grid** — 5 cards: Total · Online · Offline · CPU% · RAM%
- **Grid de server cards** — scroll de `asm_server_card.py`

### 2.6 Server Card (Sprint 1) — `src/asm_ui/asm_server_card.py`

Funcionalidades implementadas:

| Feature | Descrição |
|---|---|
| **Cor customizada** | Borda colorida via `srv.color` (hex) — sobrepõe cor de status |
| **Tags** | Chips coloridos abaixo do nome (até 4 visíveis), lista em `srv.tags` |
| **Rename inline** | Double-click no nome → entry in-place → Enter/FocusOut salva → `asm_config_manager.save()` → `_rebuild_server_sidebar()` |
| **⚡ Start sem mods** | Aparece quando `srv.active_mods` e servidor não busy → chama `_asm_start_server(srv, no_mods=True)` |
| **Port conflict check** | `_check_port_conflicts(srv)` usa `socket.connect_ex` antes do start; alerta se porta ocupada |

### 2.7 Painel de Configuração — `src/asm_ui/asm_server_panel.py`

**24 seções** na nav lateral. Estado: todas com builder implementado.

| # | Seção | Conteúdo | Status |
|---|---|---|---|
| 1 | Administração | Mapa (picker visual + campo manual), portas, senhas, RCON, mods, MOTD, saves, branch, cluster, args extras, personalização de card | ✅ Completo |
| 2 | Gerenciamento Automático | Auto-restart (hora + countdown), auto-update check, notify Discord | ✅ Completo |
| 3 | Detalhes do Discord Bot | Webhook URL, notificações start/stop/join/leave | ✅ Completo |
| 4 | Detalhes do Servidor | Notas livres do servidor | ✅ Completo |
| 5 | Regras | Hardcore/PvP/PvE, dificuldade, tribe size, tributes, diseases, auto-PvE, extras | ✅ Completo |
| 6 | Transferências / Tributo | Downloads/Uploads de survivors, items, dinos; expiração de tributos | ✅ Completo |
| 7 | Bate-papo e Notificações | Voice chat global/proximity, notificações join/leave | ✅ Completo |
| 8 | HUD e Visuais | Crosshair, HUD, 3ª pessoa, mapa, damage text, hit markers, gamma | ✅ Completo |
| 9 | Configurações do Jogador | Multiplicadores XP, dano, resistência, drains; per-level stats grid 12 atributos | ✅ Completo |
| 10 | Configurações do Dino | Dano, resist, max tamed, count, taming, food/stamina drain; per-level stats grid 4 colunas | ✅ Completo |
| 11 | Reprodução | Mating, egg hatch, mature speed, food/cuddle/imprint; botão Calculadora Breeding | ✅ Completo |
| 12 | Meio Ambiente | Harvest, recursos, ciclo dia/noite, spoiling, temperatura, clima, agricultura | ✅ Completo |
| 13 | Estruturas | Resistência, dano, limites, decay PvE/PvP, torretas, platform saddle | ✅ Completo |
| 14 | Engramas | Options (only_allow, auto_unlock) + raw editor `OverrideNamedEngramEntries` | ✅ Completo |
| 15 | Arquivos do Servidor | Textboxes admin IDs, whitelist IDs, exclusive join IDs | ✅ Completo |
| 16 | Progressões de Nível | Gerador rápido (max_lvl, xp_base, mult, engrams/lvl) + raw textbox LevelExperienceRampOverrides + gerador dino | ✅ Completo |
| 17 | Substituições de Crafting | Editor INI 2 painéis (seções + chave/valor) para `ConfigOverrideItemCraftingCosts` | ✅ Completo |
| 18 | Substituições de Stack | Editor INI 2 painéis para `ConfigOverrideItemMaxQuantity` | ✅ Completo |
| 19 | Substituições de Spawner | Editor INI 2 painéis para `ConfigAddNPCSpawnEntriesContainer` | ✅ Completo |
| 20 | Substituições de Supply Crate | Editor INI 2 painéis para `ConfigOverrideSupplyCrateItems` | ✅ Completo |
| 21 | Impedir Transferências | Raw textbox `PreventTransferForClassNames` | ✅ Completo |
| 22 | Custom GameUserSettings.ini | Raw textbox livre injetado direto no GUS.ini | ✅ Completo |
| 23 | Custom Game.ini | Raw textbox livre injetado direto no Game.ini | ✅ Completo |
| 24 | ARK Procedural (PGM) | pgm_enabled toggle, PGMapName, PGTerrainPropertiesString raw | ✅ Completo |

**`_save(app, srv)`** — fluxo de salvamento:
1. Varre `vars_ref` (StringVars + IntVars) e escreve via `setattr` com cast de tipo
2. Handlers especiais: mods (textbox linhas), MOTD, notes, admin/whitelist/exclusive IDs
3. `_raw_*` prefixo → grava no campo de mesmo nome sem prefixo
4. `_tags_csv` → split por `,` → `srv.tags`
5. `_pls` dict → `List[float]` para cada `per_level_*`
6. `app.asm_config_manager.update_server(srv)` → salva JSON
7. `app._asm_refresh_dashboard()` → re-renderiza cards

### 2.8 Breeding Calculator — `src/breeding_calculator.py`

```python
open_breeding_calculator(parent, gs, widgets, on_apply)
```

- `gs`: `AsmServerConfig` — lê `baby_mature_speed_multiplier`, `egg_hatch_speed_multiplier`, `mating_interval_multiplier`, `baby_cuddle_interval_multiplier`
- `widgets`: dict `{"gs_{campo}": StringVar}` — atualizado ao aplicar
- `on_apply`: callback após aplicar multiplicadores
- Calcula tempos em tabela por criatura (Rex, Quetzal, etc.) com base nos multiplicadores
- Botão "Aplicar ao Servidor" → `setattr(gs, attr, val)` + `widget.set(val)` + `on_apply()`

**Acesso no painel:** botão na seção 11 — Reprodução:
```python
def _open_calc():
    from ..breeding_calculator import open_breeding_calculator
    widgets = {f"gs_{k}": v for k, v in vars_ref.items() if not k.startswith("_")}
    open_breeding_calculator(sf, srv, widgets, on_apply)
```

### 2.9 Mapa Picker — Seção Administração

**12 mapas oficiais** (Volcano e Caballus removidos — são mods):

| Mapa | ID Interno |
|---|---|
| The Island | `TheIsland` |
| Scorched Earth | `ScorchedEarth_P` |
| Aberration | `Aberration_P` |
| Extinction | `Extinction` |
| Genesis Part 1 | `Genesis` |
| Genesis Part 2 | `Gen2` |
| The Center | `TheCenter` |
| Ragnarok | `Ragnarok` |
| Valguero | `Valguero_P` |
| Crystal Isles | `CrystalIsles` |
| Lost Island | `LostIsland` |
| Fjordur | `Fjordur` |

**Campo manual** — abaixo do botão do mapa: CTkEntry com a mesma `map_var` StringVar, permite digitar qualquer mapa não listado (ex: `Svartalfheim`, `PrimitivePlus_P`).

---

## 3. Fase A — Pendências TEK Core (importação do ASM)

### A1. Per-Level Stats → INI_MAP + write_ini

**Prioridade:** 🔴 Alta
**Arquivo:** `src/asm_engine/asm_ini_manager.py`

Os campos `per_level_*` são arrays indexados no ARK e **não** seguem o padrão `key=value` do INI_MAP. Requerem escrita especial em `write_ini()`.

**Formato no Game.ini** (seção `/Script/ShooterGame.ShooterGameMode`):
```ini
[/Script/ShooterGame.ShooterGameMode]
PerLevelStatsMultiplier_Player[0]=2.0
PerLevelStatsMultiplier_Player[1]=1.5
...
PerLevelStatsMultiplier_Player[11]=1.0
PerLevelStatsMultiplier_DinoWild[0]=1.0
...
PerLevelStatsMultiplier_DinoTamed[0]=1.0
...
PerLevelStatsMultiplier_DinoTamed_Add[0]=0.2
...
PerLevelStatsMultiplier_DinoTamed_Affinity[0]=0.5
...
```

**O que precisa ser implementado em `write_ini()`:**
```python
# Após o loop principal do INI_MAP, antes de escrever os arquivos:
PERLEVEL_MAP = [
    ("per_level_player",           "PerLevelStatsMultiplier_Player"),
    ("per_level_dino_wild",        "PerLevelStatsMultiplier_DinoWild"),
    ("per_level_dino_tamed",       "PerLevelStatsMultiplier_DinoTamed"),
    ("per_level_dino_tamed_add",   "PerLevelStatsMultiplier_DinoTamed_Add"),
    ("per_level_dino_tamed_affinity","PerLevelStatsMultiplier_DinoTamed_Affinity"),
]
game_mode_sec = game.setdefault(_GAME_MODE_SECTION, {})
for field_attr, ini_prefix in PERLEVEL_MAP:
    values: list = getattr(cfg, field_attr, [])
    for idx, val in enumerate(values):
        game_mode_sec[f"{ini_prefix}[{idx}]"] = _format_value(val)
```

**Leitura de volta** também precisa ser implementada em `read_ini()` (função ainda não existe — ver A5).

**Dependências:** nenhuma
**Impacto:** sem isso, os valores de per-level stats são salvos no JSON mas nunca gravados no Game.ini do servidor.

---

### A2. `asm_steamcmd.py` — Install/Update via SteamCMD

**Prioridade:** 🔴 Alta
**Arquivo a criar:** `src/asm_engine/asm_steamcmd.py`
**Referência ASM:** `Lib/ServerApp.cs`

O ASM usa o SteamCMD para instalar e atualizar servidores. No modo TEK, isso está **ausente** — o botão de instalação no painel Administração não faz nada ainda.

**Funcionalidades a implementar:**

```python
class AsmSteamCmd:
    """Gerencia install/update/validate de servidores ARK via SteamCMD."""

    APP_ID = "376030"  # ARK: Survival Evolved dedicated server

    def __init__(self, steamcmd_path: str, on_log: Callable[[str], None] = None) -> None: ...

    def install_server(self, install_dir: str, branch: str = "",
                       branch_password: str = "",
                       on_done: Callable[[bool, str], None] = None) -> None:
        """
        Instala ou atualiza o servidor ARK.
        Comando: steamcmd.exe +login anonymous
                              +force_install_dir <install_dir>
                              +app_update 376030 [[-beta <branch>] [-betapassword <pwd>]]
                              +quit
        """

    def validate_server(self, install_dir: str) -> None:
        """app_update 376030 validate"""

    def get_steamcmd_path(self) -> Optional[str]:
        """Localiza steamcmd.exe:
        1. Registro: HKCU\Software\Valve\Steam\SteamPath\steamapps\common\ARK Survival Evolved Dedicated Server\steamcmd
        2. Padrão: C:\steamcmd\steamcmd.exe
        3. Configurado pelo usuário
        """

    def download_mod(self, mod_id: str, install_dir: str) -> None:
        """
        Comando: steamcmd.exe +login anonymous
                              +workshop_download_item 346110 <mod_id>
                              +quit
        Copia de: Steam\steamapps\workshop\content\346110\<mod_id>\
        Para: <install_dir>\ShooterGame\Content\Mods\<mod_id>\
        """
```

**Chamadas no painel:**
- Seção 1 (Administração) → botão "⬇ Instalar / Atualizar Servidor"
- Seção 1 → botão "📦 Baixar Mods"
- Seção 2 (Gerenciamento Automático) → `enable_auto_update_check` já está no config

**Dependências:** `src/asm_engine/asm_config_manager.py`, `src/asm_engine/asm_server_config.py`
**Caminho SteamCMD padrão:** `C:\steamcmd\steamcmd.exe` ou localizado no registro do Steam
**ARK Workshop ID:** `346110` (para mods)
**ARK Server App ID:** `376030`

---

### A3. Botões de Ação no Painel Administração

**Prioridade:** 🔴 Alta
**Arquivo:** `src/asm_ui/asm_server_panel.py` — `_build_administracao()`
**Depende de:** A2 (asm_steamcmd.py)

Adicionar na seção Administração (após a seção de mods, row ~30+):

```python
# Botões de ação do servidor
_section_label(sf, "Ações do Servidor", row_n, accent)
ctk.CTkButton(sf, text="⬇  Instalar / Atualizar Servidor",  command=_do_install, ...)
ctk.CTkButton(sf, text="📦  Baixar / Atualizar Mods",        command=_do_mods, ...)
ctk.CTkButton(sf, text="✅  Validar Arquivos",               command=_do_validate, ...)
```

Callback `_do_install`:
```python
def _do_install():
    from ..asm_engine.asm_steamcmd import AsmSteamCmd
    sc = AsmSteamCmd(app.config_manager.steamcmd_path, on_log=_log_to_panel)
    sc.install_server(srv.install_dir, srv.branch_name, srv.branch_password,
                      on_done=lambda ok, msg: app.after(0, lambda: _show_result(ok, msg)))
```

---

### A4. `read_ini()` — Leitura do INI → AsmServerConfig

**Prioridade:** 🟡 Média
**Arquivo:** `src/asm_engine/asm_ini_manager.py`

Atualmente `write_ini()` existe mas `read_ini()` **não está implementado**. O botão "Importar do INI" no painel não funciona ainda.

**Assinatura esperada:**
```python
def read_ini(cfg: AsmServerConfig) -> None:
    """Lê GameUserSettings.ini e Game.ini e popula cfg.
    Inverte os campos com inverted=True.
    Converte tipos (str→bool, str→int, str→float).
    Lê PerLevelStatsMultiplier_Player[N] → cfg.per_level_player[N].
    """
```

**Lógica de inversão:**
```python
# Para campos com "inverted": True
# INI: ServerPVE=True → enable_pvp = False
# INI: ServerPVE=False → enable_pvp = True
```

**Leitura de per-level stats:**
```python
import re
for line_key, line_val in game_mode_entries:
    m = re.match(r'PerLevelStatsMultiplier_(\w+)\[(\d+)\]', line_key)
    if m:
        prefix, idx = m.group(1), int(m.group(2))
        attr = PERLEVEL_INI_TO_FIELD.get(prefix)
        if attr:
            lst = getattr(cfg, attr)
            if idx < len(lst):
                lst[idx] = float(line_val)
```

**Botão "Importar do INI" a adicionar** na seção 22/23 (Custom GUS/Game) do painel.

---

### A5. `restart()` + RCON `DoExit` no AsmServerManager

**Prioridade:** 🟡 Média
**Arquivo:** `src/asm_engine/asm_server_manager.py`

```python
def restart(self, server_id: str,
            use_rcon: bool = True,
            on_done: Optional[Callable[[bool, str], None]] = None) -> None:
    """
    1. Se use_rcon=True: envia RCON 'DoExit' para desligar graciosamente
    2. Aguarda até status=STOPPED (timeout 60s)
    3. Chama self.start(cfg, on_done)
    """
```

**Integração com app_tek.py:**
```python
def _asm_restart_server(self, srv: AsmServerConfig) -> None:
    self.asm_server_manager.restart(srv.id, use_rcon=True,
                                    on_done=lambda ok, msg: ...)
```

---

### A6. `asm_rcon_window.py` — Console RCON TEK

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_ui/asm_rcon_window.py`
**Referência ASM:** `Windows/RCONWindow.xaml`
**Depende de:** `src/rcon_client.py` (já existe no PRIMITIVE)

O `rcon_client.py` já implementa o protocolo RCON completo:
```python
# src/rcon_client.py — já existente
class RconClient:
    def connect(self, host: str, port: int, password: str) -> None: ...
    def send_command(self, command: str) -> str: ...
    def disconnect(self) -> None: ...
```

O que falta é a **janela UI**:
```python
def open_asm_rcon_window(app, srv: AsmServerConfig) -> None:
    """
    Abre janela RCON para o servidor TEK.
    - Conecta automaticamente usando srv.server_ip, srv.rcon_port, srv.admin_password
    - Campo de input de comandos
    - Área de log com resposta
    - Botões: Conectar / Desconectar / Limpar
    - Auto-scroll para baixo
    - Histórico de comandos (↑↓ navega)
    """
```

**Layout esperado:**
- TopBar com status de conexão (✅ verde / ❌ vermelho)
- Área de log (CTkTextbox, readonly, fundo escuro, fonte Consolas)
- Campo de input + botão "Enviar"
- Botões de atalho: `ListPlayers`, `SaveWorld`, `DoExit`, `Broadcast <msg>`

---

### A7. `asm_player_list.py` — Lista de Jogadores TEK

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_ui/asm_player_list.py`
**Referência ASM:** `Windows/PlayerListWindow.xaml`

```python
def open_asm_player_list(app, srv: AsmServerConfig) -> None:
    """
    Abre janela com jogadores conectados via RCON 'ListPlayers'.
    Atualiza a cada 30s automaticamente.
    Ações por jogador: Kick, Ban, Whitelist, Admin.
    """
```

**RCON commands:**
- `ListPlayers` → parse de "0. Nome, SteamID"
- `KickPlayer <steamid>` → kick
- `Ban <nome>` → ban
- `Cheat AddToWhitelist <steamid>` → whitelist
- `Cheat AllowPlayerToJoinNoCheck <steamid>` → exclusive join

---

### A8. `asm_save_restore.py` — Backup/Restore de Saves TEK

**Prioridade:** 🟢 Baixa
**Arquivo a criar:** `src/asm_ui/asm_save_restore.py`
**Referência ASM:** `Windows/WorldSaveRestoreWindow.xaml`

```python
# Path dos saves:
saves_dir = Path(srv.install_dir) / "ShooterGame" / "Saved" / "SavedArks"
# Arquivos: TheIsland.ark, TheIsland_AntiCorruptionBackup.bak,
#           Tribes/*.arktribe, Players/*.arkprofile
```

```python
def open_asm_save_restore(app, srv: AsmServerConfig) -> None:
    """
    Lista backups existentes.
    Botão 'Backup agora' → copia SavedArks/ para pasta datada.
    Botão 'Restaurar' → para servidor, substitui arquivos, reinicia.
    """
```

**Pasta de backup:** `{install_dir}/ARKLAND_Backups/YYYY-MM-DD_HH-MM-SS/`

---

### A9. `asm_scheduler_ui.py` — Agendador de Tarefas TEK

**Prioridade:** 🟢 Baixa
**Arquivo a criar:** `src/asm_ui/asm_scheduler_ui.py`
**Referência ASM:** `Windows/ScheduledTasksWindow.xaml`

Os campos `enable_auto_restart`, `auto_restart_time`, `restart_countdown_minutes`, `enable_auto_update_check`, `auto_update_check_minutes` já existem no `AsmServerConfig` e já há UI na seção 2 (Gerenciamento Automático).

O que falta é o **loop de execução** no `app_tek.py`:
```python
def _asm_scheduler_tick(self) -> None:
    """Chamado a cada 60s via app.after(60000, self._asm_scheduler_tick).
    Para cada servidor com enable_auto_restart=True:
      - Compara datetime.now().strftime("%H:%M") com srv.auto_restart_time
      - Se match: envia RCON countdown → restart
    Para cada servidor com enable_auto_update_check=True:
      - Verifica se {auto_update_check_minutes} se passaram desde última verificação
      - Chama AsmSteamCmd.check_update() → se atualização disponível, agenda restart
    """
```

---

### A10. Workshop Browser TEK

**Prioridade:** 🟢 Baixa
**Arquivo a criar:** `src/asm_ui/asm_workshop.py`
**Referência ASM:** `Windows/WorkshopFilesWindow.xaml`

**Reutiliza:** `src/dialogs/mod_search_dialog.py` já existente (busca na Steam API).

```python
def open_asm_workshop(app, srv: AsmServerConfig) -> None:
    """
    Abre browser de mods do Workshop Steam.
    Busca por nome/ID → lista resultados com thumbnail, nome, rating.
    Botão ➕ Adicionar → adiciona à lista srv.active_mods.
    Botão 📦 Baixar Todos → chama AsmSteamCmd.download_mod() para cada mod novo.
    """
```

**API usada:** `https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/`

---

## 4. Fase B — Janelas Auxiliares TEK (ASM-fiel)

### B1. Botões de Acesso Rápido no Server Card

**Arquivo:** `src/asm_ui/asm_server_card.py`

Adicionar botões de ação no footer do card além de ▶ ⏹ 🔄:

| Botão | Ação |
|---|---|
| `🖥 RCON` | `open_asm_rcon_window(app, srv)` |
| `👥 Players` | `open_asm_player_list(app, srv)` |
| `💾 Backup` | `open_asm_save_restore(app, srv)` |

**Condição:** apenas quando `srv.rcon_enabled = True` e status = RUNNING.

---

### B2. Indicadores de Status Mais Ricos no Card

**Arquivo:** `src/asm_ui/asm_server_card.py`

- **Uptime** — calcular a partir do momento em que o status mudou para RUNNING
- **Players online** — atualizado via RCON `ListPlayers` a cada 30s (count apenas)
- **Versão do servidor** — ler de `{install_dir}/version.txt` (arquivo gerado pelo SteamCMD)
- **Memória usada** — via `psutil.Process(pid).memory_info().rss`

**Formato sugerido no card:**
```
● ONLINE  |  👥 12/70  |  🕐 2h 34min  |  RAM: 4.2 GB
```

---

## 5. Sprint 2 — Ferramentas de Operação

**Contexto:** funcionalidades de gerenciamento operacional para servidores TEK em execução.

---

### S2.1 Gerenciador de Arquivos do Servidor

**Arquivo a criar:** `src/asm_ui/asm_file_manager.py`
**Prioridade:** 🔴 Alta

Abre um explorador de arquivos dentro da janela do app, navegando pelo `install_dir` do servidor.

**Estrutura de UI:**
```
┌─ File Manager — {srv.name} ───────────────────────────────────┐
│  📁 ShooterGame/                                              │
│  ├── 📁 Binaries/Win64/                                       │
│  │    ├── 📁 ArkApi/Plugins/   ← plugins instalados          │
│  ├── 📁 Saved/                                                │
│  │    ├── 📁 Config/WindowsServer/   ← GUS + Game.ini        │
│  │    ├── 📁 SavedArks/   ← saves do mundo                   │
│  │    ├── 📁 Logs/   ← ShooterGame.log                       │
│  ├── 📁 Content/Mods/   ← mods instalados                    │
└───────────────────────────────────────────────────────────────┘
```

**Funcionalidades:**
- Navegação de diretórios com breadcrumb
- Listagem com ícone por tipo (pasta, .ini, .ark, .dll, .txt)
- Abrir arquivos de texto com editor simples inline (`.ini`, `.json`, `.txt`, `.log`)
- Botões: Atualizar, Abrir no Explorer, Copiar caminho
- Atalhos rápidos: `[GUS.ini] [Game.ini] [Logs] [Plugins] [SavedArks]`

**Paths de atalho:**
```python
SHORTCUTS = {
    "⚙ GUS.ini":    "ShooterGame/Saved/Config/WindowsServer/GameUserSettings.ini",
    "🎮 Game.ini":  "ShooterGame/Saved/Config/WindowsServer/Game.ini",
    "📋 Logs":      "ShooterGame/Saved/Logs/",
    "🔌 Plugins":   "ShooterGame/Binaries/Win64/ArkApi/Plugins/",
    "💾 Saves":     "ShooterGame/Saved/SavedArks/",
    "🧩 Mods":      "ShooterGame/Content/Mods/",
}
```

---

### S2.2 CPU Affinity e Prioridade de Processo

**Arquivo:** `src/app_tek.py` + `src/asm_engine/asm_server_manager.py`
**Prioridade:** 🟡 Média

Após o servidor iniciar, ajustar via `psutil`:

```python
import psutil

def _set_process_affinity(pid: int, cores: list[int], priority: str) -> None:
    """
    cores: [0, 1, 2, 3] → cpus usadas pelo processo
    priority: "normal" | "above_normal" | "high" | "realtime"
    """
    p = psutil.Process(pid)
    if cores:
        p.cpu_affinity(cores)
    priorities = {
        "normal":       psutil.NORMAL_PRIORITY_CLASS,
        "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
        "high":         psutil.HIGH_PRIORITY_CLASS,
        "realtime":     psutil.REALTIME_PRIORITY_CLASS,
    }
    p.nice(priorities.get(priority, psutil.NORMAL_PRIORITY_CLASS))
```

**Novos campos em `AsmServerConfig`:**
```python
cpu_affinity_cores:  List[int] = field(default_factory=list)  # [] = todos
process_priority:    str = "normal"
```

**UI:** seção nova "Desempenho do Processo" na seção 2 (Gerenciamento Automático) ou nova seção 25.

---

### S2.3 Verificador de Regras de Firewall

**Arquivo a criar:** `src/asm_engine/asm_firewall.py`
**Prioridade:** 🟡 Média

```python
def check_firewall_rules(srv: AsmServerConfig) -> list[dict]:
    """
    Usa netsh advfirewall para verificar se as portas estão abertas.
    Retorna lista de {port, protocol, status: "open"|"blocked"|"missing"}.
    """

def create_firewall_rules(srv: AsmServerConfig) -> None:
    """
    netsh advfirewall firewall add rule
        name="ARK Server {srv.name} - UDP {srv.server_port}"
        protocol=UDP
        localport={srv.server_port}
        action=allow
        dir=in
    """
```

**Portas a verificar:**
| Porta | Protocolo | Descrição |
|---|---|---|
| `srv.server_port` (7777) | UDP | Conexão de jogadores |
| `srv.query_port` (27015) | UDP | Steam query |
| `srv.rcon_port` (27020) | TCP | RCON |

**UI:** dialog "🔧 Verificar Firewall" acessível pelo server card com lista de status e botão "Criar Regras Automáticas".

---

### S2.4 Gráfico de Performance em Tempo Real

**Arquivo a criar:** `src/asm_ui/asm_perf_chart.py`
**Prioridade:** 🟢 Baixa
**Depende de:** `psutil`

Gráfico histórico de 60 pontos (últimos 5 min) para CPU%, RAM%, players online.

```python
class AsmPerfChart(ctk.CTkFrame):
    """
    Mini-gráfico de linha desenhado em tkinter Canvas.
    Atualizado via app.after(5000, self._tick).
    Exibe: CPU%, RAM%, Players.
    """
    def _tick(self) -> None:
        self._history_cpu.append(psutil.cpu_percent())
        self._history_ram.append(psutil.virtual_memory().percent)
        self._draw()
```

**Posição:** widget expandível na parte inferior do server card, ativado por botão "📊".

---

## 6. Sprint 3 — Organização e Fluxo de Trabalho

---

### S3.1 Pastas de Servidores (Grupos)

**Prioridade:** 🔴 Alta
**Arquivo a criar:** `src/asm_ui/asm_folders.py`

Agrupar servidores em pastas/grupos na sidebar e no dashboard.

**Novo campo em `AsmServerConfig`:**
```python
folder: str = ""  # nome da pasta/grupo (ex: "Cluster #1", "Testes")
```

**Novo arquivo:** `src/asm_engine/asm_folder_manager.py`
```python
class AsmFolderManager:
    """Gerencia a organização de servidores em grupos.
    Dados salvos em asm_folders.json (mesmo diretório dos asm_servers.json).
    """
    def get_folders(self) -> list[str]: ...
    def add_folder(self, name: str) -> None: ...
    def rename_folder(self, old: str, new: str) -> None: ...
    def delete_folder(self, name: str) -> None: ...  # servidores movidos para raiz
```

**UI:**
- Dashboard: cards agrupados por pasta com header da pasta e "▶ Iniciar Todos"
- Sidebar: estrutura em árvore (pasta → servidores)
- Drag-and-drop de server cards entre pastas

---

### S3.2 Ações em Lote (Bulk Actions)

**Arquivo:** `src/app_tek.py` + `src/asm_ui/asm_dashboard.py`
**Prioridade:** 🟡 Média

**Toolbar de seleção múltipla:**
```
[ ☐ Selecionar Todos ]  [ ▶ Iniciar Selecionados ]  [ ⏹ Parar Selecionados ]  [ 🔄 Reiniciar ]  [ ⚙ Aplicar Config ]
```

**Ações em lote:**
- `start_all()` / `stop_all()` / `restart_all()` → paralelo com `threading.Thread` para cada
- `apply_config_to_selected(template: AsmServerConfig, fields: list[str])` → aplica campos específicos para múltiplos servidores
- `update_mods_selected()` → `AsmSteamCmd.download_mod()` em paralelo

**Estado de seleção** mantido em `app._asm_selected_servers: set[str]` (set de IDs).

---

### S3.3 Presets de Configuração

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_engine/asm_preset_manager.py`

```python
class AsmPresetManager:
    """
    Exporta/importa subconjuntos de config como presets reutilizáveis.
    Arquivo: %APPDATA%/ARKLAND-ServerManager/presets/
    Formato: JSON com nome + dict de campos + metadados
    """
    def save_preset(self, name: str, srv: AsmServerConfig,
                    categories: list[str]) -> None:
        """categories: ["players", "dinos", "breeding", "environment", ...]"""

    def load_preset(self, name: str, srv: AsmServerConfig) -> None:
        """Aplica campos do preset ao servidor (não sobrescreve campos fora do preset)."""

    def list_presets(self) -> list[dict]:
        """Retorna [{name, created_at, categories, description}]"""
```

**Categorias de preset:**
```python
PRESET_CATEGORIES = {
    "players":     ["xp_multiplier", "player_damage_multiplier", ..., "per_level_player"],
    "dinos":       ["dino_damage_multiplier", ..., "per_level_dino_*"],
    "breeding":    ["mating_interval_multiplier", ..., "baby_imprinting_stat_scale"],
    "environment": ["harvest_amount_multiplier", ..., "disable_weather_fog"],
    "structures":  ["structure_resistance_multiplier", ..., "limit_turrets_num"],
    "rules":       ["enable_pvp", ..., "allow_tribe_alliances"],
    "full":        # todos os campos
}
```

**UI:** botão "📋 Presets" no header do painel de config → dialog com lista + importar/exportar.

---

### S3.4 Exportar/Importar Perfil Completo

**Prioridade:** 🟢 Baixa
**Arquivo:** `src/asm_engine/asm_config_manager.py`

```python
def export_server(self, server_id: str, path: str) -> None:
    """Exporta AsmServerConfig como JSON para arquivo .arkprofile."""

def import_server(self, path: str) -> AsmServerConfig:
    """Importa .arkprofile → novo servidor com novo UUID."""

def clone_server(self, server_id: str, new_name: str) -> AsmServerConfig:
    """Clona servidor com novo UUID, novo nome e install_dir vazio."""
```

**Formato do arquivo `.arkprofile`:**
```json
{
  "version": "1.0",
  "created_at": "2026-05-30T12:00:00",
  "created_by": "ARKLAND-Multi 1.3.57",
  "server": { ...AsmServerConfig.to_dict()... }
}
```

---

## 7. Sprint 4 — Dados Avançados e Importação

---

### S4.1 Tribe Log Viewer

**Prioridade:** 🔴 Alta
**Arquivo a criar:** `src/asm_ui/asm_tribe_log.py`
**Path dos logs:** `{install_dir}/ShooterGame/Saved/Logs/TribeLog.log`

```python
def open_asm_tribe_log(app, srv: AsmServerConfig) -> None:
    """
    Abre janela com logs de tribos.
    Filtra por: tribo, jogador, tipo de evento (kill, tame, structure, admin).
    Scroll para trás nos últimos N eventos.
    Destaca eventos críticos (admin, wipe, ban) em vermelho.
    Export para .txt ou .csv.
    """
```

**Formato do TribeLog:**
```
Day 123, 14:30:00: <NomeTribo> - NomeJogador destroyed an enemy structure!
Day 123, 14:31:05: <NomeTribo> - NomeJogador (NomeAdmin) Admin Command: ...
```

**UI:**
- Filtro de texto (busca em tempo real)
- Chips de filtro: `[Todos] [Kills] [Estruturas] [Admin] [Tames]`
- Atualização automática (tail do arquivo a cada 5s via thread)
- Botão "Copiar seleção" e "Exportar"

---

### S4.2 Importar Servidor Existente

**Prioridade:** 🔴 Alta
**Arquivo:** `src/asm_ui/asm_add_server_dialog.py`

Modo "Importar existente" — detecta configuração de um servidor já instalado:

```python
def import_existing_server(install_dir: str) -> AsmServerConfig:
    """
    1. Verifica existência de ShooterGameServer.exe
    2. Lê GameUserSettings.ini → popula campos de Administration, Rules, etc.
    3. Lê Game.ini → popula campos de Players, Dinos, Environment, etc.
    4. Lê CLI do RunServer.cmd → detecta map, ports, etc.
    5. Retorna AsmServerConfig preenchido
    """
```

**Detecção automática de portas** a partir do RunServer.cmd:
```
ShooterGameServer.exe TheIsland?listen?Port=7777?QueryPort=27015?MaxPlayers=70
    -nosteamclient -game -server -log
```

**Dialog de confirmação** mostrando campos detectados antes de criar o servidor.

---

### S4.3 Editor Visual de Engramas

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_ui/asm_engram_editor.py`

Substituição do raw editor da seção 14 por um editor visual:

```
┌─ Editor de Engramas ──────────────────────────────────────────┐
│  🔍 Filtrar: [__________]  [ ☐ Apenas modificados ]          │
│  ─────────────────────────────────────────────────────────── │
│  Engram                │ Pontos │ Nível │ Esconder │ Forçar   │
│  ─────────────────────────────────────────────────────────── │
│  ✦ Crossbow            │  [9]   │ [10]  │   ☐      │  ☐      │
│  ✦ Metal Wall          │  [5]   │ [22]  │   ☐      │  ☐      │
│  ✦ Turret              │  [20]  │ [75]  │   ☑      │  ☐      │
└───────────────────────────────────────────────────────────────┘
```

**Fonte de dados:** arquivo `engrams.json` embutido com todos os ~500 engramas do ARK.
**Formato Game.ini gerado:**
```ini
OverrideNamedEngramEntries=(EngramClassName="EngramEntry_Crossbow_C",EngramLevelRequirement=10,EngramPointsCost=9,bCanUnlockItem=True)
```

---

### S4.4 Calculadora de Ascensão de Nível (XP Table)

**Prioridade:** 🟡 Média

Já existe uma calculadora básica inline na seção 16 (Progressões de Nível) com campos `max_lvl`, `xp_base`, `mult`, `engrams`. Melhorias a adicionar:

1. **Preview da tabela** gerada — mostrar as 10 primeiras e últimas linhas antes de aplicar
2. **Modo fórmula custom** — permitir expressão Python segura (`lvl * 100 + lvl ** 2 * 5`)
3. **Preset de tabelas populares** — Official (70 lvls), Hard (150), Custom (configurável)
4. **Gráfico da curva XP** — mini canvas CTk mostrando a distribuição de XP por nível

---

### S4.5 Editor de Spawner Avançado

**Prioridade:** 🟢 Baixa
**Arquivo a criar:** `src/asm_ui/asm_spawner_editor.py`

Substituição do raw editor da seção 19 por interface visual:

```
┌─ Substituições de Spawner ────────────────────────────────────┐
│  [+ Adicionar Container]                                      │
│  ─────────────────────────────────────────────────────────── │
│  📦 DinoSpawnEntries_Island_C                                  │
│    ├─ [+ Adicionar Entrada]                                   │
│    ├─ Triceratops_Character_BP_C  [Peso: 0.1]  [Limite: 0]   │
│    └─ Rex_Character_BP_C          [Peso: 0.3]  [Limite: 5]   │
└───────────────────────────────────────────────────────────────┘
```

**Formato Game.ini gerado:**
```ini
ConfigAddNPCSpawnEntriesContainer=(NPCSpawnEntriesContainerClassString="DinoSpawnEntries_Island_C",...)
```

---

## 8. Sprint 5 — Cloud e IA

---

### S5.1 Backup em Nuvem (S3 / Backblaze B2)

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_engine/asm_cloud_backup.py`
**Dependências novas:** `boto3` (S3/B2)

```python
class AsmCloudBackup:
    """
    Upload automático de saves para S3 ou B2 após cada backup local.
    """
    def __init__(self, provider: str, bucket: str, key_id: str, key_secret: str): ...

    def upload_backup(self, local_path: Path, server_name: str) -> None:
        """
        Caminho no S3: arkland-backups/{server_name}/{data}/{arquivo}
        Comprime com zipfile antes do upload.
        """

    def list_remote_backups(self, server_name: str) -> list[dict]: ...
    def download_backup(self, remote_key: str, local_path: Path) -> None: ...
```

**Configuração por servidor em `AsmServerConfig`:**
```python
cloud_backup_enabled:  bool = False
cloud_backup_provider: str  = "s3"    # "s3" | "b2" | "gcs"
cloud_backup_bucket:   str  = ""
cloud_backup_prefix:   str  = ""
```

**Credenciais:** armazenadas em `%APPDATA%\ARKLAND-ServerManager\credentials.json` — **nunca** no `asm_servers.json` (evitar leak no JSON de config).

---

### S5.2 Assistente IA para Configuração de Servidores

**Prioridade:** 🟢 Baixa
**Arquivo a criar:** `src/asm_ui/asm_ai_assistant.py`
**Dependências novas:** `openai` (API OpenAI ou local LLM)

```python
def open_asm_ai_assistant(app, srv: AsmServerConfig) -> None:
    """
    Chat contextual que conhece o config atual do servidor.
    Exemplos de queries:
      - "Quero que meus jogadores subam de nível rápido mas não muito fácil"
      - "Configure para server PvE casual com breeding x10"
      - "Otimize os multiplicadores de estrutura para um server survival"

    O assistente responde com sugestões de valores e botão:
    [✅ Aplicar sugestões ao servidor]
    """
```

**Contexto injetado no prompt:**
```python
context = f"""
Servidor ARK: {srv.name}
Modo: {"PvP" if srv.enable_pvp else "PvE"}
Mapa: {srv.server_map}
Max Players: {srv.max_players}
Configurações atuais relevantes: XP x{srv.xp_multiplier}, Taming x{srv.taming_speed_multiplier}, ...
"""
```

---

### S5.3 Monitor de Desempenho Avançado

**Prioridade:** 🟡 Média
**Arquivo a criar:** `src/asm_ui/asm_monitor_window.py`

Dashboard de monitoramento em tempo real com histórico de 24h:

```
┌─ Monitor de Performance — {srv.name} ────────────────────────┐
│  CPU: ████░░░░ 42%  |  RAM: ██████░░ 6.2 GB / 8 GB          │
│  Players: 18/70     |  Uptime: 14h 23min                     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Gráfico CPU (últimas 24h)                           │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Gráfico Players (últimas 24h)                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  Alertas: [⚠ CPU > 80%] [⚠ RAM > 90%] [⚠ Players = 0 por 2h]│
└───────────────────────────────────────────────────────────────┘
```

**Alertas configuráveis** com ação (ex: enviar Discord webhook, reiniciar servidor).

---

## 9. Referências Técnicas

### 9.1 Tabela de Dependências por Feature

| Feature | Arquivo Python existente | Dependências externas | Requer A2+ |
|---|---|---|---|
| A1 — per_level INI | `asm_ini_manager.py` | nenhuma | Não |
| A2 — SteamCMD | novo `asm_steamcmd.py` | nenhuma | — |
| A3 — Botões install | `asm_server_panel.py` | nenhuma | A2 |
| A4 — read_ini | `asm_ini_manager.py` | nenhuma | Não |
| A5 — restart/RCON | `asm_server_manager.py` + `rcon_client.py` | nenhuma | Não |
| A6 — RCON Window | novo `asm_rcon_window.py` | `rcon_client.py` ✅ | A5 |
| A7 — Player List | novo `asm_player_list.py` | `rcon_client.py` ✅ | A5 |
| A8 — Save Restore | novo `asm_save_restore.py` | nenhuma | Não |
| A9 — Scheduler | `app_tek.py` | nenhuma | Não |
| A10 — Workshop | novo `asm_workshop.py` + `mod_search_dialog.py` ✅ | urllib ✅ | A2 |
| S2.1 — File Manager | novo `asm_file_manager.py` | nenhuma | Não |
| S2.2 — CPU Affinity | `asm_server_manager.py` | psutil ✅ | Não |
| S2.3 — Firewall | novo `asm_firewall.py` | subprocess (netsh) ✅ | Não |
| S2.4 — Perf Chart | novo `asm_perf_chart.py` | psutil ✅ | Não |
| S3.1 — Pastas | novo `asm_folder_manager.py` | nenhuma | Não |
| S3.2 — Bulk Actions | `app_tek.py` + `asm_dashboard.py` | nenhuma | Não |
| S3.3 — Presets | novo `asm_preset_manager.py` | nenhuma | Não |
| S3.4 — Export/Import | `asm_config_manager.py` | nenhuma | Não |
| S4.1 — Tribe Log | novo `asm_tribe_log.py` | nenhuma | Não |
| S4.2 — Import Existente | `asm_add_server_dialog.py` + A4 | nenhuma | A4 |
| S4.3 — Engram Editor | novo `asm_engram_editor.py` | engrams.json embutido | Não |
| S4.4 — XP Calculator | `asm_server_panel.py` | nenhuma | Não |
| S4.5 — Spawner Visual | novo `asm_spawner_editor.py` | nenhuma | Não |
| S5.1 — Cloud Backup | novo `asm_cloud_backup.py` | boto3 (novo) | A8 |
| S5.2 — IA Assistant | novo `asm_ai_assistant.py` | openai (novo) | Não |
| S5.3 — Monitor Avançado | novo `asm_monitor_window.py` | psutil ✅, tkinter Canvas ✅ | Não |

### 9.2 Ordem de Execução Recomendada

```
A1 → A2 → A3 → A4 → A5 → A6 → A7  (TEK Core)
         ↓
        A8 → A9 → A10               (Recursos auxiliares)
         ↓
  S2.1 → S2.2 → S2.3 → S2.4        (Sprint 2 — Ferramentas)
         ↓
  S3.1 → S3.2 → S3.3 → S3.4        (Sprint 3 — Organização)
         ↓
  S4.1 → S4.2 → S4.3 → S4.4 → S4.5 (Sprint 4 — Dados)
         ↓
  S5.1 → S5.2 → S5.3                (Sprint 5 — Cloud/IA)
```

**A1 é crítico** — deve ser feito antes de qualquer teste com servidores reais, pois sem ele os per-level stats nunca chegam ao Game.ini.

**A2 + A3** liberam o fluxo completo de instalação no modo TEK.

**A4** é pré-requisito para S4.2 (importar servidor existente lê o INI).

### 9.3 Campos do INI_MAP que PRECISAM de Atenção

Os campos abaixo existem em `AsmServerConfig` mas **não estão no INI_MAP** ainda:

| Campo | Tipo | INI esperado |
|---|---|---|
| `per_level_player[0..11]` | `List[float]` | `Game.ini → PerLevelStatsMultiplier_Player[N]` |
| `per_level_dino_wild[0..11]` | `List[float]` | `Game.ini → PerLevelStatsMultiplier_DinoWild[N]` |
| `per_level_dino_tamed[0..11]` | `List[float]` | `Game.ini → PerLevelStatsMultiplier_DinoTamed[N]` |
| `per_level_dino_tamed_add[0..11]` | `List[float]` | `Game.ini → PerLevelStatsMultiplier_DinoTamed_Add[N]` |
| `per_level_dino_tamed_affinity[0..11]` | `List[float]` | `Game.ini → PerLevelStatsMultiplier_DinoTamed_Affinity[N]` |
| `allow_cave_flyers` | `bool` | CLI flag `-ForceAllowCaveFlyers` (não INI) |
| `exclusive_join` | `bool` | CLI flag `-exclusivejoin` (não INI) |
| `admin_ids` | `List[str]` | `AllowedCheaterSteamIDs.txt` (não INI) |
| `whitelist_ids` | `List[str]` | `PlayersJoinNoCheckList.txt` (não INI) |
| `exclusive_join_ids` | `List[str]` | `ExclusiveJoin.txt` (não INI) |
| `engram_entries_raw` | `str` | Injetado raw no Game.ini |
| `player_level_stats_raw` | `str` | Injetado raw no Game.ini |
| `dino_level_stats_raw` | `str` | Injetado raw no Game.ini |
| `crafting_overrides_raw` | `str` | Injetado raw no Game.ini |
| `stack_size_overrides_raw` | `str` | Injetado raw no Game.ini |
| `npc_spawn_overrides_raw` | `str` | Injetado raw no Game.ini |
| `supply_crate_overrides_raw` | `str` | Injetado raw no Game.ini |
| `prevent_transfer_raw` | `str` | Injetado raw no GUS.ini |

**Status atual dos raw fields:** os `_raw_*` já são injetados em `write_ini()` via `_inject_raw()`. O que falta é somente os `per_level_*` (array-indexed) e os arquivos de texto (`admin_ids`, `whitelist_ids`, `exclusive_join_ids`).

### 9.4 Linha de Comando TEK — Formato Fiel ao ASM

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

### 9.5 Variáveis de Ambiente Seguras para o Processo Servidor

```python
# Aplicadas em AsmServerManager._start_worker():
env = os.environ.copy()
env.pop("__COMPAT_LAYER", None)          # evita shim DetectorsAppHealth → crash ArkShopUI

# Remove _MEIPASS do PATH (PyInstaller artefato)
meipass = getattr(sys, "_MEIPASS", None)
if meipass:
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep)
        if not p.startswith(meipass)
    )
```

### 9.6 Causa Raiz Histórica do Crash ArkShopUI (Resolvido)

> **Para referência futura:** O crash `ArkShopUI.dll!CheckOnTimerCallbacks` foi causado por conflito de banco MySQL — ArkShop e Permissions usando `MysqlDB: "arkshop"` com schemas incompatíveis na tabela `Players`. Fix: alterar `Permissions/config.json → MysqlDB: "ark_permission"`. Resolvido em 26/05/2026.

O crash **não era** relacionado ao ARKLAND — era de config de plugin. O fix de `__COMPAT_LAYER` (1.3.44) e o fix do `modPath` dos `.mod` files (1.3.40) foram investigações paralelas corretas que melhoraram a estabilidade geral mas não eram a causa do crash específico do ArkShopUI.

---

*Documento gerado automaticamente pela análise completa do workspace em 30/05/2026.*
*Última revisão de código base: `src/asm_ui/asm_server_panel.py`, `src/asm_engine/asm_server_config.py`, `src/asm_engine/asm_ini_manager.py`, `src/asm_engine/asm_server_manager.py`, `src/app_tek.py`.*
