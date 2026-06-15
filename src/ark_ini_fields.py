"""
Constantes de mapeamento e funções de população para leitura de INIs do ARK.
Extraído de ark_ini.py para manter o módulo principal abaixo de 1000 linhas.
"""
from __future__ import annotations

import configparser
import io
import re
from pathlib import Path
from typing import Optional

from .server_config import ServerConfig


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
    # ── Novos campos (ASM parity) ─────────────────────────────────────────────
    # Dino — tamed/wild multipliers separados
    ("tamed_dino_damage_multiplier",          "ServerSettings", "TamedDinoDamageMultiplier",             float),
    ("tamed_dino_resistance_multiplier",      "ServerSettings", "TamedDinoResistanceMultiplier",         float),
    ("dino_character_stamina_drain_multiplier","ServerSettings","DinoCharacterStaminaDrainMultiplier",   float),
    ("dino_turret_damage_multiplier",         "ServerSettings", "TurretDamageMultiplierDino",            float),
    ("max_personal_tamed_dinos",              "ServerSettings", "MaxPersonalTamedDinos",                  float),
    ("personal_tamed_dinos_saddle_structure_cost","ServerSettings","PersonalTamedDinosSaddleStructureCost",int),
    # Dino — imprinting/mateBoost/decay
    ("disable_imprint_dino_buff",             "ServerSettings", "DisableImprintDinoBuff",                bool),
    ("allow_anyone_baby_imprint_cuddle",      "ServerSettings", "AllowAnyoneBabyImprintCuddle",          bool),
    ("allow_flying_stamina_recovery",         "ServerSettings", "AllowFlyingStaminaRecovery",            bool),
    ("prevent_mate_boost",                    "ServerSettings", "PreventMateBoost",                      bool),
    ("allow_multiple_attached_c4",            "ServerSettings", "AllowMultipleAttachedC4",               bool),
    ("auto_destroy_decayed_dinos",            "ServerSettings", "AutoDestroyDecayedDinos",               bool),
    ("pve_dino_decay_period_multiplier",      "ServerSettings", "PvEDinoDecayPeriodMultiplier",          float),
    # Ciclo de dia/noite / temperatura
    ("day_cycle_speed_scale",                 "ServerSettings", "DayCycleSpeedScale",                    float),
    ("day_time_speed_scale",                  "ServerSettings", "DayTimeSpeedScale",                     float),
    ("night_time_speed_scale",                "ServerSettings", "NightTimeSpeedScale",                   float),
    ("disable_weather_fog",                   "ServerSettings", "DisableWeatherFog",                     bool),
    # PvP gamma / Hit Markers
    ("allow_pvp_gamma",                       "ServerSettings", "EnablePVPGamma",                        bool),
    ("allow_hit_markers",                     "ServerSettings", "AllowHitMarkers",                       bool),
    # Estruturas — decay
    ("pvp_structure_decay",                   "ServerSettings", "PvPStructureDecay",                     bool),
    ("max_structures_visible",                "ServerSettings", "TheMaxStructuresInRange",               int),
    ("max_platform_saddle_structure_limit",   "ServerSettings", "MaxPlatformSaddleStructureLimit",       int),
    ("override_structure_platform_prevention","ServerSettings", "OverrideStructurePlatformPrevention",   bool),
    ("auto_destroy_old_structures_multiplier","ServerSettings", "AutoDestroyOldStructuresMultiplier",    float),
    ("only_auto_destroy_core_structures",     "ServerSettings", "OnlyAutoDestroyCoreStructures",         bool),
    ("only_decay_unsnapped_core_structures",  "ServerSettings", "OnlyDecayUnsnappedCoreStructures",      bool),
    ("fast_decay_unsnapped_core_structures",  "ServerSettings", "FastDecayUnsnappedCoreStructures",      bool),
    ("destroy_unconnected_water_pipes",       "ServerSettings", "DestroyUnconnectedWaterPipes",          bool),
    # Estruturas — placement
    ("allow_cave_building_pve",               "ServerSettings", "AllowCaveBuildingPvE",                  bool),
    ("pve_allow_structures_at_supply_drops",  "ServerSettings", "PvEAllowStructuresAtSupplyDrops",       bool),
    ("enable_extra_structure_prevention_volumes","ServerSettings","EnableExtraStructurePreventionVolumes",bool),
    # Recursos
    ("clamp_resource_harvest_damage",         "ServerSettings", "ClampResourceHarvestDamage",            bool),
    # Doenças — NonPermanentDiseases (EnableDiseases gravado com lógica invertida separada)
    ("non_permanent_diseases",                "ServerSettings", "NonPermanentDiseases",                  bool),
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


