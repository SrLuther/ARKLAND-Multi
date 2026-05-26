# ARKLAND TEK — Plano de Arquitetura

> Documento de planejamento. Atualizar conforme decisões forem tomadas.
> Criado em: 25/05/2026

---

## Contexto

O ARKLAND-Multi opera atualmente no modo **PRIMITIVE** — sistema proprietário de gerenciamento de servidores ARK.

O **ARKLAND TEK** é uma reimplementação completa do **ASM (ARK Server Manager)** em Python/CustomTkinter, integrada ao mesmo executável como um modo alternativo global.

> **Pré-requisito para construção do TEK:** confirmar resultado do [Teste T13](./PENDING_ISSUES.md) — se o crash do ArkShopUI for causado pelo que o ARKLAND *escreve* (não pelo que *instala*), o TEK pode herdar o mesmo problema. Nesse caso, o TEK só faz sentido se a causa for identificada e corrigida primeiro.

---

## Modos de Operação

### PRIMITIVE (atual)

- Engine proprietária do ARKLAND-Multi
- Configs armazenadas em `data/servers/`
- UI atual (CustomTkinter, tema verde)
- `src/server_config.py`, `src/server_manager.py`, `src/ark_ini.py`

### TEK (planejado)

- Reimplementação fiel do ASM em Python
- Configs armazenadas em `data/asm_servers/` (separadas do PRIMITIVE)
- Nova UI (visual diferente — tema a definir)
- Código em `src/asm_engine/` e `src/asm_ui/`
- **Nenhum arquivo compartilhado com PRIMITIVE** exceto o estritamente necessário

### Switch Global

- Seletor no topo do app (não por servidor)
- Salvo no `AppConfig` principal
- Ao trocar de modo, a UI inteira é substituída
- Os dois modos são completamente independentes em dados e lógica

---

## Estrutura de Pastas (TEK)

```text
src/
├── asm_engine/                  # Engine backend fiel ao ASM
│   ├── __init__.py
│   ├── asm_server_config.py     # Equivalente ao ServerProfile.cs
│   ├── asm_server_manager.py    # Equivalente ao ServerRuntime.cs
│   ├── asm_steamcmd.py          # Equivalente ao ServerApp.cs
│   ├── asm_ini_manager.py       # Sistema IniFileEntry em Python
│   ├── asm_rcon.py              # RCON (baseado no ServerRCON.cs)
│   └── asm_scheduler.py         # Tarefas agendadas (auto-shutdown, etc.)
│
└── asm_ui/                      # UI do modo TEK
    ├── __init__.py
    ├── asm_dashboard.py         # Dashboard principal
    ├── asm_server_card.py       # Cards de servidor
    ├── asm_server_panel.py      # Painel de configuração do servidor
    └── asm_pages/               # Abas da configuração
        ├── __init__.py
        ├── asm_tab_administration.py
        ├── asm_tab_rules.py
        ├── asm_tab_chat.py
        ├── asm_tab_hud.py
        ├── asm_tab_players.py
        ├── asm_tab_dinos.py
        ├── asm_tab_environment.py
        ├── asm_tab_structures.py
        ├── asm_tab_engrams.py
        ├── asm_tab_levels.py
        ├── asm_tab_mods.py
        └── asm_tab_custom.py

data/
├── servers/                     # Configs PRIMITIVE (existente)
└── asm_servers/                 # Configs TEK (novo, separado)
```

---

## ASM Source — Referência

