"""
INI_MAP — mapeamento declarativo entre AsmServerConfig e os arquivos .ini do ARK.
Fiel ao sistema IniFileEntry do ARK Server Manager (ASM) em C#.

Formato de cada entrada:
    campo_python: (arquivo, seção, chave_ini, opções)

Arquivos:
    "GUS"  → GameUserSettings.ini
    "Game" → Game.ini

Opções disponíveis no dict:
    "inverted"        : bool  — escreve (not valor) no INI
    "conditional_on"  : str   — só escreve se o campo indicado for truthy
    "omit_if_default" : bool  — omite a linha se o valor == padrão (default True)
    "always_write"    : bool  — escreve mesmo se == padrão
    "list_sep"        : str   — separador para campos List[str] (default ",")
    "cli_only"        : bool  — não vai ao INI; vai apenas na linha de comando
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Any

from .asm_server_config import AsmServerConfig


# ── Mapeamento declarativo ────────────────────────────────────────────────────
# (campo_python): (arquivo, seção, chave_ini, opções)
INI_MAP: dict[str, tuple] = {
    # Administration
    "session_name":             ("GUS", "SessionSettings",  "SessionName",                {}),
    "server_password":          ("GUS", "ServerSettings",   "ServerPassword",              {}),
    "admin_password":           ("GUS", "ServerSettings",   "ServerAdminPassword",         {}),
    "spectator_password":       ("GUS", "ServerSettings",   "SpectatorPassword",           {}),
    "server_port":              ("GUS", "SessionSettings",  "Port",                        {"always_write": True}),
    "query_port":               ("GUS", "SessionSettings",  "QueryPort",                   {"always_write": True}),
    "server_ip":                ("GUS", "SessionSettings",  "MultiHome",                   {"conditional_on": "server_ip"}),
    "max_players":              ("GUS", "GameSession",      "MaxPlayers",                  {"always_write": True}),
    "rcon_enabled":             ("GUS", "ServerSettings",   "RCONEnabled",                 {"always_write": True}),
    "rcon_port":                ("GUS", "ServerSettings",   "RCONPort",                    {"always_write": True}),
    "rcon_log_buffer":          ("GUS", "ServerSettings",   "RCONServerGameLogBuffer",     {}),
    "admin_logging":            ("GUS", "ServerSettings",   "AdminLogging",                {}),
    "active_mods":              ("GUS", "ServerSettings",   "ActiveMods",                  {"list_sep": ","}),
    "auto_save_period":         ("GUS", "ServerSettings",   "AutoSavePeriodMinutes",       {}),
    "kick_idle_players":        ("GUS", "ServerSettings",   "KickIdlePlayersPeriod",       {}),
    "enable_ban_list_url":      ("GUS", "ServerSettings",   "BanListURL",                  {"conditional_on": "enable_ban_list_url", "use_field": "ban_list_url"}),
    "motd":                     ("GUS", "MessageOfTheDay",  "Message",                     {"conditional_on": "motd"}),
    "motd_duration":            ("GUS", "MessageOfTheDay",  "Duration",                    {"conditional_on": "motd"}),

    # Rules
    "enable_hardcore":              ("GUS", "ServerSettings", "ServerHardcore",               {}),
    "enable_pvp":                   ("GUS", "ServerSettings", "ServerPVE",                    {"inverted": True}),
    "allow_cave_building_pve":      ("GUS", "ServerSettings", "AllowCaveBuildingPvE",         {}),
    "disable_friendly_fire_pvp":    ("Game","GameMode",       "bDisableFriendlyFire",          {}),
    "disable_friendly_fire_pve":    ("Game","GameMode",       "bPvEDisableFriendlyFire",       {}),
    "disable_loot_crates":          ("Game","GameMode",       "bDisableLootCrates",            {}),
    "override_official_difficulty": ("GUS", "ServerSettings", "OverrideOfficialDifficulty",   {"conditional_on": "enable_difficulty_override"}),
    "difficulty_offset":            ("GUS", "ServerSettings", "DifficultyOffset",             {}),
    "max_tribe_size":               ("GUS", "ServerSettings", "MaxNumberOfPlayersInTribe",    {"conditional_on": "max_tribe_size"}),
    "enable_tribute_downloads":     ("GUS", "ServerSettings", "NoTributeDownloads",           {"inverted": True}),
    "prevent_download_survivors":   ("GUS", "ServerSettings", "PreventDownloadSurvivors",     {}),
    "prevent_download_items":       ("GUS", "ServerSettings", "PreventDownloadItems",         {}),
    "prevent_download_dinos":       ("GUS", "ServerSettings", "PreventDownloadDinos",         {}),
    "prevent_upload_survivors":     ("GUS", "ServerSettings", "PreventUploadSurvivors",       {}),
    "prevent_upload_items":         ("GUS", "ServerSettings", "PreventUploadItems",           {}),
    "prevent_upload_dinos":         ("GUS", "ServerSettings", "PreventUploadDinos",           {}),
    "allow_pvp_gamma":              ("GUS", "ServerSettings", "EnablePVPGamma",               {}),
    "allow_tribe_alliances":        ("GUS", "ServerSettings", "PreventTribeAlliances",        {"inverted": True}),
    "allow_custom_recipes":         ("Game","GameMode",       "bAllowCustomRecipes",           {}),
    "enable_diseases":              ("GUS", "ServerSettings", "PreventDiseases",              {"inverted": True}),
    "prevent_pvp_offline":          ("GUS", "ServerSettings", "PreventOfflinePvP",            {}),
    "auto_pve_timer":               ("Game","GameMode",       "bAutoPvETimer",                {}),

    # ChatAndNotifications
    "global_voice_chat":            ("GUS", "ServerSettings", "globalVoiceChat",              {}),
    "proximity_chat":               ("GUS", "ServerSettings", "proximityChat",                {}),
    "player_leave_notifications":   ("GUS", "ServerSettings", "alwaysNotifyPlayerLeft",       {}),
    "player_joined_notifications":  ("GUS", "ServerSettings", "alwaysNotifyPlayerJoined",     {}),

    # HudAndVisuals
    "allow_crosshair":              ("GUS", "ServerSettings", "ServerCrosshair",              {}),
    "allow_hud":                    ("GUS", "ServerSettings", "ServerForceNoHud",             {"inverted": True}),
    "allow_third_person_view":      ("GUS", "ServerSettings", "AllowThirdPersonPlayer",       {}),
    "show_map_player_location":     ("GUS", "ServerSettings", "ShowMapPlayerLocation",        {}),
    "show_floating_damage_text":    ("GUS", "ServerSettings", "ShowFloatingDamageText",       {}),
    "allow_hit_markers":            ("GUS", "ServerSettings", "AllowHitMarkers",              {}),

    # Players
    "xp_multiplier":                        ("GUS","ServerSettings","XPMultiplier",                           {}),
    "player_damage_multiplier":             ("GUS","ServerSettings","PlayerDamageMultiplier",                  {}),
    "player_resistance_multiplier":         ("GUS","ServerSettings","PlayerResistanceMultiplier",              {}),
    "player_water_drain_multiplier":        ("GUS","ServerSettings","PlayerCharacterWaterDrainMultiplier",     {}),
    "player_food_drain_multiplier":         ("GUS","ServerSettings","PlayerCharacterFoodDrainMultiplier",      {}),
    "player_stamina_drain_multiplier":      ("GUS","ServerSettings","PlayerCharacterStaminaDrainMultiplier",   {}),
    "player_health_recovery_multiplier":    ("GUS","ServerSettings","PlayerCharacterHealthRecoveryMultiplier", {}),
    "player_harvesting_damage_multiplier":  ("GUS","ServerSettings","PlayerHarvestingDamageMultiplier",        {}),
    "crafting_skill_bonus_multiplier":      ("GUS","ServerSettings","CraftingSkillBonusMultiplier",            {}),
    "enable_flyer_carry":                   ("GUS","ServerSettings","AllowFlyerCarryPVE",                      {}),
    "override_max_xp_player":              ("GUS","ServerSettings","OverrideMaxExperiencePointsPlayer",       {"conditional_on": "override_max_xp_player"}),

    # Dinos
    "dino_damage_multiplier":               ("GUS","ServerSettings","DinoDamageMultiplier",                   {}),
    "tamed_dino_damage_multiplier":         ("GUS","ServerSettings","TamedDinoDamageMultiplier",              {}),
    "dino_resistance_multiplier":           ("GUS","ServerSettings","DinoResistanceMultiplier",               {}),
    "tamed_dino_resistance_multiplier":     ("GUS","ServerSettings","TamedDinoResistanceMultiplier",          {}),
    "max_tamed_dinos":                      ("GUS","ServerSettings","MaxTamedDinos",                          {}),
    "dino_count_multiplier":                ("GUS","ServerSettings","DinoCountMultiplier",                    {}),
    "taming_speed_multiplier":              ("GUS","ServerSettings","TamingSpeedMultiplier",                  {}),
    "mating_interval_multiplier":           ("Game","GameMode",     "MatingIntervalMultiplier",               {}),
    "egg_hatch_speed_multiplier":           ("Game","GameMode",     "EggHatchSpeedMultiplier",                {}),
    "baby_mature_speed_multiplier":         ("Game","GameMode",     "BabyMatureSpeedMultiplier",              {}),
    "baby_food_consumption_multiplier":     ("Game","GameMode",     "BabyFoodConsumptionSpeedMultiplier",     {}),
    "baby_cuddle_interval_multiplier":      ("Game","GameMode",     "BabyCuddleIntervalMultiplier",           {}),
    "baby_imprinting_stat_scale":           ("Game","GameMode",     "BabyImprintingStatScaleMultiplier",      {}),
    "disable_imprint_buff":                 ("GUS","ServerSettings","DisableImprintDinoBuff",                 {}),
    "allow_anyone_baby_imprint":            ("GUS","ServerSettings","AllowAnyoneBabyImprintCuddle",           {}),
    "disable_dino_riding":                  ("Game","GameMode",     "bDisableDinoRiding",                     {}),
    "disable_dino_taming":                  ("Game","GameMode",     "bDisableDinoTaming",                     {}),
    "passive_tame_interval_multiplier":     ("Game","GameMode",     "PassiveTameIntervalMultiplier",          {}),
    "dino_harvesting_damage_multiplier":    ("GUS","ServerSettings","DinoHarvestingDamageMultiplier",         {}),
    "disable_dino_decay_pve":               ("GUS","ServerSettings","DisableDinoDecayPvE",                   {}),
    "pvp_dino_decay":                       ("GUS","ServerSettings","PvPDinoDecay",                          {"inverted": True}),

    # Environment
    "harvest_amount_multiplier":                ("GUS","ServerSettings","HarvestAmountMultiplier",                     {}),
    "harvest_health_multiplier":                ("GUS","ServerSettings","HarvestHealthMultiplier",                     {}),
    "resources_respawn_multiplier":             ("GUS","ServerSettings","ResourcesRespawnPeriodMultiplier",            {}),
    "day_cycle_speed_scale":                    ("GUS","ServerSettings","DayCycleSpeedScale",                          {}),
    "day_time_speed_scale":                     ("GUS","ServerSettings","DayTimeSpeedScale",                           {}),
    "night_time_speed_scale":                   ("GUS","ServerSettings","NightTimeSpeedScale",                         {}),
    "global_spoiling_time_multiplier":          ("GUS","ServerSettings","GlobalSpoilingTimeMultiplier",                {}),
    "global_item_decomposition_multiplier":     ("GUS","ServerSettings","GlobalItemDecompositionTimeMultiplier",       {}),
    "global_corpse_decomposition_multiplier":   ("GUS","ServerSettings","GlobalCorpseDecompositionTimeMultiplier",     {}),
    "crop_decay_speed_multiplier":              ("Game","GameMode",     "CropDecaySpeedMultiplier",                    {}),
    "crop_growth_speed_multiplier":             ("Game","GameMode",     "CropGrowthSpeedMultiplier",                   {}),
    "hair_growth_speed_multiplier":             ("Game","GameMode",     "HairGrowthSpeedMultiplier",                   {}),
    "base_temperature_multiplier":              ("GUS","ServerSettings","BaseTemperatureMultiplier",                   {}),
    "disable_weather_fog":                      ("GUS","ServerSettings","DisableWeatherFog",                           {}),

    # Structures
    "structure_resistance_multiplier":           ("GUS","ServerSettings","StructureResistanceMultiplier",              {}),
    "structure_damage_multiplier":               ("GUS","ServerSettings","StructureDamageMultiplier",                  {}),
    "max_structures_in_range":                   ("GUS","ServerSettings","TheMaxStructuresInRange",                    {}),
    "per_platform_max_structures_multiplier":    ("GUS","ServerSettings","PerPlatformMaxStructuresMultiplier",         {}),
    "max_platform_saddle_structures":            ("GUS","ServerSettings","MaxPlatformSaddleStructureLimit",            {}),
    "enable_structure_decay_pve":                ("GUS","ServerSettings","DisableStructureDecayPVE",                   {"inverted": True}),
    "pve_structure_decay_period_multiplier":     ("GUS","ServerSettings","PvEStructureDecayPeriodMultiplier",          {}),
    "pve_structure_decay_destruction_period":    ("GUS","ServerSettings","PvEStructureDecayDestructionPeriod",         {}),
    "auto_destroy_old_structures_multiplier":    ("GUS","ServerSettings","AutoDestroyOldStructuresMultiplier",         {"conditional_on": "auto_destroy_old_structures_multiplier"}),
    "force_all_structure_locking":               ("GUS","ServerSettings","ForceAllStructureLocking",                   {}),
    "disable_structure_placement_collision":     ("Game","GameMode",     "bDisableStructurePlacementCollision",         {}),
    "limit_turrets_in_range":                    ("GUS","ServerSettings","LimitTurretsInRange",                        {}),
    "limit_turrets_range":                       ("GUS","ServerSettings","LimitTurretsRange",                          {"conditional_on": "limit_turrets_in_range"}),
    "limit_turrets_num":                         ("GUS","ServerSettings","LimitTurretsNum",                            {"conditional_on": "limit_turrets_in_range"}),
}

# Mapeamento de arquivo → nome real do arquivo INI
_FILE_NAMES = {
    "GUS":  "GameUserSettings.ini",
    "Game": "Game.ini",
}

# Seção do Game.ini — depende do modo de jogo
_GAME_MODE_SECTION = "/Script/ShooterGame.ShooterGameMode"


def _ini_path(install_dir: str, file_key: str) -> Path:
    name = _FILE_NAMES[file_key]
    return Path(install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / name


def _bool_str(val: bool) -> str:
    return "True" if val else "False"


def _format_value(val: Any) -> str:
    if isinstance(val, bool):
        return _bool_str(val)
    if isinstance(val, float):
        # ARK usa até 6 casas; remove zeros desnecessários
        s = f"{val:.6f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(val)


def write_ini(cfg: AsmServerConfig) -> None:
    """Escreve GameUserSettings.ini e Game.ini a partir de AsmServerConfig.

    ⚠️  T13 PENDENTE — confirmar se a escrita causa crash do ArkShopUI antes
        de usar em produção. Ver PENDING_ISSUES.md T13.
    """
    if not cfg.install_dir:
        raise ValueError("install_dir não configurado")

    # Agrupa valores por (arquivo, seção)
    gus: dict[str, dict[str, str]] = {}   # {secao: {chave: valor}}
    game: dict[str, dict[str, str]] = {}

    for field_name, (file_key, section, ini_key, opts) in INI_MAP.items():
        # Verificar conditional_on
        cond = opts.get("conditional_on")
        if cond:
            cond_val = getattr(cfg, cond, None)
            if not cond_val:
                continue

        raw = getattr(cfg, field_name, None)
        if raw is None:
            continue

        # Campo que usa outro field para o valor (ex: enable_ban_list_url → ban_list_url)
        use_field = opts.get("use_field")
        if use_field:
            raw = getattr(cfg, use_field, raw)

        # Inversão booleana
        if opts.get("inverted") and isinstance(raw, bool):
            raw = not raw

        # Listas (mods, engrams, etc.)
        if isinstance(raw, list):
            sep = opts.get("list_sep", ",")
            value = sep.join(str(x) for x in raw)
        else:
            value = _format_value(raw)

        # Omitir se valor padrão (a menos que always_write)
        # (por ora omite apenas strings/bools vazios/False sem always_write)
        if not opts.get("always_write") and value in ("", "False", "0", "0.0", "1.0", "1"):
            # Heurística simples: multipliers=1.0 e booleans=False são padrão
            # Para campos críticos (porta, etc.) usamos always_write
            pass  # não pula — deixa escrever para garantir consistência

        target = gus if file_key == "GUS" else game
        section_key = _GAME_MODE_SECTION if (file_key == "Game" and section == "GameMode") else section
        target.setdefault(section_key, {})[ini_key] = value

    # Seções customizadas livres
    for custom in cfg.custom_ini_sections:
        f = custom.get("file", "GUS").upper()
        sec = custom.get("section", "")
        target = gus if f in ("GUS", "GAMEUSERSETTINGS.INI") else game
        for entry in custom.get("entries", []):
            target.setdefault(sec, {})[entry["key"]] = entry["value"]

    _write_ini_file(_ini_path(cfg.install_dir, "GUS"),  gus)
    _write_ini_file(_ini_path(cfg.install_dir, "Game"), game)


def _write_ini_file(path: Path, sections: dict[str, dict[str, str]]) -> None:
    """Escreve um arquivo INI preservando seções existentes não gerenciadas."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Lê o arquivo existente (se houver) para preservar seções não mapeadas
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # preserva case
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                parser.read_file(fh)
        except Exception:
            pass

    # Injeta / substitui as seções gerenciadas
    for section, kvs in sections.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in kvs.items():
            parser.set(section, key, value)

    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        parser.write(fh)
    tmp.replace(path)


