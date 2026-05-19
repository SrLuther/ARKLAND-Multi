"""
Leitura e escrita dos arquivos INI do ARK: Survival Evolved.
Suporta GameUserSettings.ini e Game.ini.
"""
from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional

from .server_config import ServerConfig


# ── Mapeamento GameUserSettings.ini ──────────────────────────────────────────
# (campo_python, secao_ini, chave_ini, tipo)
_GUS_SERVER_SETTINGS = [
    ("difficulty_offset",                     "ServerSettings", "DifficultyOffset",                     float),
    ("override_official_difficulty",          "ServerSettings", "OverrideOfficialDifficulty",            float),
    ("xp_multiplier",                         "ServerSettings", "XPMultiplier",                         float),
    ("taming_speed_multiplier",               "ServerSettings", "TamingSpeedMultiplier",                 float),
    ("harvest_amount_multiplier",             "ServerSettings", "HarvestAmountMultiplier",               float),
    ("resource_respawn_period_multiplier",    "ServerSettings", "ResourcesRespawnPeriodMultiplier",      float),
    ("harvest_health_multiplier",             "ServerSettings", "HarvestHealthMultiplier",               float),
    ("dino_count_multiplier",                 "ServerSettings", "DinoCountMultiplier",                   float),
    ("max_tamed_dinos",                       "ServerSettings", "MaxTamedDinos",                         int),
    ("player_damage_multiplier",              "ServerSettings", "PlayerDamageMultiplier",                float),
    ("player_resistance_multiplier",          "ServerSettings", "PlayerResistanceMultiplier",            float),
    ("player_character_water_drain_multiplier",  "ServerSettings", "PlayerCharacterWaterDrainMultiplier",   float),
    ("player_character_food_drain_multiplier",   "ServerSettings", "PlayerCharacterFoodDrainMultiplier",    float),
    ("player_character_health_recovery_multiplier","ServerSettings","PlayerCharacterHealthRecoveryMultiplier",float),
    ("player_character_stamina_drain_multiplier","ServerSettings", "PlayerCharacterStaminaDrainMultiplier",  float),
    ("dino_damage_multiplier",                "ServerSettings", "DinoDamageMultiplier",                  float),
    ("dino_resistance_multiplier",            "ServerSettings", "DinoResistanceMultiplier",              float),
    ("dino_character_health_recovery_multiplier","ServerSettings","DinoCharacterHealthRecoveryMultiplier",  float),
    ("dino_character_food_drain_multiplier",  "ServerSettings", "DinoCharacterFoodDrainMultiplier",      float),
    # Breeding — também escritos em Game.ini (local canônico, prioridade). GUS serve de fallback.
    ("baby_mature_speed_multiplier",          "ServerSettings", "BabyMatureSpeedMultiplier",             float),
    ("baby_hatch_speed_multiplier",           "ServerSettings", "BabyHatchSpeedMultiplier",              float),
    ("baby_food_consumption_speed_multiplier","ServerSettings", "BabyFoodConsumptionSpeedMultiplier",    float),
    ("baby_cuddle_interval_multiplier",       "ServerSettings", "BabyCuddleIntervalMultiplier",          float),
    ("mating_interval_multiplier",            "ServerSettings", "MatingIntervalMultiplier",              float),
    ("egg_hatch_speed_multiplier",            "ServerSettings", "EggHatchSpeedMultiplier",               float),
    ("lay_egg_interval_multiplier",           "ServerSettings", "LayEggIntervalMultiplier",              float),
    ("baby_imprinting_stat_scale_multiplier", "ServerSettings", "BabyImprintingStatScaleMultiplier",     float),
    ("baby_cuddle_grace_period_multiplier",   "ServerSettings", "BabyCuddleGracePeriodMultiplier",       float),
    ("structure_damage_multiplier",           "ServerSettings", "StructureDamageMultiplier",             float),
    ("structure_resistance_multiplier",       "ServerSettings", "StructureResistanceMultiplier",         float),
    ("structure_damage_repair_cooldown",      "ServerSettings", "StructureDamageRepairCooldown",         int),
    ("pve_structure_decay_period_multiplier", "ServerSettings", "PvEStructureDecayPeriodMultiplier",     float),
    ("pve_structure_decay_destruction_period","ServerSettings", "PvEStructureDecayDestructionPeriod",    float),
    ("crop_growth_speed_multiplier",          "ServerSettings", "CropGrowthSpeedMultiplier",             float),
    ("crop_decay_speed_multiplier",           "ServerSettings", "CropDecaySpeedMultiplier",              float),
    ("allow_flyer_carry_pve",                 "ServerSettings", "AllowFlyerCarryPVE",                    bool),
    ("disable_structure_decay_pve",           "ServerSettings", "DisableStructureDecayPVE",              bool),
    ("disable_dino_decay_pve",                "ServerSettings", "DisableDinoDecayPVE",                   bool),
    ("prevent_offline_pvp",                   "ServerSettings", "PreventOfflinePVP",                     bool),
    ("show_map_player_location",              "ServerSettings", "ShowMapPlayerLocation",                 bool),
    ("allow_third_person_player",             "ServerSettings", "AllowThirdPersonPlayer",                bool),
    ("always_notify_player_joined",           "ServerSettings", "AlwaysNotifyPlayerJoined",              bool),
    ("always_notify_player_left",             "ServerSettings", "AlwaysNotifyPlayerLeft",                bool),
    ("server_hardcore",                       "ServerSettings", "ServerHardcore",                        bool),
    ("server_pvp",                            "ServerSettings", "ServerPVP",                             bool),
    ("no_tribute_downloads",                  "ServerSettings", "NoTributeDownloads",                    bool),
    ("item_stack_size_multiplier",            "ServerSettings", "ItemStackSizeMultiplier",               float),
    ("spoiling_time_multiplier",              "ServerSettings", "SpoilingTimeMultiplier",                float),
    ("item_decomposition_time_multiplier",    "ServerSettings", "ItemDecompositionTimeMultiplier",       float),
    ("kick_idle_players_period",              "ServerSettings", "KickIdlePlayersPeriod",                 float),
    ("platform_saddle_build_area_bounds_multiplier","ServerSettings","PlatformSaddleBuildAreaBoundsMultiplier",float),
    ("per_platform_max_structures_multiplier","ServerSettings", "PerPlatformMaxStructuresMultiplier",    float),
    ("kill_xp_multiplier",                    "ServerSettings", "KillXPMultiplier",                      float),
    ("harvest_xp_multiplier",                 "ServerSettings", "HarvestXPMultiplier",                   float),
    ("craft_xp_multiplier",                   "ServerSettings", "CraftXPMultiplier",                     float),
    ("generic_xp_multiplier",                 "ServerSettings", "GenericXPMultiplier",                   float),
    ("special_xp_multiplier",                 "ServerSettings", "SpecialXPMultiplier",                   float),
    ("fishing_loot_quality_multiplier",       "ServerSettings", "FishingLootQualityMultiplier",          float),
    ("max_tribe_size",                        "ServerSettings", "MaxTribeSize",                          int),
    ("tribe_name_change_cooldown",            "ServerSettings", "TribeNameChangeCooldown",               float),
    ("override_max_experience_points_player", "ServerSettings", "OverrideMaxExperiencePointsPlayer",     int),
    ("override_max_experience_points_dino",   "ServerSettings", "OverrideMaxExperiencePointsDino",       int),
]