**Path local:** `C:\Users\Ciano\Documents\_asm_src\ARK Server Manager\`

| Arquivo ASM | Equivalente TEK | Descrição |
| --- | --- | --- |
| `Lib/ServerProfile.cs` | `asm_server_config.py` | ~300 campos de config com mapeamento INI |
| `Lib/ServerRuntime.cs` | `asm_server_manager.py` | Start/stop/monitor/restart do servidor |
| `Lib/ServerApp.cs` | `asm_steamcmd.py` | Install/update via SteamCMD |
| `Lib/ServerRCON.cs` | `asm_rcon.py` | Console RCON |
| `Lib/ServerManager.cs` | `asm_dashboard.py` (parcial) | Gerenciador global de múltiplos servidores |
| `Windows/ServerSettingsControl.xaml` | `asm_pages/asm_tab_*.py` | Todas as abas de configuração (608KB de UI) |
| `Windows/GlobalSettingsControl.xaml` | `asm_ui/asm_global_settings.py` | Configurações globais do ASM |
| `Windows/RCONWindow.xaml` | `asm_ui/asm_rcon_window.py` | Janela RCON |
| `Windows/PlayerListWindow.xaml` | `asm_ui/asm_player_list.py` | Lista de jogadores |
| `Windows/WorkshopFilesWindow.xaml` | `asm_ui/asm_workshop.py` | Browser de mods do Workshop |
| `Windows/WorldSaveRestoreWindow.xaml` | `asm_ui/asm_save_restore.py` | Backup/restore de saves |
| `Windows/ScheduledTasksWindow.xaml` | `asm_ui/asm_scheduler_ui.py` | Gerenciador de tarefas agendadas |

---

## IniMapper — Conceito Central

O ASM usa reflection C# com atributos `[IniFileEntry]` para mapear ~300 campos automaticamente para o INI. No Python, esse sistema é substituído por um dicionário declarativo central.

### Estrutura do mapeamento

```python
# src/asm_engine/asm_ini_manager.py

INI_MAP = {
    # (campo_python): (arquivo, secao, chave_ini, opcoes)
    "session_name":        ("GameUserSettings.ini", "SessionSettings",  "SessionName",         {}),
    "server_password":     ("GameUserSettings.ini", "ServerSettings",   "ServerPassword",       {}),
    "admin_password":      ("GameUserSettings.ini", "ServerSettings",   "ServerAdminPassword",  {}),
    "spectator_password":  ("GameUserSettings.ini", "ServerSettings",   "SpectatorPassword",    {}),
    "server_port":         ("GameUserSettings.ini", "SessionSettings",  "Port",                 {}),
    "query_port":          ("GameUserSettings.ini", "SessionSettings",  "QueryPort",            {}),
    "server_ip":           ("GameUserSettings.ini", "SessionSettings",  "MultiHome",            {"conditioned_on": "server_ip"}),
    "max_players":         ("GameUserSettings.ini", "GameSession",      "MaxPlayers",           {}),
    "rcon_enabled":        ("GameUserSettings.ini", "ServerSettings",   "RCONEnabled",          {}),
    "rcon_port":           ("GameUserSettings.ini", "ServerSettings",   "RCONPort",             {}),
    "active_mods":         ("GameUserSettings.ini", "ServerSettings",   "ActiveMods",           {}),
    # ... ~300 campos no total
}
```

### Leitura/escrita automática

```python
def write_ini_from_config(config: AsmServerConfig, install_dir: str) -> None:
    """Escreve GameUserSettings.ini e Game.ini a partir do config."""
    ...

def read_ini_to_config(config: AsmServerConfig, install_dir: str) -> None:
    """Lê os INIs e popula o config."""
    ...