def read_ini(cfg: AsmServerConfig) -> None:
    """Lê GameUserSettings.ini e Game.ini e popula cfg in-place."""
    if not cfg.install_dir:
        return

    parsers: dict[str, configparser.RawConfigParser] = {}
    for fk in ("GUS", "Game"):
        p = configparser.RawConfigParser()
        p.optionxform = str
        fp = _ini_path(cfg.install_dir, fk)
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8-sig") as fh:
                    p.read_file(fh)
            except Exception:
                pass
        parsers[fk] = p

    for field_name, (file_key, section, ini_key, opts) in INI_MAP.items():
        p = parsers[file_key]
        sec = _GAME_MODE_SECTION if (file_key == "Game" and section == "GameMode") else section
        if not p.has_option(sec, ini_key):
            continue
        raw = p.get(sec, ini_key)

        # Tipo do campo
        from dataclasses import fields as _fields
        ftype = next((f.type for f in _fields(AsmServerConfig) if f.name == field_name), None)
        try:
            if ftype in ("bool", bool) or str(ftype) == "bool":
                val: Any = raw.lower() in ("true", "1", "yes")
            elif ftype in ("int", int) or str(ftype) == "int":
                val = int(float(raw))
            elif ftype in ("float", float) or str(ftype) == "float":
                val = float(raw)
            elif ftype in ("List[str]",):
                sep = opts.get("list_sep", ",")
                val = [x.strip() for x in raw.split(sep) if x.strip()]
            else:
                val = raw
        except Exception:
            continue

        # Desfaz inversão
        if opts.get("inverted") and isinstance(val, bool):
            val = not val

        setattr(cfg, field_name, val)


def build_launch_args(cfg: AsmServerConfig) -> list[str]:
    """Monta a lista de argumentos de linha de comando fiel ao ASM GetServerArgs()."""
    params = [
        f"{cfg.server_map}",
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
        params.append(f"?ClusterId={cfg.cross_ark_cluster_id}")
        params.append("?PreventDownloadItems=False")

    flags = ["-nosteamclient", "-game", "-server", "-log"]
    if cfg.allow_cave_flyers:
        flags.append("-ForceAllowCaveFlyers")

    if cfg.additional_args.strip():
        import shlex
        try:
            flags += shlex.split(cfg.additional_args)
        except Exception:
            flags.append(cfg.additional_args)

    # O ARK espera: ShooterGameServer.exe MAP?param1?param2 -flag1 -flag2
    combined_map = "".join(params)
    return [combined_map] + flags