def _normalize_section_case(parser: configparser.RawConfigParser, canonical: str) -> None:
    """Garante que a seção exista com o nome canônico (preservando maiúsculas/minúsculas).

    Se o parser contiver uma seção com nome diferente apenas no case
    (ex: '/script/shootergame.shootergamemode' vs '/Script/ShooterGame.ShooterGameMode'),
    renomeia-a para o nome canônico movendo todas as chaves.
    Isso evita que o app crie seções duplicadas ao salvar.

    Regras de merge quando AMBAS as seções existem:
    - A seção canônica (escrita pelo app) mantém seus valores;
    - A seção com case errado apenas preenche chaves ausentes.
    """
    canonical_lower = canonical.lower()
    for existing in list(parser.sections()):
        if existing.lower() == canonical_lower and existing != canonical:
            if not parser.has_section(canonical):
                # Só a versão com case errado existe → renomeia para canônico
                parser.add_section(canonical)
                for key, value in parser.items(existing):
                    parser.set(canonical, key, value)
            else:
                # Ambas existem → a seção com case errado é a original (pré-existente);
                # a canônica foi criada acidentalmente pelo app com valores possivelmente errados.
                # A seção original sobrescreve conflitos; a canônica mantém chaves únicas suas.
                for key, value in parser.items(existing):
                    parser.set(canonical, key, value)
            parser.remove_section(existing)
            break


_GUS_SHOOTER_USER_SETTINGS_SECTION = "/Script/ShooterGame.ShooterGameUserSettings"
_GUS_ENGINE_GAME_SESSION_SECTION = "/Script/Engine.GameSession"

# Ordem canônica de escrita (templates Shockbyte/PingPerfect / ASM legado).
GUS_SECTION_ORDER: tuple[str, ...] = (
    _GUS_SHOOTER_USER_SETTINGS_SECTION,
    "ScalabilityGroups",
    "SessionSettings",
    "ServerSettings",
    _GUS_ENGINE_GAME_SESSION_SECTION,
    "GameSession",
    "MessageOfTheDay",
)

_GUS_CANONICAL_SECTIONS = GUS_SECTION_ORDER

_GUS_REQUIRED_MIN_KEYS: dict[str, dict[str, str]] = {
    _GUS_SHOOTER_USER_SETTINGS_SECTION: {"Version": "5"},
}


def ensure_gus_ark_sections(parser: configparser.RawConfigParser) -> None:
    """Garante todas as seções canônicas do GameUserSettings.ini do ARK ASE.

    Seções podem ficar vazias (apenas cabeçalho [Seção]) — exceto
    [/Script/ShooterGame.ShooterGameUserSettings], que exige Version=5.
    Sem isso o servidor considera o arquivo inválido e o regrava inteiro
    com valores padrão no boot (arkmanager/ark-server-tools#722).
    """
    for sec in _GUS_CANONICAL_SECTIONS:
        _normalize_section_case(parser, sec)

    for sec in _GUS_CANONICAL_SECTIONS:
        if not parser.has_section(sec):
            parser.add_section(sec)

    for sec, keys in _GUS_REQUIRED_MIN_KEYS.items():
        for key, value in keys.items():
            if not parser.has_option(sec, key):
                parser.set(sec, key, value)


def ensure_gus_ark_skeleton(parser: configparser.RawConfigParser) -> None:
    """Alias de ensure_gus_ark_sections — mantido para imports existentes."""
    ensure_gus_ark_sections(parser)


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


def _read_gus_rcon_motd_mods(parser: configparser.RawConfigParser, config: "ServerConfig") -> None:
    """Lê RCON, MOTD, mods, AutoSavePeriod e ActiveEvent do parser GUS."""
    ss = "ServerSettings"
    try:
        if parser.has_option(ss, "RCONEnabled"):
            config.rcon_enabled = _str_to_bool(parser.get(ss, "RCONEnabled"))
    except Exception: pass
    try:
        if parser.has_option(ss, "RCONPort"):
            config.rcon_port = int(float(parser.get(ss, "RCONPort")))
    except Exception: pass
    try:
        if parser.has_option("MessageOfTheDay", "Message"):
            config.motd = parser.get("MessageOfTheDay", "Message")
    except Exception: pass
    try:
        if parser.has_option("MessageOfTheDay", "Duration"):
            config.motd_duration = int(float(parser.get("MessageOfTheDay", "Duration")))
    except Exception: pass
    if parser.has_option(ss, "ActiveMods"):
        raw = parser.get(ss, "ActiveMods").strip()
        config.mods = [m.strip() for m in raw.split(",") if m.strip()]
    try:
        if parser.has_option(ss, "AutoSavePeriodMinutes"):
            config.auto_save_period = float(parser.get(ss, "AutoSavePeriodMinutes"))
    except Exception: pass
    try:
        if parser.has_option(ss, "ActiveEvent"):
            config.active_event = parser.get(ss, "ActiveEvent").strip()
    except Exception: pass