# ── Mapeamento Game.ini [/Script/ShooterGame.ShooterGameMode] → game_settings ──────────────────────
# Local canônico para breeding multipliers. Têm precedência sobre GameUserSettings.ini [ServerSettings].
_GAME_INI_SECTION = "/Script/ShooterGame.ShooterGameMode"
_GAME_INI_GAME_SETTINGS = [
    ("baby_mature_speed_multiplier",           "BabyMatureSpeedMultiplier",             float),
    ("baby_hatch_speed_multiplier",            "BabyHatchSpeedMultiplier",              float),
    ("baby_food_consumption_speed_multiplier", "BabyFoodConsumptionSpeedMultiplier",    float),
    ("baby_cuddle_interval_multiplier",        "BabyCuddleIntervalMultiplier",          float),
    ("mating_interval_multiplier",             "MatingIntervalMultiplier",              float),
    ("egg_hatch_speed_multiplier",             "EggHatchSpeedMultiplier",               float),
    ("lay_egg_interval_multiplier",            "LayEggIntervalMultiplier",              float),
    ("baby_imprinting_stat_scale_multiplier",  "BabyImprintingStatScaleMultiplier",     float),
    ("baby_cuddle_grace_period_multiplier",    "BabyCuddleGracePeriodMultiplier",       float),
]

# Campos da secao [SessionSettings] / [/Script/Engine.GameSession]
_GUS_SESSION_SETTINGS = [
    ("max_players",       "SessionSettings", "MaxPlayers",           int),
    ("server_name",       "SessionSettings", "SessionName",          str),
    ("server_password",   "SessionSettings", "ServerPassword",       str),
    ("admin_password",    "SessionSettings", "ServerAdminPassword",  str),
    ("server_port",       "SessionSettings", "Port",                 int),
    ("query_port",        "SessionSettings", "QueryPort",            int),
]


def _str_to_bool(v: str) -> bool:
    return v.strip().lower() in ("true", "1", "yes")


def _bool_to_str(v: bool) -> str:
    return "True" if v else "False"


def _coerce(value: str, typ):
    if typ is bool:
        return _str_to_bool(value)
    if typ is int:
        return int(float(value))
    if typ is float:
        return float(value)
    return value


def get_ini_path(install_dir: str, filename: str) -> Path:
    """Retorna o caminho do arquivo INI dentro da instalação ARK."""
    return (
        Path(install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / filename
    )


_INI_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "cp1252",
    "latin-1",
)