```

---

## Campos do ServerProfile.cs — Categorias

Todos os campos abaixo devem ser implementados em `asm_server_config.py`.

### Administration (Admin / Rede / Sessão)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `session_name` | `SessionName` | GameUserSettings | SessionSettings |
| `server_password` | `ServerPassword` | GameUserSettings | ServerSettings |
| `admin_password` | `ServerAdminPassword` | GameUserSettings | ServerSettings |
| `spectator_password` | `SpectatorPassword` | GameUserSettings | ServerSettings |
| `server_port` | `Port` | GameUserSettings | SessionSettings |
| `query_port` | `QueryPort` | GameUserSettings | SessionSettings |
| `server_ip` | `MultiHome` | GameUserSettings | SessionSettings |
| `max_players` | `MaxPlayers` | GameUserSettings | GameSession |
| `rcon_enabled` | `RCONEnabled` | GameUserSettings | ServerSettings |
| `rcon_port` | `RCONPort` | GameUserSettings | ServerSettings |
| `rcon_log_buffer` | `RCONServerGameLogBuffer` | GameUserSettings | ServerSettings |
| `admin_logging` | `AdminLogging` | GameUserSettings | ServerSettings |
| `server_map` | — | CLI | — |
| `total_conversion_mod_id` | — | CLI | — |
| `active_mods` | `ActiveMods` | GameUserSettings | ServerSettings |
| `enable_ban_list_url` | `BanListURL` | GameUserSettings | ServerSettings |
| `kick_idle_players` | `KickIdlePlayersPeriod` | GameUserSettings | ServerSettings |
| `auto_save_period` | `AutoSavePeriodMinutes` | GameUserSettings | ServerSettings |
| `motd` | `Message` | GameUserSettings | MessageOfTheDay |
| `motd_duration` | `Duration` | GameUserSettings | MessageOfTheDay |
| `alt_save_directory_name` | `AltSaveDirectoryName` | CLI (`?`) | — |
| `cross_ark_cluster_id` | — | CLI (`?`) | — |
| `branch_name` | — | SteamCMD | — |
| `branch_password` | — | SteamCMD | — |
| `additional_args` | — | CLI (append) | — |

### Rules (Regras de Jogo)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `enable_hardcore` | `ServerHardcore` | GameUserSettings | ServerSettings |
| `enable_pvp` | `ServerPVE` (invertido) | GameUserSettings | ServerSettings |
| `allow_cave_building_pve` | `AllowCaveBuildingPvE` | GameUserSettings | ServerSettings |
| `disable_friendly_fire_pvp` | `bDisableFriendlyFire` | Game | GameMode |
| `disable_friendly_fire_pve` | `bPvEDisableFriendlyFire` | Game | GameMode |
| `disable_loot_crates` | `bDisableLootCrates` | Game | GameMode |
| `enable_difficulty_override` | — | — | — |
| `override_official_difficulty` | `OverrideOfficialDifficulty` | GameUserSettings | ServerSettings |
| `difficulty_offset` | `DifficultyOffset` | GameUserSettings | ServerSettings |
| `max_tribe_size` | `MaxNumberOfPlayersInTribe` | GameUserSettings | ServerSettings |
| `enable_tribute_downloads` | `NoTributeDownloads` (invertido) | GameUserSettings | ServerSettings |
| `prevent_download_survivors` | `PreventDownloadSurvivors` | GameUserSettings | ServerSettings |
| `prevent_download_items` | `PreventDownloadItems` | GameUserSettings | ServerSettings |
| `prevent_download_dinos` | `PreventDownloadDinos` | GameUserSettings | ServerSettings |
| `prevent_upload_survivors` | `PreventUploadSurvivors` | GameUserSettings | ServerSettings |
| `prevent_upload_items` | `PreventUploadItems` | GameUserSettings | ServerSettings |
| `prevent_upload_dinos` | `PreventUploadDinos` | GameUserSettings | ServerSettings |
| `allow_pvp_gamma` | `EnablePVPGamma` | GameUserSettings | ServerSettings |
| `allow_tribe_alliances` | `PreventTribeAlliances` (invertido) | GameUserSettings | ServerSettings |
| `allow_custom_recipes` | `bAllowCustomRecipes` | Game | GameMode |
| `enable_diseases` | `PreventDiseases` (invertido) | GameUserSettings | ServerSettings |
| `prevent_pvp_offline` | `PreventOfflinePvP` | GameUserSettings | ServerSettings |
| `auto_pve_timer` | `bAutoPvETimer` | Game | GameMode |

### ChatAndNotifications

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `global_voice_chat` | `globalVoiceChat` | GameUserSettings | ServerSettings |
| `proximity_chat` | `proximityChat` | GameUserSettings | ServerSettings |
| `player_leave_notifications` | `alwaysNotifyPlayerLeft` | GameUserSettings | ServerSettings |
| `player_joined_notifications` | `alwaysNotifyPlayerJoined` | GameUserSettings | ServerSettings |

### HudAndVisuals

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `allow_crosshair` | `ServerCrosshair` | GameUserSettings | ServerSettings |
| `allow_hud` | `ServerForceNoHud` (invertido) | GameUserSettings | ServerSettings |
| `allow_third_person_view` | `AllowThirdPersonPlayer` | GameUserSettings | ServerSettings |
| `show_map_player_location` | `ShowMapPlayerLocation` | GameUserSettings | ServerSettings |
| `allow_pvp_gamma` | `EnablePVPGamma` | GameUserSettings | ServerSettings |
| `show_floating_damage_text` | `ShowFloatingDamageText` | GameUserSettings | ServerSettings |
| `allow_hit_markers` | `AllowHitMarkers` | GameUserSettings | ServerSettings |

### Players (Multiplicadores de Jogador)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `xp_multiplier` | `XPMultiplier` | GameUserSettings | ServerSettings |
| `player_damage_multiplier` | `PlayerDamageMultiplier` | GameUserSettings | ServerSettings |
| `player_resistance_multiplier` | `PlayerResistanceMultiplier` | GameUserSettings | ServerSettings |
| `player_water_drain_multiplier` | `PlayerCharacterWaterDrainMultiplier` | GameUserSettings | ServerSettings |
| `player_food_drain_multiplier` | `PlayerCharacterFoodDrainMultiplier` | GameUserSettings | ServerSettings |
| `player_stamina_drain_multiplier` | `PlayerCharacterStaminaDrainMultiplier` | GameUserSettings | ServerSettings |
| `player_health_recovery_multiplier` | `PlayerCharacterHealthRecoveryMultiplier` | GameUserSettings | ServerSettings |
| `player_harvesting_damage_multiplier` | `PlayerHarvestingDamageMultiplier` | GameUserSettings | ServerSettings |
| `crafting_skill_bonus_multiplier` | `CraftingSkillBonusMultiplier` | GameUserSettings | ServerSettings |
| `enable_flyer_carry` | `AllowFlyerCarryPVE` | GameUserSettings | ServerSettings |
| `override_max_xp_player` | `OverrideMaxExperiencePointsPlayer` | GameUserSettings | ServerSettings |

### Dinos (Multiplicadores de Dinossauros)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `dino_damage_multiplier` | `DinoDamageMultiplier` | GameUserSettings | ServerSettings |
| `tamed_dino_damage_multiplier` | `TamedDinoDamageMultiplier` | GameUserSettings | ServerSettings |
| `dino_resistance_multiplier` | `DinoResistanceMultiplier` | GameUserSettings | ServerSettings |
| `tamed_dino_resistance_multiplier` | `TamedDinoResistanceMultiplier` | GameUserSettings | ServerSettings |
| `max_tamed_dinos` | `MaxTamedDinos` | GameUserSettings | ServerSettings |
| `dino_count_multiplier` | `DinoCountMultiplier` | GameUserSettings | ServerSettings |
| `taming_speed_multiplier` | `TamingSpeedMultiplier` | GameUserSettings | ServerSettings |
| `mating_interval_multiplier` | `MatingIntervalMultiplier` | Game | GameMode |
| `egg_hatch_speed_multiplier` | `EggHatchSpeedMultiplier` | Game | GameMode |
| `baby_mature_speed_multiplier` | `BabyMatureSpeedMultiplier` | Game | GameMode |
| `baby_food_consumption_multiplier` | `BabyFoodConsumptionSpeedMultiplier` | Game | GameMode |
| `baby_cuddle_interval_multiplier` | `BabyCuddleIntervalMultiplier` | Game | GameMode |
| `baby_imprinting_stat_scale` | `BabyImprintingStatScaleMultiplier` | Game | GameMode |
| `disable_imprint_buff` | `DisableImprintDinoBuff` | GameUserSettings | ServerSettings |
| `allow_anyone_baby_imprint` | `AllowAnyoneBabyImprintCuddle` | GameUserSettings | ServerSettings |
| `disable_dino_riding` | `bDisableDinoRiding` | Game | GameMode |
| `disable_dino_taming` | `bDisableDinoTaming` | Game | GameMode |
| `passive_tame_interval_multiplier` | `PassiveTameIntervalMultiplier` | Game | GameMode |
| `dino_harvesting_damage_multiplier` | `DinoHarvestingDamageMultiplier` | GameUserSettings | ServerSettings |
| `allow_cave_flyers` | — | CLI (`-ForceAllowCaveFlyers`) | — |
| `disable_dino_decay_pve` | `DisableDinoDecayPvE` | GameUserSettings | ServerSettings |
| `pvp_dino_decay` | `PvPDinoDecay` (invertido) | GameUserSettings | ServerSettings |

### Environment (Ambiente)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `harvest_amount_multiplier` | `HarvestAmountMultiplier` | GameUserSettings | ServerSettings |
| `harvest_health_multiplier` | `HarvestHealthMultiplier` | GameUserSettings | ServerSettings |
| `resources_respawn_multiplier` | `ResourcesRespawnPeriodMultiplier` | GameUserSettings | ServerSettings |
| `day_cycle_speed_scale` | `DayCycleSpeedScale` | GameUserSettings | ServerSettings |
| `day_time_speed_scale` | `DayTimeSpeedScale` | GameUserSettings | ServerSettings |
| `night_time_speed_scale` | `NightTimeSpeedScale` | GameUserSettings | ServerSettings |
| `global_spoiling_time_multiplier` | `GlobalSpoilingTimeMultiplier` | GameUserSettings | ServerSettings |
| `global_item_decomposition_multiplier` | `GlobalItemDecompositionTimeMultiplier` | GameUserSettings | ServerSettings |
| `global_corpse_decomposition_multiplier` | `GlobalCorpseDecompositionTimeMultiplier` | GameUserSettings | ServerSettings |
| `crop_decay_speed_multiplier` | `CropDecaySpeedMultiplier` | Game | GameMode |
| `crop_growth_speed_multiplier` | `CropGrowthSpeedMultiplier` | Game | GameMode |
| `hair_growth_speed_multiplier` | `HairGrowthSpeedMultiplier` | Game | GameMode |
| `base_temperature_multiplier` | `BaseTemperatureMultiplier` | GameUserSettings | ServerSettings |
| `disable_weather_fog` | `DisableWeatherFog` | GameUserSettings | ServerSettings |

### Structures (Estruturas)

| Campo Python | INI Key | Arquivo | Seção |
| --- | --- | --- | --- |
| `structure_resistance_multiplier` | `StructureResistanceMultiplier` | GameUserSettings | ServerSettings |
| `structure_damage_multiplier` | `StructureDamageMultiplier` | GameUserSettings | ServerSettings |
| `max_structures_in_range` | `TheMaxStructuresInRange` | GameUserSettings | ServerSettings |
| `per_platform_max_structures_multiplier` | `PerPlatformMaxStructuresMultiplier` | GameUserSettings | ServerSettings |
| `max_platform_saddle_structures` | `MaxPlatformSaddleStructureLimit` | GameUserSettings | ServerSettings |
| `enable_structure_decay_pve` | `DisableStructureDecayPVE` (invertido) | GameUserSettings | ServerSettings |
| `pve_structure_decay_period_multiplier` | `PvEStructureDecayPeriodMultiplier` | GameUserSettings | ServerSettings |
| `pve_structure_decay_destruction_period` | `PvEStructureDecayDestructionPeriod` | GameUserSettings | ServerSettings |
| `auto_destroy_old_structures_multiplier` | `AutoDestroyOldStructuresMultiplier` | GameUserSettings | ServerSettings |
| `force_all_structure_locking` | `ForceAllStructureLocking` | GameUserSettings | ServerSettings |
| `disable_structure_placement_collision` | `DisableStructurePlacementCollision` | GameUserSettings | ServerSettings |
| `limit_turrets_in_range` | `LimitTurretsInRange` | GameUserSettings | ServerSettings |
| `limit_turrets_range` | `LimitTurretsRange` | GameUserSettings | ServerSettings |
| `limit_turrets_num` | `LimitTurretsNum` | GameUserSettings | ServerSettings |

---

## Linha de Comando TEK (ASM-fiel)

O TEK **não coloca** na CLI os campos que o ASM mantém apenas no INI:

```python
# CLI TEK (fiel ao ASM GetServerArgs())
params = [
    "?listen",
    f"?Port={cfg.server_port}",
    f"?QueryPort={cfg.query_port}",
    f"?MaxPlayers={cfg.max_players}",
]
if cfg.server_ip:
    params.append(f"?MultiHome={cfg.server_ip}")