def _read_gus_inverted_bools(parser: configparser.RawConfigParser, gs, ss: str) -> None:
    """Lê booleanos invertidos e NPC stasis range scale de [ServerSettings]."""
    _safe = [
        ("DisablePvEGamma",       lambda v: setattr(gs, "allow_pve_gamma",   not _str_to_bool(v))),
        ("PreventDiseases",       lambda v: setattr(gs, "enable_diseases",    not _str_to_bool(v))),
        ("PreventTribeAlliances", lambda v: setattr(gs, "allow_tribe_alliances", not _str_to_bool(v))),
        ("PvPDinoDecay",          lambda v: setattr(gs, "disable_dino_decay_pvp", not _str_to_bool(v))),
        ("TheMaxStructuresInRange", lambda v: setattr(gs, "max_structures_visible", int(float(v)))),
    ]
    for key, fn in _safe:
        try:
            if parser.has_option(ss, key):
                fn(parser.get(ss, key))
        except Exception: pass
    try:
        if parser.has_option(ss, "NPCNetworkStasisRangeScalePlayerCountStart"):
            gs.override_npc_network_stasis_range_scale = True
            gs.npc_network_stasis_range_scale_player_count_start = int(float(
                parser.get(ss, "NPCNetworkStasisRangeScalePlayerCountStart")))
    except Exception: pass
    try:
        if parser.has_option(ss, "NPCNetworkStasisRangeScalePlayerCountEnd"):
            gs.npc_network_stasis_range_scale_player_count_end = int(float(
                parser.get(ss, "NPCNetworkStasisRangeScalePlayerCountEnd")))
    except Exception: pass
    try:
        if parser.has_option(ss, "NPCNetworkStasisRangeScalePercentEnd"):
            gs.npc_network_stasis_range_scale_percent_end = float(
                parser.get(ss, "NPCNetworkStasisRangeScalePercentEnd"))
    except Exception: pass


def _read_gus_server_config_fields(
    parser: configparser.RawConfigParser, config: "ServerConfig", ss: str
) -> None:
    """Lê SpectatorPassword, BanListURL, log flags e ExtinctionEvent de GUS."""
    try:
        if parser.has_option(ss, "SpectatorPassword"):
            config.spectator_password = parser.get(ss, "SpectatorPassword")
    except Exception: pass
    try:
        if parser.has_option(ss, "BanListURL"):
            config.enable_ban_list_url = True
            config.ban_list_url = parser.get(ss, "BanListURL").strip('"')
    except Exception: pass
    for attr, key in [
        ("rcon_server_game_log_buffer",         "RCONServerGameLogBuffer"),
    ]:
        try:
            if parser.has_option(ss, key):
                setattr(config, attr, int(float(parser.get(ss, key))))
        except Exception: pass
    for attr, key in [
        ("admin_logging",                       "AdminLogging"),
        ("allow_hide_damage_source_from_logs",  "AllowHideDamageSourceFromLogs"),
        ("tribe_log_destroyed_enemy_structures","TribeLogDestroyedEnemyStructures"),
    ]:
        try:
            if parser.has_option(ss, key):
                setattr(config, attr, _str_to_bool(parser.get(ss, key)))
        except Exception: pass
    try:
        if parser.has_option(ss, "ExtinctionEventTimeInterval"):
            config.enable_extinction_event = True
            config.extinction_event_time_interval = int(float(
                parser.get(ss, "ExtinctionEventTimeInterval")))
    except Exception: pass