def _bom_encoding(path: Path) -> Optional[str]:
    """Detecta BOM nos primeiros bytes e retorna o encoding correspondente."""
    try:
        bom = path.read_bytes()[:4]
    except OSError:
        return None
    if bom[:3] == b'\xef\xbb\xbf':
        return "utf-8-sig"
    if bom[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return "utf-16"
    return None


def _ordered_encodings(path: Path) -> tuple:
    """Retorna _INI_ENCODINGS com o encoding detectado pelo BOM em primeiro lugar."""
    detected = _bom_encoding(path)
    if detected is None:
        return _INI_ENCODINGS
    return (detected,) + tuple(e for e in _INI_ENCODINGS if e != detected)


def _read_text_with_fallback(path: Path) -> str:
    """Lê texto com fallback para codificações comuns em INIs no Windows."""
    last_error: Optional[Exception] = None
    for enc in _ordered_encodings(path):
        try:
            text = path.read_text(encoding=enc)
            return text.lstrip('\ufeff')
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError(f"Nao foi possivel ler o arquivo INI: {path}")


def _read_ini_with_fallback(path: Path, strict: bool = False) -> configparser.RawConfigParser:
    """Lê INI aceitando codificações comuns no Windows e retorna o parser populado."""
    last_error: Optional[Exception] = None

    for enc in _ordered_encodings(path):
        try:
            text = path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
            continue

        text = text.lstrip('\ufeff')  # remove BOM remanescente (ex: utf-16-le sem strip)
        parser = configparser.RawConfigParser(strict=strict)
        parser.optionxform = str  # type: ignore[method-assign]  # preserva maiúsculas/minúsculas das chaves
        try:
            parser.read_string(text, source=str(path))
            return parser
        except configparser.Error as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError(f"Nao foi possivel interpretar o arquivo INI: {path}")


def read_ini_with_fallback(path: Path, strict: bool = False) -> configparser.RawConfigParser:
    """API publica para leitura de INI com fallback de encoding."""
    return _read_ini_with_fallback(path, strict=strict)


def _write_encoding(path: Path) -> str:
    """Retorna o encoding para escrever o arquivo preservando o BOM original.

    Se o arquivo existir e tiver BOM conhecido, usa o mesmo encoding.
    Caso contrário, usa utf-8 (sem BOM) como padrão seguro.
    """
    if path.exists():
        detected = _bom_encoding(path)
        if detected:
            return detected
    return "utf-8"


# ── Funções de população de config a partir de parsers já carregados ─────────

# ── Mapeamento de args de linha de comando → campos Python ───────────────────
# Construído automaticamente a partir de _GUS_SERVER_SETTINGS:
# chave lowercase do arg ?Key=Value  →  (field_name, tipo)
_CMDLINE_MAP: dict[str, tuple[str, type]] = {
    key.lower(): (field_name, typ)
    for field_name, _section, key, typ in _GUS_SERVER_SETTINGS
}


def parse_cmdline_args(text: str) -> dict[str, str]:
    """Extrai pares ?Key=Value da linha de chamada ao ShooterGameServer.exe num arquivo .bat/.cmd.

    Retorna dicionário com as chaves em lowercase.
    """
    import re
    match = re.search(r'ShooterGameServer\.exe\s+(.+)', text, re.IGNORECASE)
    if not match:
        return {}
    args_str = match.group(1)
    return {k.lower(): v for k, v in re.findall(r'\?([A-Za-z0-9_]+)=([^\s?]+)', args_str)}


def find_startup_bat(folder: Path) -> Optional[Path]:
    """Procura um .bat ou .cmd que contenha 'ShooterGameServer.exe' na pasta informada
    e em até 4 níveis de pastas-pai.  Retorna o primeiro encontrado, ou None.
    """
    candidate = folder
    for _ in range(5):
        for ext in ("*.bat", "*.cmd"):
            for bat in candidate.glob(ext):
                try:
                    content = bat.read_text(encoding="utf-8", errors="replace")
                    if "ShooterGameServer.exe" in content:
                        return bat
                except OSError:
                    continue
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


# Campos de ServerConfig (não game_settings) passados via ?Arg= na linha de comando
_CMDLINE_CONFIG_MAP: dict[str, tuple[str, type]] = {
    "port":                   ("server_port",       int),
    "queryport":              ("query_port",         int),
    "maxplayers":             ("max_players",        int),
    "sessionname":            ("server_name",        str),
    "serverpassword":         ("server_password",    str),
    "serveradminpassword":    ("admin_password",      str),
    "rconenabled":            ("rcon_enabled",        bool),
    "rconport":               ("rcon_port",           int),
    "autosaveperiodminutes":  ("auto_save_period",    float),
    "activeevent":            ("active_event",        str),
}


def apply_cmdline_args_to_config(args: dict[str, str], config: ServerConfig) -> None:
    """Aplica os args de linha de comando (já parseados) sobre ServerConfig.

    Cobre game_settings (via _CMDLINE_MAP) e campos diretos de ServerConfig
    (via _CMDLINE_CONFIG_MAP). Os args têm precedência sobre o INI.
    """
    gs = config.game_settings
    for key_lower, value in args.items():
        if key_lower in _CMDLINE_MAP:
            field_name, typ = _CMDLINE_MAP[key_lower]
            try:
                setattr(gs, field_name, _coerce(value, typ))
            except Exception:
                pass
        elif key_lower in _CMDLINE_CONFIG_MAP:
            field_name, typ = _CMDLINE_CONFIG_MAP[key_lower]
            try:
                setattr(config, field_name, _coerce(value, typ))
            except Exception:
                pass


def populate_config_from_gus(
    parser: configparser.RawConfigParser, config: ServerConfig
) -> None:
    """Popula ServerConfig a partir de um parser GameUserSettings.ini já carregado.

    Cobre: ServerSettings, SessionSettings, RCONEnabled/Port e MessageOfTheDay.
    """
    gs = config.game_settings

    for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
        try:
            if parser.has_option(section, key):
                setattr(gs, field_name, _coerce(parser.get(section, key), typ))
        except Exception:
            pass

    for field_name, section, key, typ in _GUS_SESSION_SETTINGS:
        try:
            if parser.has_option(section, key):
                setattr(config, field_name, _coerce(parser.get(section, key), typ))
        except Exception:
            pass

    # RCON
    try:
        if parser.has_option("ServerSettings", "RCONEnabled"):
            config.rcon_enabled = _str_to_bool(parser.get("ServerSettings", "RCONEnabled"))
    except Exception:
        pass
    try:
        if parser.has_option("ServerSettings", "RCONPort"):
            config.rcon_port = int(float(parser.get("ServerSettings", "RCONPort")))
    except Exception:
        pass

    # Mensagem do Dia
    try:
        if parser.has_option("MessageOfTheDay", "Message"):
            config.motd = parser.get("MessageOfTheDay", "Message")
    except Exception:
        pass
    try:
        if parser.has_option("MessageOfTheDay", "Duration"):
            config.motd_duration = int(float(parser.get("MessageOfTheDay", "Duration")))
    except Exception:
        pass

    # Mods
    if parser.has_option("ServerSettings", "ActiveMods"):
        raw_mods = parser.get("ServerSettings", "ActiveMods").strip()
        config.mods = [m.strip() for m in raw_mods.split(",") if m.strip()]

    # AutoSavePeriodMinutes
    try:
        if parser.has_option("ServerSettings", "AutoSavePeriodMinutes"):
            config.auto_save_period = float(parser.get("ServerSettings", "AutoSavePeriodMinutes"))
    except Exception:
        pass

    # ActiveEvent
    try:
        if parser.has_option("ServerSettings", "ActiveEvent"):
            config.active_event = parser.get("ServerSettings", "ActiveEvent").strip()
    except Exception:
        pass


def populate_config_from_game_ini(
    parser: configparser.RawConfigParser, config: ServerConfig
) -> None:
    """Popula ServerConfig.advanced_settings a partir de um parser Game.ini já carregado."""
    adv = config.advanced_settings
    section = "/Script/ShooterGame.ShooterGameMode"

    bool_fields = [
        ("prevent_download_survivors",               "bPreventDownloadSurvivors"),
        ("prevent_download_items",                   "bPreventDownloadItems"),
        ("prevent_download_dinos",                   "bPreventDownloadDinos"),
        ("prevent_upload_survivors",                 "bPreventUploadSurvivors"),
        ("prevent_upload_items",                     "bPreventUploadItems"),
        ("prevent_upload_dinos",                     "bPreventUploadDinos"),
        ("no_transfer_from_filtering",               "NoTransferFromFiltering"),
        ("enable_cryopod_nerf",                      "EnableCryopodNerf"),
        ("allow_crateSpawns_on_top_of_structures",   "AllowCrateSpawnsOnTopOfStructures"),
        ("use_optimized_harvesting_health",          "UseOptimizedHarvestingHealth"),
        ("b_passive_defenses_damage_riderless_dinos","bPassiveDefensesDamageRiderlessDinos"),
        ("global_voice_chat",                        "GlobalVoiceChat"),
        ("proximity_chat",                           "ProximityChat"),
        ("allow_raid_dino_feeding",                  "AllowRaidDinoFeeding"),
        ("b_auto_pve_timer",                         "bAutoPvETimer"),
        ("b_auto_pve_use_system_time",               "bAutoPvEUseSystemTime"),
        ("force_all_structure_locking",              "ForceAllStructureLocking"),
        ("force_flyer_explosives",                   "ForceFlyerExplosives"),
    ]

    float_fields = [
        ("cryopod_nerf_duration",                    "CryopodNerfDuration"),
        ("cryopod_nerf_damage_mult",                 "CryopodNerfDamageMult"),
        ("raid_dino_character_food_drain_multiplier","RaidDinoCharacterFoodDrainMultiplier"),
        ("oxygen_swim_speed_stat_multiplier",        "OxygenSwimSpeedStatMultiplier"),
        ("dino_harvesting_damage_multiplier",        "DinoHarvestingDamageMultiplier"),
        ("player_harvesting_damage_multiplier",      "PlayerHarvestingDamageMultiplier"),
        ("custom_recipe_effectiveness_multiplier",   "CustomRecipeEffectivenessMultiplier"),
        ("custom_recipe_skill_multiplier",           "CustomRecipeSkillMultiplier"),
        ("auto_pve_start_time_seconds",              "AutoPvEStartTimeSeconds"),
        ("auto_pve_stop_time_seconds",               "AutoPvEStopTimeSeconds"),
    ]

    for field_name, key in bool_fields:
        try:
            if parser.has_option(section, key):
                setattr(adv, field_name, _str_to_bool(parser.get(section, key)))
        except Exception:
            pass

    for field_name, key in float_fields:
        try:
            if parser.has_option(section, key):
                setattr(adv, field_name, float(parser.get(section, key)))
        except Exception:
            pass

    # ── Campos de breeding (local canônico: Game.ini) → game_settings ────────
    gs = config.game_settings
    for field_name, key, typ in _GAME_INI_GAME_SETTINGS:
        try:
            if parser.has_option(_GAME_INI_SECTION, key):
                setattr(gs, field_name, _coerce(parser.get(_GAME_INI_SECTION, key), typ))
        except Exception:
            pass

    # ── PerLevelStatsMultiplier — lê os 12 índices de cada grupo ─────────────
    for ini_key, attr in [
        ("PerLevelStatsMultiplier_DinoTamed",          "per_level_stats_mult_dino_tamed"),
        ("PerLevelStatsMultiplier_DinoTamed_Add",      "per_level_stats_mult_dino_tamed_add"),
        ("PerLevelStatsMultiplier_DinoTamed_Affinity", "per_level_stats_mult_dino_tamed_affinity"),
        ("PerLevelStatsMultiplier_DinoWild",           "per_level_stats_mult_dino_wild"),
        ("PerLevelStatsMultiplier_Player",             "per_level_stats_mult_player"),
    ]:
        vals = list(getattr(gs, attr))
        for i in range(12):
            try:
                if parser.has_option(section, f"{ini_key}[{i}]"):
                    vals[i] = float(parser.get(section, f"{ini_key}[{i}]"))
            except Exception:
                pass
        setattr(gs, attr, vals)

    # ── Spawn de Dinos Customizados ──────────────────────────────────────────
    # configparser não preserva chaves duplicadas, por isso lemos as linhas brutas.
    # Tentamos localizar o arquivo a partir do parser source se disponível.
    # A chamada normal passa pelo ArkIniManager, que chama populate_config_from_game_ini
    # passando um parser já lido de um arquivo conhecido — usamos _npc_spawn_path_hint
    # definida logo abaixo; aqui não temos o path, então o caller deve usar
    # populate_npc_spawns_from_file() separadamente.


def populate_npc_spawns_from_file(path: "Path", config: "ServerConfig") -> None:  # noqa: F821
    """Alias para compatibilidade retroativa."""
    populate_custom_game_ini_from_file(path, config)


def populate_custom_game_ini_from_file(path: "Path", config: "ServerConfig") -> None:  # noqa: F821
    """Lê spawns, multiplicadores de dino e supply crates de um Game.ini bruto."""
    adv = config.advanced_settings
    adv.npc_spawn_entries_add = []
    adv.npc_spawn_entries_override = []
    adv.dino_class_resistance_multipliers = []
    adv.dino_class_damage_multipliers = []
    adv.tamed_dino_class_resistance_multipliers = []
    adv.tamed_dino_class_damage_multipliers = []
    adv.supply_crate_overrides = []
    try:
        text = _read_text_with_fallback(path)
    except (OSError, ValueError):
        return
    for line in text.splitlines():
        line = line.strip()
        ll = line.lower()
        if ll.startswith("configaddnpcspawnentriescontainer="):
            value = line[len("configaddnpcspawnentriescontainer="):]
            c = _parse_npc_spawn_container(value)
            if c is not None:
                adv.npc_spawn_entries_add.append(c)
        elif ll.startswith("configoverridenpcspawnentriescontainer="):
            value = line[len("configoverridenpcspawnentriescontainer="):]
            c = _parse_npc_spawn_container(value, is_override=True)
            if c is not None:
                adv.npc_spawn_entries_override.append(c)
        elif ll.startswith("dinoclassresistancemultipliers="):
            e = _parse_dino_class_multiplier(line[len("dinoclassresistancemultipliers="):])
            if e:
                adv.dino_class_resistance_multipliers.append(e)
        elif ll.startswith("dinoclassdamagemultipliers="):
            e = _parse_dino_class_multiplier(line[len("dinoclassdamagemultipliers="):])
            if e:
                adv.dino_class_damage_multipliers.append(e)
        elif ll.startswith("tameddinoclassresistancemultipliers="):
            e = _parse_dino_class_multiplier(line[len("tameddinoclassresistancemultipliers="):])
            if e:
                adv.tamed_dino_class_resistance_multipliers.append(e)
        elif ll.startswith("tameddinoclassdamagemultipliers="):
            e = _parse_dino_class_multiplier(line[len("tameddinoclassdamagemultipliers="):])
            if e:
                adv.tamed_dino_class_damage_multipliers.append(e)
        elif ll.startswith("configoverridesupplycrateitems="):
            value = line[line.index("=") + 1:]
            c = _parse_supply_crate_override(value)
            if c:
                adv.supply_crate_overrides.append(c)


def _parse_npc_spawn_container(value: str, is_override: bool = False):
    """Parseia o valor de uma linha ConfigAdd/OverrideNPCSpawnEntriesContainer.

    Retorna um dict com chaves: container, max_enemies_multiplier, entries.
    Retorna None em caso de falha.

    Formato esperado:
        (NPCSpawnEntriesContainerClassString="DinoSpawnEntriesBeach_C",
         NPCSpawnEntries=((AnEntryName="X",EntryWeight=1.0,
           NPCsToSpawnStrings=("BP'...'"[,...]))[,...]),
         MaxDesiredNumEnemiesMultiplier=1.0)
    """
    import re
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    # Extrai NPCSpawnEntriesContainerClassString
    m = re.search(r'NPCSpawnEntriesContainerClassString\s*=\s*"([^"]*)"', value)
    container_class = m.group(1) if m else ""

    # Extrai MaxDesiredNumEnemiesMultiplier (override only)
    max_mult = 1.0
    m2 = re.search(r'MaxDesiredNumEnemiesMultiplier\s*=\s*([\d.]+)', value)
    if m2:
        try:
            max_mult = float(m2.group(1))
        except ValueError:
            pass

    # Extrai o bloco NPCSpawnEntries=((…))
    entries = []
    m3 = re.search(r'NPCSpawnEntries\s*=\s*\(', value)
    if m3:
        start = m3.end() - 1  # aponta para o '(' externo
        # Avança até o parêntese externo de fechamento
        block = _extract_balanced(value, start)
        if block:
            inner = block[1:-1]  # remove parênteses externos
            # Cada entry começa com '('
            entry_strings = _split_top_level_parens(inner)
            for es in entry_strings:
                entry = _parse_npc_spawn_entry(es)
                if entry is not None:
                    entries.append(entry)

    return {
        "container": container_class,
        "max_enemies_multiplier": max_mult,
        "entries": entries,
    }


def _extract_balanced(text: str, start: int) -> str:
    """Extrai a substring que começa em text[start]='(' e termina no ')' balanceado."""
    if start >= len(text) or text[start] != "(":
        return ""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return ""


def _split_top_level_parens(text: str):
    """Divide a string em itens separados por vírgula no nível mais externo,
    onde cada item pode ser um grupo entre parênteses ou um valor simples."""
    items = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(ch)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _parse_npc_spawn_entry(text: str):
    """Parseia um único entry de NPCSpawnEntries como (AnEntryName=…,EntryWeight=…,NPCsToSpawnStrings=(…))."""
    import re
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    m_name   = re.search(r'AnEntryName\s*=\s*"([^"]*)"', text)
    m_weight = re.search(r'EntryWeight\s*=\s*([\d.]+)', text)
    name   = m_name.group(1)   if m_name   else ""
    try:
        weight = float(m_weight.group(1)) if m_weight else 1.0
    except ValueError:
        weight = 1.0

    # Extrai NPCsToSpawnStrings=(…)
    blueprints: list[str] = []
    m_bp = re.search(r'NPCsToSpawnStrings\s*=\s*\(', text)
    if m_bp:
        start = m_bp.end() - 1
        block = _extract_balanced(text, start)
        if block:
            inner = block[1:-1]
            # cada blueprint é "Blueprint'...'"
            blueprints = [bp.strip().strip('"') for bp in inner.split(",") if bp.strip()]

    return {"name": name, "weight": weight, "blueprints": blueprints}


def _serialize_npc_spawn_container(container: dict, is_override: bool = False) -> str:
    """Serializa um container de spawn de dinos para o formato INI do ARK.

    Retorna a linha completa SEM a chave prefix (ex: só o valor entre parênteses).
    """
    parts = [f'NPCSpawnEntriesContainerClassString="{container.get("container", "")}"']

    # Entries
    entry_strs = []
    for entry in container.get("entries", []):
        name     = entry.get("name", "")
        weight   = entry.get("weight", 1.0)
        bps      = entry.get("blueprints", [])
        bp_str   = ",".join(f'"{bp}"' for bp in bps)
        entry_strs.append(
            f'(AnEntryName="{name}",EntryWeight={weight},NPCsToSpawnStrings=({bp_str}))'
        )
    entries_inner = ",".join(entry_strs)
    parts.append(f"NPCSpawnEntries=({entries_inner})")

    if is_override:
        mult = container.get("max_enemies_multiplier", 1.0)
        parts.append(f"MaxDesiredNumEnemiesMultiplier={mult}")

    return "(" + ",".join(parts) + ")"


# ── Multiplicadores por Classe de Dino ─────────────────────────────────────

def _parse_dino_class_multiplier(value: str):
    """Parseia (ClassName="<name>",Multiplier=<float>)."""
    import re
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    m = re.search(r'ClassName\s*=\s*"([^"]*)"', value)
    if not m:
        return None
    m2 = re.search(r'Multiplier\s*=\s*([\d.]+)', value)
    try:
        mult = float(m2.group(1)) if m2 else 1.0
    except ValueError:
        mult = 1.0
    return {"class_name": m.group(1), "multiplier": mult}


def _serialize_dino_class_multiplier(entry: dict) -> str:
    return f'(ClassName="{entry.get("class_name", "")}",Multiplier={entry.get("multiplier", 1.0)})'


# ── Supply Crate Item Overrides ─────────────────────────────────────────────

def _parse_supply_item_entry(text: str):
    """Parseia um ItemEntry de supply crate."""
    import re
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    def _flt(pat, default=1.0):
        m = re.search(pat, text)
        try:
            return float(m.group(1)) if m else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=False):
        m = re.search(pat, text)
        return m.group(1).strip().lower() in ("true", "1") if m else default

    weight    = _flt(r'EntryWeight\s*=\s*([\d.]+)', 1.0)
    min_qty   = _flt(r'MinQuantity\s*=\s*([\d.]+)', 1.0)
    max_qty   = _flt(r'MaxQuantity\s*=\s*([\d.]+)', 1.0)
    min_ql    = _flt(r'MinQuality\s*=\s*([\d.]+)', 1.0)
    max_ql    = _flt(r'MaxQuality\s*=\s*([\d.]+)', 1.0)
    force_bp  = _bl(r'bForceBlueprint\s*=\s*(\w+)', False)
    bp_chance = _flt(r'ChanceToBeBlueprintOverride\s*=\s*([\d.]+)', 0.0)

    items: list[str] = []
    m_items = re.search(r'ItemClassStrings\s*=\s*\(', text)
    if m_items:
        block = _extract_balanced(text, m_items.end() - 1)
        if block:
            items = [s.strip().strip('"') for s in block[1:-1].split(",") if s.strip()]

    return {
        "weight": weight,
        "items": items,
        "min_qty": min_qty,
        "max_qty": max_qty,
        "min_quality": min_ql,
        "max_quality": max_ql,
        "force_blueprint": force_bp,
        "blueprint_chance": bp_chance,
    }