if cfg.alt_save_directory_name:
    params.append(f"?AltSaveDirectoryName={cfg.alt_save_directory_name}")
if cfg.cross_ark_cluster_id:
    params.append(f"?AltSaveDirectoryName={cfg.alt_save_directory_name}")
    params.append(f"?PreventDownloadItems=False")  # cluster implies download

flags = ["-nosteamclient", "-game", "-server", "-log"]
```

**NÃO incluir na CLI (vai apenas no INI):**

- `?SessionName=` → `[SessionSettings] SessionName`
- `?ServerPassword=` → `[ServerSettings] ServerPassword`
- `?ServerAdminPassword=` → `[ServerSettings] ServerAdminPassword`
- `?RCONEnabled=` → `[ServerSettings] RCONEnabled`
- `?RCONPort=` → `[ServerSettings] RCONPort`
- `?GameModIds=` → `[ServerSettings] ActiveMods`

---

## Funcionalidades Completas (checklist de implementação)

### Engine (asm_engine)

- [ ] `asm_server_config.py` — dataclass com todos os ~300 campos
- [ ] `asm_ini_manager.py` — IniMapper + write_ini + read_ini
- [ ] `asm_server_manager.py` — start / stop / restart / monitor de processo
- [ ] `asm_steamcmd.py` — install / update / validate (SteamCMD)
- [ ] `asm_rcon.py` — conexão RCON, envio de comandos, log de respostas
- [ ] `asm_scheduler.py` — auto-shutdown, auto-restart, auto-update agendados

### UI (asm_ui)

- [ ] `asm_dashboard.py` — lista de servidores TEK, status, botões de ação
- [ ] `asm_server_card.py` — card de servidor com status online/offline/updating
- [ ] `asm_server_panel.py` — container das abas de config
- [ ] `asm_tab_administration.py` — Nome, senhas, rede, RCON, mods, MOTD, saves, branch
- [ ] `asm_tab_rules.py` — PvP/PvE, dificuldade, tribos, transfers, XP, doenças
- [ ] `asm_tab_chat.py` — Voice chat, proximity, notificações de join/leave
- [ ] `asm_tab_hud.py` — Crosshair, HUD, terceira pessoa, mapa, gamma
- [ ] `asm_tab_players.py` — Multiplicadores de player (XP, dano, resistência, etc.)
- [ ] `asm_tab_dinos.py` — Multiplicadores de dino, taming, breeding, imprinting
- [ ] `asm_tab_environment.py` — Ciclo dia/noite, colheita, recursos, temperatura
- [ ] `asm_tab_structures.py` — Dano, decay, limites, torretas
- [ ] `asm_tab_engrams.py` — Lista de engrams editável (hide/force unlock/cost)
- [ ] `asm_tab_levels.py` — Tabela de níveis de jogador e dino (XP + engram points)
- [ ] `asm_tab_mods.py` — Gerenciador de mods (instalação, ordem, Workshop browser)
- [ ] `asm_tab_custom.py` — INI personalizado (editor livre de GameUserSettings/Game.ini)
- [ ] `asm_rcon_window.py` — Console RCON interativo
- [ ] `asm_player_list.py` — Lista de jogadores conectados com ações (kick, ban, whitelist)
- [ ] `asm_workshop.py` — Browser de mods do Workshop Steam
- [ ] `asm_save_restore.py` — Backup e restore de saves do mundo
- [ ] `asm_scheduler_ui.py` — UI do agendador de tarefas

### Integração no App

- [ ] Switch PRIMITIVE/TEK no header do app principal
- [ ] Persistência do modo ativo no `AppConfig`
- [ ] Separação de dados: `data/servers/` (PRIMITIVE) vs `data/asm_servers/` (TEK)
- [ ] Import/export de perfis entre os dois modos (opcional)

---

## Decisões Pendentes

1. **Resultado do T13** — confirmar se o crash é de instalação ou de config antes de iniciar o TEK
2. **Visual do TEK** — definir cor/tema da UI (proposta: azul/teal, diferente do verde PRIMITIVE)
3. **Persistência de configuração** — formato JSON idêntico ao PRIMITIVE, ou novo schema?
4. **Migração** — haverá ferramenta para migrar configs PRIMITIVE → TEK?
5. **Abas complexas** — engrams e levels requerem tabelas editáveis dinâmicas; definir componente CTk a usar