def _read_gus_tribute_crossark(
    parser: configparser.RawConfigParser, config: "ServerConfig", ss: str
) -> None:
    """Lê campos de tribute, CrossARK e auto-respawn de GUS."""
    for attr, key in [
        ("tribute_character_expiration_seconds", "TributeCharacterExpirationSeconds"),
        ("tribute_item_expiration_seconds",       "TributeItemExpirationSeconds"),
        ("tribute_dino_expiration_seconds",       "TributeDinoExpirationSeconds"),
        ("minimum_dino_reupload_interval",        "MinimumDinoReuploadInterval"),
    ]:
        try:
            if parser.has_option(ss, key):
                setattr(config, attr, int(float(parser.get(ss, key))))
        except Exception: pass
    try:
        if parser.has_option(ss, "CrossARKAllowForeignDinoDownloads"):
            config.cross_ark_allow_foreign_dino_downloads = _str_to_bool(
                parser.get(ss, "CrossARKAllowForeignDinoDownloads"))
    except Exception: pass
    try:
        if parser.has_option(ss, "ServerAutoForceRespawnWildDinosInterval"):
            config.enable_auto_force_respawn_wild_dinos_interval = True
            config.server_auto_force_respawn_wild_dinos_interval = int(float(
                parser.get(ss, "ServerAutoForceRespawnWildDinosInterval")))
    except Exception: pass


def populate_config_from_gus(
    parser: configparser.RawConfigParser, config: ServerConfig
) -> None:
    """Popula ServerConfig a partir de um parser GameUserSettings.ini já carregado."""
    _normalize_section_case(parser, "ServerSettings")
    _normalize_section_case(parser, "SessionSettings")
    _normalize_section_case(parser, "MessageOfTheDay")
    gs = config.game_settings
    for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
        try:
            if parser.has_option(section, key):
                setattr(gs, field_name, _coerce(parser.get(section, key), typ))
        except Exception: pass
    for field_name, section, key, typ in _GUS_SESSION_SETTINGS:
        try:
            if parser.has_option(section, key):
                setattr(config, field_name, _coerce(parser.get(section, key), typ))
        except Exception: pass
    _read_gus_rcon_motd_mods(parser, config)
    ss = "ServerSettings"
    _read_gus_inverted_bools(parser, gs, ss)
    _read_gus_server_config_fields(parser, config, ss)
    _read_gus_tribute_crossark(parser, config, ss)


_GAME_INI_ADV_BOOL_FIELDS: list = [
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
    ("use_tame_limit_for_structures_only",       "bUseTameLimitForStructuresOnly"),
    ("disable_dino_riding",                      "bDisableDinoRiding"),
    ("disable_dino_taming",                      "bDisableDinoTaming"),
    ("disable_friendly_fire_pvp",                "bDisableFriendlyFire"),
    ("disable_friendly_fire_pve",                "bPvEDisableFriendlyFire"),
    ("disable_loot_crates",                      "bDisableLootCrates"),
    ("increase_pvp_respawn_interval",            "bIncreasePvPRespawnInterval"),
    ("allow_tribe_war_pve",                      "bPvEAllowTribeWar"),
    ("allow_tribe_war_cancel_pve",               "bPvEAllowTribeWarCancel"),
    ("allow_custom_recipes",                     "bAllowCustomRecipes"),
    ("use_corpse_locator",                       "bUseCorpseLocator"),
    ("allow_unlimited_respecs",                  "bAllowUnlimitedRespecs"),
    ("allow_platform_saddle_multi_floors",       "bAllowPlatformSaddleMultiFloors"),
    ("random_supply_crate_points",               "bRandomSupplyCratePoints"),
    ("disable_structure_placement_collision",    "bDisableStructurePlacementCollision"),
    ("flyer_platform_allow_unaligned_dino_basing","bFlyerPlatformAllowUnalignedDinoBasing"),
    ("enable_fast_decay_interval",               "EnableFastDecayInterval"),
    ("limit_turrets_in_range",                   "bLimitTurretsInRange"),
    ("hard_limit_turrets_in_range",              "bHardLimitTurretsInRange"),
]