def _parse_supply_item_set(text: str):
    """Parseia um ItemSet de supply crate."""
    import re
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]

    def _flt(pat, default=1.0):
        m = re.search(pat, text)
        try:
            return float(m.group(1)) if m else default
        except (ValueError, AttributeError):
            return default

    def _int(pat, default=1):
        m = re.search(pat, text)
        try:
            return int(float(m.group(1))) if m else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=True):
        m = re.search(pat, text)
        return m.group(1).strip().lower() in ("true", "1") if m else default

    entries: list[dict] = []
    m_e = re.search(r'ItemEntries\s*=\s*\(', text)
    if m_e:
        block = _extract_balanced(text, m_e.end() - 1)
        if block:
            for es in _split_top_level_parens(block[1:-1]):
                e = _parse_supply_item_entry(es)
                if e is not None:
                    entries.append(e)

    return {
        "min_items":          _int(r'MinNumItems\s*=\s*([\d.]+)', 1),
        "max_items":          _int(r'MaxNumItems\s*=\s*([\d.]+)', 2),
        "num_items_power":    _flt(r'NumItemsPower\s*=\s*([\d.]+)', 1.0),
        "set_weight":         _flt(r'SetWeight\s*=\s*([\d.]+)', 1.0),
        "items_no_replacement": _bl(r'bItemsRandomWithoutReplacement\s*=\s*(\w+)', True),
        "entries":            entries,
    }


