"""
Leitura e escrita dos arquivos INI do ARK: Survival Evolved.
Suporta GameUserSettings.ini e Game.ini.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional

from .server_config import ServerConfig, ServerGameSettings, ServerAdvancedSettings


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

# Campos da secao [SessionSettings] / [/Script/Engine.GameSession]
_GUS_SESSION_SETTINGS = [
    ("max_players",       "SessionSettings", "MaxPlayers",           int),
    ("server_name",       "SessionSettings", "SessionName",          str),
    ("server_password",   "SessionSettings", "ServerPassword",       str),
    ("admin_password",    "SessionSettings", "ServerAdminPassword",  str),
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


# ══════════════════════════════════════════════════════════════════════════════
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

        parser = configparser.RawConfigParser(strict=False)
        parser.read(str(path), encoding="utf-8")

        gs = config.game_settings

        for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
            try:
                if parser.has_option(section, key):
                    raw = parser.get(section, key)
                    setattr(gs, field_name, _coerce(raw, typ))
            except Exception:
                pass

        for field_name, section, key, typ in _GUS_SESSION_SETTINGS:
            try:
                if parser.has_option(section, key):
                    raw = parser.get(section, key)
                    setattr(config, field_name, _coerce(raw, typ))
            except Exception:
                pass

        # Mods
        if parser.has_option("ServerSettings", "ActiveMods"):
            raw_mods = parser.get("ServerSettings", "ActiveMods").strip()
            config.mods = [m.strip() for m in raw_mods.split(",") if m.strip()]

    def load_game_ini(self, config: ServerConfig) -> None:
        """Popula ServerConfig.advanced_settings com valores de Game.ini."""
        path = get_ini_path(self._install_dir, "Game.ini")
        if not path.exists():
            return

        parser = configparser.RawConfigParser(strict=False)
        parser.read(str(path), encoding="utf-8")

        adv = config.advanced_settings
        section = "/Script/ShooterGame.ShooterGameMode"

        bool_fields = [
            ("prevent_download_survivors",              "bPreventDownloadSurvivors"),
            ("prevent_download_items",                  "bPreventDownloadItems"),
            ("prevent_download_dinos",                  "bPreventDownloadDinos"),
            ("prevent_upload_survivors",                "bPreventUploadSurvivors"),
            ("prevent_upload_items",                    "bPreventUploadItems"),
            ("prevent_upload_dinos",                    "bPreventUploadDinos"),
            ("no_transfer_from_filtering",              "NoTransferFromFiltering"),
            ("enable_cryopod_nerf",                     "EnableCryopodNerf"),
            ("allow_crateSpawns_on_top_of_structures",  "AllowCrateSpawnsOnTopOfStructures"),
            ("use_optimized_harvesting_health",         "UseOptimizedHarvestingHealth"),
            ("b_passive_defenses_damage_riderless_dinos","bPassiveDefensesDamageRiderlessDinos"),
            ("global_voice_chat",                       "GlobalVoiceChat"),
            ("proximity_chat",                          "ProximityChat"),
            ("allow_raid_dino_feeding",                 "AllowRaidDinoFeeding"),
            ("b_auto_pve_timer",                        "bAutoPvETimer"),
            ("b_auto_pve_use_system_time",              "bAutoPvEUseSystemTime"),
            ("force_all_structure_locking",             "ForceAllStructureLocking"),
            ("force_flyer_explosives",                  "ForceFlyerExplosives"),
        ]

        float_fields = [
            ("cryopod_nerf_duration",                   "CryopodNerfDuration"),
            ("cryopod_nerf_damage_mult",                "CryopodNerfDamageMult"),
            ("raid_dino_character_food_drain_multiplier","RaidDinoCharacterFoodDrainMultiplier"),
            ("oxygen_swim_speed_stat_multiplier",       "OxygenSwimSpeedStatMultiplier"),
            ("dino_harvesting_damage_multiplier",       "DinoHarvestingDamageMultiplier"),
            ("player_harvesting_damage_multiplier",     "PlayerHarvestingDamageMultiplier"),
            ("custom_recipe_effectiveness_multiplier",  "CustomRecipeEffectivenessMultiplier"),
            ("custom_recipe_skill_multiplier",          "CustomRecipeSkillMultiplier"),
            ("auto_pve_start_time_seconds",             "AutoPvEStartTimeSeconds"),
            ("auto_pve_stop_time_seconds",              "AutoPvEStopTimeSeconds"),
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

    # ── Escrita ───────────────────────────────────────────────────────────────

    def save_game_user_settings(self, config: ServerConfig) -> None:
        """Escreve GameUserSettings.ini com os valores do ServerConfig."""
        path = get_ini_path(self._install_dir, "GameUserSettings.ini")
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.RawConfigParser()
        if path.exists():
            parser.read(str(path), encoding="utf-8")

        gs = config.game_settings

        for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
            if not parser.has_section(section):
                parser.add_section(section)
            value = getattr(gs, field_name)
            if typ is bool:
                parser.set(section, key, _bool_to_str(value))
            else:
                parser.set(section, key, str(value))

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

        with open(str(path), "w", encoding="utf-8") as fh:
            parser.write(fh)

    def save_game_ini(self, config: ServerConfig) -> None:
        """Escreve Game.ini com os valores de ServerConfig.advanced_settings."""
        path = get_ini_path(self._install_dir, "Game.ini")
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.RawConfigParser()
        if path.exists():
            parser.read(str(path), encoding="utf-8")

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

        with open(str(path), "w", encoding="utf-8") as fh:
            parser.write(fh)

    def save_all(self, config: ServerConfig) -> None:
        """Salva GameUserSettings.ini e Game.ini de uma vez."""
        self.save_game_user_settings(config)
        self.save_game_ini(config)