_GAME_INI_ADV_FLOAT_FIELDS: list = [
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
    ("passive_tame_interval_multiplier",         "PassiveTameIntervalMultiplier"),
    ("wild_dino_character_food_drain_multiplier","WildDinoCharacterFoodDrainMultiplier"),
    ("tamed_dino_character_food_drain_multiplier","TamedDinoCharacterFoodDrainMultiplier"),
    ("wild_dino_torpor_drain_multiplier",        "WildDinoTorporDrainMultiplier"),
    ("tamed_dino_torpor_drain_multiplier",       "TamedDinoTorporDrainMultiplier"),
    ("baby_cuddle_lose_imprint_quality_speed_multiplier","BabyCuddleLoseImprintQualitySpeedMultiplier"),
    ("base_temperature_multiplier",              "BaseTemperatureMultiplier"),
    ("prevent_offline_pvp_connection_invincible_interval","PreventOfflinePvPConnectionInvincibleInterval"),
    ("supply_crate_loot_quality_multiplier",     "SupplyCrateLootQualityMultiplier"),
    ("use_corpse_life_span_multiplier",          "UseCorpseLifeSpanMultiplier"),
    ("global_powered_battery_durability_decrease_per_second","GlobalPoweredBatteryDurabilityDecreasePerSecond"),
    ("global_corpse_decomposition_time_multiplier","GlobalCorpseDecompositionTimeMultiplier"),
    ("poop_interval_multiplier",                 "PoopIntervalMultiplier"),
    ("hair_growth_speed_multiplier",             "HairGrowthSpeedMultiplier"),
    ("resource_no_replenish_radius_players",     "ResourceNoReplenishRadiusPlayers"),
    ("resource_no_replenish_radius_structures",  "ResourceNoReplenishRadiusStructures"),
    ("crafting_skill_bonus_multiplier",          "CraftingSkillBonusMultiplier"),
    ("pvp_zone_structure_damage_multiplier",     "PvPZoneStructureDamageMultiplier"),
    ("fast_decay_interval",                      "FastDecayInterval"),
    ("limit_turrets_range",                      "LimitTurretsRange"),
    ("increase_pvp_respawn_interval_multiplier", "IncreasePvPRespawnIntervalMultiplier"),
]

_GAME_INI_ADV_INT_FIELDS: list = [
    ("max_alliances_per_tribe",                  "MaxAlliancesPerTribe"),
    ("max_tribes_per_alliance",                  "MaxTribesPerAlliance"),
    ("increase_pvp_respawn_interval_check_period","IncreasePvPRespawnIntervalCheckPeriod"),
    ("increase_pvp_respawn_interval_base_amount","IncreasePvPRespawnIntervalBaseAmount"),
    ("limit_turrets_num",                        "LimitTurretsNum"),
]

_GAME_INI_PER_LEVEL_STATS: list = [
    ("PerLevelStatsMultiplier_DinoTamed",          "per_level_stats_mult_dino_tamed"),
    ("PerLevelStatsMultiplier_DinoTamed_Add",      "per_level_stats_mult_dino_tamed_add"),
    ("PerLevelStatsMultiplier_DinoTamed_Affinity", "per_level_stats_mult_dino_tamed_affinity"),
    ("PerLevelStatsMultiplier_DinoWild",           "per_level_stats_mult_dino_wild"),
    ("PerLevelStatsMultiplier_Player",             "per_level_stats_mult_player"),
]


def _read_per_level_stats(
    parser: configparser.RawConfigParser, gs: object, section: str
) -> None:
    for ini_key, attr in _GAME_INI_PER_LEVEL_STATS:
        vals = list(getattr(gs, attr))
        for i in range(12):
            try:
                if parser.has_option(section, f"{ini_key}[{i}]"):
                    vals[i] = float(parser.get(section, f"{ini_key}[{i}]"))
            except Exception:
                pass
        setattr(gs, attr, vals)


def populate_config_from_game_ini(
    parser: configparser.RawConfigParser, config: ServerConfig
) -> None:
    """Popula ServerConfig.advanced_settings a partir de um parser Game.ini já carregado."""
    adv = config.advanced_settings
    section = "/Script/ShooterGame.ShooterGameMode"
    _normalize_section_case(parser, section)
    for field_name, key in _GAME_INI_ADV_BOOL_FIELDS:
        try:
            if parser.has_option(section, key):
                setattr(adv, field_name, _str_to_bool(parser.get(section, key)))
        except Exception:
            pass
    for field_name, key in _GAME_INI_ADV_FLOAT_FIELDS:
        try:
            if parser.has_option(section, key):
                setattr(adv, field_name, float(parser.get(section, key)))
        except Exception:
            pass
    for field_name, key in _GAME_INI_ADV_INT_FIELDS:
        try:
            if parser.has_option(section, key):
                setattr(adv, field_name, int(float(parser.get(section, key))))
        except Exception:
            pass
    try:
        if parser.has_option(section, "MaxTribeLogs"):
            config.max_tribe_logs = int(float(parser.get(section, "MaxTribeLogs")))
    except Exception:
        pass
    gs = config.game_settings
    for field_name, key, typ in _GAME_INI_GAME_SETTINGS:
        try:
            if parser.has_option(_GAME_INI_SECTION, key):
                setattr(gs, field_name, _coerce(parser.get(_GAME_INI_SECTION, key), typ))
        except Exception:
            pass
    _read_per_level_stats(parser, gs, section)