def _parse_supply_crate_override(value: str):
    """Parseia o valor de uma linha ConfigOverrideSupplyCrateItems."""
    import re
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    m = re.search(r'SupplyCrateClassString\s*=\s*"([^"]*)"', value)
    crate_class = m.group(1) if m else ""

    def _flt(pat, default=1.0):
        m2 = re.search(pat, value)
        try:
            return float(m2.group(1)) if m2 else default
        except (ValueError, AttributeError):
            return default

    def _int(pat, default=1):
        m2 = re.search(pat, value)
        try:
            return int(float(m2.group(1))) if m2 else default
        except (ValueError, AttributeError):
            return default

    def _bl(pat, default=True):
        m2 = re.search(pat, value)
        return m2.group(1).strip().lower() in ("true", "1") if m2 else default

    item_sets: list[dict] = []
    m_s = re.search(r'ItemSets\s*=\s*\(', value)
    if m_s:
        block = _extract_balanced(value, m_s.end() - 1)
        if block:
            for ss in _split_top_level_parens(block[1:-1]):
                s = _parse_supply_item_set(ss)
                if s is not None:
                    item_sets.append(s)

    return {
        "crate_class":       crate_class,
        "min_sets":          _int(r'MinItemSets\s*=\s*([\d.]+)', 1),
        "max_sets":          _int(r'MaxItemSets\s*=\s*([\d.]+)', 1),
        "num_sets_power":    _flt(r'NumItemSetsPower\s*=\s*([\d.]+)', 1.0),
        "sets_no_replacement": _bl(r'bSetsRandomWithoutReplacement\s*=\s*(\w+)', True),
        "item_sets":         item_sets,
    }


def _serialize_supply_crate_override(crate: dict) -> str:
    """Serializa um supply crate override para o formato INI do ARK."""
    set_strs: list[str] = []
    for item_set in crate.get("item_sets", []):
        entry_strs: list[str] = []
        for entry in item_set.get("entries", []):
            items = entry.get("items", [])
            items_str = ",".join('"' + i + '"' for i in items)
            weights_str = ",".join("1.0" for _ in items)
            ep = (
                f'EntryWeight={entry.get("weight", 1.0)},'
                f'ItemClassStrings=({items_str}),'
                f'ItemsWeights=({weights_str}),'
                f'MinQuantity={entry.get("min_qty", 1.0)},'
                f'MaxQuantity={entry.get("max_qty", 1.0)},'
                f'MinQuality={entry.get("min_quality", 1.0)},'
                f'MaxQuality={entry.get("max_quality", 1.0)},'
                f'bForceBlueprint={"True" if entry.get("force_blueprint", False) else "False"},'
                f'ChanceToBeBlueprintOverride={entry.get("blueprint_chance", 0.0)}'
            )
            entry_strs.append(f'({ep})')
        sp = (
            f'MinNumItems={item_set.get("min_items", 1)},'
            f'MaxNumItems={item_set.get("max_items", 2)},'
            f'NumItemsPower={item_set.get("num_items_power", 1.0)},'
            f'SetWeight={item_set.get("set_weight", 1.0)},'
            f'bItemsRandomWithoutReplacement={"True" if item_set.get("items_no_replacement", True) else "False"},'
            f'ItemEntries=({",".join(entry_strs)})'
        )
        set_strs.append(f'({sp})')

    parts = (
        f'SupplyCrateClassString="{crate.get("crate_class", "")}",'
        f'MinItemSets={crate.get("min_sets", 1)},'
        f'MaxItemSets={crate.get("max_sets", 1)},'
        f'NumItemSetsPower={crate.get("num_sets_power", 1.0)},'
        f'bSetsRandomWithoutReplacement={"True" if crate.get("sets_no_replacement", True) else "False"},'
        f'ItemSets=({",".join(set_strs)})'
    )
    return f'({parts})'


# ══════════════════════════════════════════════════════════════════════════════

def _level_to_xp(level: int) -> int:
    """Converte nível-teto em XP total cumulativo usando a curva padrão do ARK SE.

    Fórmula: soma de round(0.667 * i^2.04) para i de 1 a level-1.
    Dá ~226 000 XP para atingir o nível 100 (curva default).
    """
    if level <= 1:
        return 0
    return sum(max(1, round(0.667 * i ** 2.04)) for i in range(1, level))


# ── Helpers para edição estruturada de INI ────────────────────────────────────

def parse_ini_text_to_sections(text: str) -> list:
    """Converte texto INI bruto em lista de seções estruturadas.

    Retorna::

        [{"section": str, "entries": [{"key": str, "value": str}]}, ...]

    Seções sem nenhuma entrada são incluídas (lista de entries vazia).
    Linhas de comentário (;  ou  #) são ignoradas.
    """
    sections: list = []
    current: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = {"section": line[1:-1], "entries": []}
            sections.append(current)
        elif "=" in line and current is not None:
            key, _, value = line.partition("=")
            current["entries"].append({"key": key.strip(), "value": value.strip()})
    return sections


def sections_to_ini_text(sections: list) -> str:
    """Serializa lista de seções de volta para texto INI bruto."""
    lines: list = []
    for sec in sections:
        sec_name = (sec.get("section") or "").strip()
        if not sec_name:
            continue
        lines.append(f"[{sec_name}]")
        for entry in sec.get("entries", []):
            key = (entry.get("key") or "").strip()
            value = (entry.get("value") or "").strip()
            if key:
                lines.append(f"{key}={value}")
        lines.append("")
    return "\n".join(lines)


# Chaves oficialmente suportadas pelo ?customdynamicconfigurl= do ARK (patch 307.2+).
# Apenas estas são aplicadas em tempo real, sem reinicialização do servidor.
# A seção [/Script/ShooterGame.ShooterGameMode] NÃO é suportada neste sistema.
_DYNAMIC_CONFIG_KEYS = [
    # (campo_em_ServerGameSettings, chave_ini)
    ("taming_speed_multiplier",               "TamingSpeedMultiplier"),
    ("harvest_amount_multiplier",             "HarvestAmountMultiplier"),
    ("xp_multiplier",                         "XPMultiplier"),
    ("mating_interval_multiplier",            "MatingIntervalMultiplier"),
    ("baby_mature_speed_multiplier",          "BabyMatureSpeedMultiplier"),
    ("egg_hatch_speed_multiplier",            "EggHatchSpeedMultiplier"),
    ("baby_food_consumption_speed_multiplier","BabyFoodConsumptionSpeedMultiplier"),
    ("crop_growth_speed_multiplier",          "CropGrowthSpeedMultiplier"),
    ("baby_cuddle_interval_multiplier",       "BabyCuddleIntervalMultiplier"),
    ("baby_imprinting_stat_scale_multiplier", "BabyImprintingStatScaleMultiplier"),
]


def build_dynamic_config(config: ServerConfig) -> str:
    """Gera conteúdo INI para ?customdynamicconfigurl= do ARK (patch 307.2+).

    Inclui apenas as chaves em _DYNAMIC_CONFIG_KEYS — as únicas que o ARK
    aplica em tempo real sem reinicialização do servidor.

    Args:
        config: Configuração do servidor a partir da qual gerar o conteúdo.

    Returns:
        String no formato INI pronta para ser servida via HTTP.
    """
    import io

    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[method-assign]  # preserva case das chaves

    section = "ServerSettings"
    parser.add_section(section)

    gs = config.game_settings
    for field_name, key in _DYNAMIC_CONFIG_KEYS:
        value = getattr(gs, field_name, None)
        if value is None:
            continue
        parser.set(section, key, str(value))

    # ActiveEvent — suportado na prática (Wildcard usava para eventos oficiais)
    if config.active_event:
        parser.set(section, "ActiveEvent", config.active_event)

    buf = io.StringIO()
    parser.write(buf)
    return buf.getvalue()


class ArkIniManager:
    """Lê e escreve GameUserSettings.ini e Game.ini de um servidor ARK."""

    def __init__(self, install_dir: str) -> None:
        self._install_dir = install_dir

    # ── Leitura ───────────────────────────────────────────────────────────────

    def load_game_user_settings(self, config: ServerConfig) -> None:
        """Popula ServerConfig com os valores de GameUserSettings.ini."""
        path = get_ini_path(self._install_dir, "GameUserSettings.ini")
        if not path.exists():
            return
        parser = _read_ini_with_fallback(path, strict=False)
        populate_config_from_gus(parser, config)

    def load_game_ini(self, config: ServerConfig) -> None:
        """Popula ServerConfig.advanced_settings com valores de Game.ini."""
        path = get_ini_path(self._install_dir, "Game.ini")
        if not path.exists():
            return
        parser = _read_ini_with_fallback(path, strict=False)
        populate_config_from_game_ini(parser, config)
        populate_custom_game_ini_from_file(path, config)

    # ── Escrita ───────────────────────────────────────────────────────────────

    def save_game_user_settings(self, config: ServerConfig) -> None:
        """Escreve GameUserSettings.ini com os valores do ServerConfig."""
        path = get_ini_path(self._install_dir, "GameUserSettings.ini")
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.RawConfigParser()
        parser.optionxform = str  # type: ignore[method-assign]  # preserva maiúsculas/minúsculas das chaves
        if path.exists():
            parser = _read_ini_with_fallback(path)

        gs = config.game_settings

        for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
            if not parser.has_section(section):
                parser.add_section(section)
            value = getattr(gs, field_name)
            if typ is bool:
                parser.set(section, key, _bool_to_str(value))
            else:
                parser.set(section, key, str(value))

        # Se level_cap > 0, sobrepõe o XP calculado pela curva padrão
        if gs.player_level_cap > 0:
            parser.set("ServerSettings", "OverrideMaxExperiencePointsPlayer",
                       str(_level_to_xp(gs.player_level_cap)))
        if gs.dino_level_cap > 0:
            parser.set("ServerSettings", "OverrideMaxExperiencePointsDino",
                       str(_level_to_xp(gs.dino_level_cap)))

        for field_name, section, key, typ in _GUS_SESSION_SETTINGS:
            if not parser.has_section(section):
                parser.add_section(section)
            value = getattr(config, field_name)
            if typ is bool:
                parser.set(section, key, _bool_to_str(value))
            else:
                parser.set(section, key, str(value))

        # Mods
        if not parser.has_section("ServerSettings"):
            parser.add_section("ServerSettings")
        if config.mods:
            parser.set("ServerSettings", "ActiveMods", ",".join(config.mods))

        # RCON
        if not parser.has_section("ServerSettings"):
            parser.add_section("ServerSettings")
        parser.set("ServerSettings", "RCONEnabled", _bool_to_str(config.rcon_enabled))
        parser.set("ServerSettings", "RCONPort",    str(config.rcon_port))

        # AutoSavePeriodMinutes / ActiveEvent
        parser.set("ServerSettings", "AutoSavePeriodMinutes", str(config.auto_save_period))
        if config.active_event:
            parser.set("ServerSettings", "ActiveEvent", config.active_event)
        elif parser.has_option("ServerSettings", "ActiveEvent"):
            parser.remove_option("ServerSettings", "ActiveEvent")

        # Mensagem do Dia (MOTD)
        motd_section = "MessageOfTheDay"
        if not parser.has_section(motd_section):
            parser.add_section(motd_section)
        parser.set(motd_section, "Message",  config.motd)
        parser.set(motd_section, "Duration", str(config.motd_duration))

        with open(str(path), "w", encoding=_write_encoding(path)) as fh:
            parser.write(fh)

    def save_game_ini(self, config: ServerConfig) -> None:
        """Escreve Game.ini com os valores de ServerConfig.advanced_settings."""
        import re as _re
        path = get_ini_path(self._install_dir, "Game.ini")
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.RawConfigParser()
        parser.optionxform = str  # type: ignore[method-assign]  # preserva maiúsculas/minúsculas das chaves
        if path.exists():
            parser = _read_ini_with_fallback(path)

        section = "/Script/ShooterGame.ShooterGameMode"
        if not parser.has_section(section):
            parser.add_section(section)

        adv = config.advanced_settings

        mappings: list[tuple] = [
            ("bPreventDownloadSurvivors",               adv.prevent_download_survivors,              bool),
            ("bPreventDownloadItems",                   adv.prevent_download_items,                  bool),
            ("bPreventDownloadDinos",                   adv.prevent_download_dinos,                  bool),
            ("bPreventUploadSurvivors",                 adv.prevent_upload_survivors,                bool),
            ("bPreventUploadItems",                     adv.prevent_upload_items,                    bool),
            ("bPreventUploadDinos",                     adv.prevent_upload_dinos,                    bool),
            ("NoTransferFromFiltering",                 adv.no_transfer_from_filtering,              bool),
            ("EnableCryopodNerf",                       adv.enable_cryopod_nerf,                     bool),
            ("CryopodNerfDuration",                     adv.cryopod_nerf_duration,                   float),
            ("CryopodNerfDamageMult",                   adv.cryopod_nerf_damage_mult,                float),
            ("AllowCrateSpawnsOnTopOfStructures",       adv.allow_crateSpawns_on_top_of_structures,  bool),
            ("UseOptimizedHarvestingHealth",            adv.use_optimized_harvesting_health,         bool),
            ("bPassiveDefensesDamageRiderlessDinos",    adv.b_passive_defenses_damage_riderless_dinos, bool),
            ("GlobalVoiceChat",                         adv.global_voice_chat,                       bool),
            ("ProximityChat",                           adv.proximity_chat,                          bool),
            ("AllowRaidDinoFeeding",                    adv.allow_raid_dino_feeding,                 bool),
            ("RaidDinoCharacterFoodDrainMultiplier",    adv.raid_dino_character_food_drain_multiplier, float),
            ("OxygenSwimSpeedStatMultiplier",           adv.oxygen_swim_speed_stat_multiplier,       float),
            ("DinoHarvestingDamageMultiplier",          adv.dino_harvesting_damage_multiplier,       float),
            ("PlayerHarvestingDamageMultiplier",        adv.player_harvesting_damage_multiplier,     float),
            ("CustomRecipeEffectivenessMultiplier",     adv.custom_recipe_effectiveness_multiplier,  float),
            ("CustomRecipeSkillMultiplier",             adv.custom_recipe_skill_multiplier,          float),
            ("bAutoPvETimer",                           adv.b_auto_pve_timer,                        bool),
            ("bAutoPvEUseSystemTime",                   adv.b_auto_pve_use_system_time,              bool),
            ("AutoPvEStartTimeSeconds",                 adv.auto_pve_start_time_seconds,             float),
            ("AutoPvEStopTimeSeconds",                  adv.auto_pve_stop_time_seconds,              float),
            ("ForceAllStructureLocking",                adv.force_all_structure_locking,             bool),
            ("ForceFlyerExplosives",                    adv.force_flyer_explosives,                  bool),
        ]

        for key, value, typ in mappings:
            if typ is bool:
                parser.set(section, key, _bool_to_str(value))
            else:
                parser.set(section, key, str(value))

        # ── Campos de breeding (local canônico: Game.ini) ─────────────────
        gs = config.game_settings
        for field_name, key, typ in _GAME_INI_GAME_SETTINGS:
            parser.set(section, key, str(getattr(gs, field_name)))

        # ── PerLevelStatsMultiplier — escreve apenas valores não-padrão ───────
        for ini_key, attr in [
            ("PerLevelStatsMultiplier_DinoTamed",          "per_level_stats_mult_dino_tamed"),
            ("PerLevelStatsMultiplier_DinoTamed_Add",      "per_level_stats_mult_dino_tamed_add"),
            ("PerLevelStatsMultiplier_DinoTamed_Affinity", "per_level_stats_mult_dino_tamed_affinity"),
            ("PerLevelStatsMultiplier_DinoWild",           "per_level_stats_mult_dino_wild"),
            ("PerLevelStatsMultiplier_Player",             "per_level_stats_mult_player"),
        ]:
            vals = getattr(gs, attr)
            for i, v in enumerate(vals):
                ini_k = f"{ini_key}[{i}]"
                if v != 1.0:
                    parser.set(section, ini_k, f"{v:.6g}")
                else:
                    try:
                        parser.remove_option(section, ini_k)
                    except Exception:
                        pass

        # ── Escrita inicial via configparser ──────────────────────────────
        import io
        buf = io.StringIO()
        parser.write(buf)
        ini_text = buf.getvalue()

        # ── Remove linhas de spawn anteriores (configparser perde duplicatas) ──
        _SPAWN_RE = _re.compile(
            r'^(?:config(?:add|override)npcspawnentriescontainer'
            r'|dinoclassresistancemultipliers'
            r'|dinoclassdamagemultipliers'
            r'|tameddinoclassresistancemultipliers'
            r'|tameddinoclassdamagemultipliers'
            r'|configoverridesupplycrateitems)\s*=.*$',
            _re.IGNORECASE | _re.MULTILINE,
        )
        ini_text = _SPAWN_RE.sub("", ini_text)

        # ── Gera novas linhas de spawn e injeta antes da próxima seção ───────
        spawn_lines: list[str] = []
        for container in adv.npc_spawn_entries_add:
            val = _serialize_npc_spawn_container(container, is_override=False)
            spawn_lines.append(f"ConfigAddNPCSpawnEntriesContainer={val}")
        for container in adv.npc_spawn_entries_override:
            val = _serialize_npc_spawn_container(container, is_override=True)
            spawn_lines.append(f"ConfigOverrideNPCSpawnEntriesContainer={val}")
        for entry in adv.dino_class_resistance_multipliers:
            spawn_lines.append(f"DinoClassResistanceMultipliers={_serialize_dino_class_multiplier(entry)}")
        for entry in adv.dino_class_damage_multipliers:
            spawn_lines.append(f"DinoClassDamageMultipliers={_serialize_dino_class_multiplier(entry)}")
        for entry in adv.tamed_dino_class_resistance_multipliers:
            spawn_lines.append(f"TamedDinoClassResistanceMultipliers={_serialize_dino_class_multiplier(entry)}")
        for entry in adv.tamed_dino_class_damage_multipliers:
            spawn_lines.append(f"TamedDinoClassDamageMultipliers={_serialize_dino_class_multiplier(entry)}")
        for crate in adv.supply_crate_overrides:
            spawn_lines.append(f"ConfigOverrideSupplyCrateItems={_serialize_supply_crate_override(crate)}")

        if spawn_lines:
            section_header = f"[{section}]".lower()
            lines = ini_text.splitlines(keepends=True)
            insert_pos = None
            in_target = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.lower() == section_header:
                    in_target = True
                    continue
                if in_target and stripped.startswith("[") and stripped.endswith("]"):
                    insert_pos = i
                    break
            if insert_pos is None and in_target:
                insert_pos = len(lines)
            if insert_pos is not None:
                spawn_block = [s + "\n" for s in spawn_lines]
                lines[insert_pos:insert_pos] = spawn_block
            ini_text = "".join(lines)

        # ── Remove linhas em branco extras deixadas pela substituição ────────
        ini_text = _re.sub(r'\n{3,}', '\n\n', ini_text)

        with open(str(path), "w", encoding=_write_encoding(path)) as fh:
            fh.write(ini_text)

    def save_all(self, config: ServerConfig) -> None:
        """Salva GameUserSettings.ini e Game.ini de uma vez."""
        self.save_game_user_settings(config)
        self.save_game_ini(config)

    # ── Configurações INI de mods ─────────────────────────────────────────────

    def apply_mod_ini_configs(self, mod_ini_configs: dict) -> None:
        """Aplica/atualiza blocos de configuração de mods em Game.ini e GameUserSettings.ini.

        Cada entrada em mod_ini_configs deve ter o formato:
            {"mod_id": {"game_ini": "...", "gus_ini": "..."}}

        Os blocos anteriores de mods são removidos antes de aplicar os novos,
        evitando duplicatas. Mods sem conteúdo não geram blocos.
        """
        import re

        _BLOCK_RE = re.compile(
            r"; =+ BEGIN MOD CONFIGS =+\n.*?; =+ END MOD CONFIGS =+\n?",
            re.DOTALL,
        )

        for file_key, filename in (("game_ini", "Game.ini"), ("gus_ini", "GameUserSettings.ini")):
            path = get_ini_path(self._install_dir, filename)
            path.parent.mkdir(parents=True, exist_ok=True)

            if path.exists():
                # Permite editar INIs existentes mesmo que tenham sido salvos em UTF-16/ANSI.
                content = _read_text_with_fallback(path)
            else:
                content = ""
            # Remove bloco antigo
            content = _BLOCK_RE.sub("", content).rstrip("\n")

            snippets = []
            for mod_id, cfg in mod_ini_configs.items():
                snippet = cfg.get(file_key, "").strip()
                if snippet:
                    snippets.append(f"; --- Mod {mod_id} ---\n{snippet}")

            if snippets:
                block = (
                    "\n\n; ========== BEGIN MOD CONFIGS ==========\n"
                    + "\n".join(snippets)
                    + "\n; ========== END MOD CONFIGS ==========\n"
                )
                content += block

            path.write_text(content, encoding=_write_encoding(path))
