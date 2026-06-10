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
from pathlib import Path
from typing import Any

from .asm_server_config import AsmServerConfig


# ── Mapeamento declarativo ────────────────────────────────────────────────────
# (campo_python): (arquivo, seção, chave_ini, opções)
INI_MAP: dict[str, tuple] = {
    # Administration
    "session_name":             ("GUS", "SessionSettings",  "SessionName",                {"always_write": True}),
    "server_password":          ("GUS", "ServerSettings",   "ServerPassword",              {}),
    "admin_password":           ("GUS", "ServerSettings",   "ServerAdminPassword",         {}),
    "spectator_password":       ("GUS", "ServerSettings",   "SpectatorPassword",           {}),
    "server_port":              ("GUS", "SessionSettings",  "Port",                        {"always_write": True}),
    "query_port":               ("GUS", "SessionSettings",  "QueryPort",                   {"always_write": True}),
    # server_ip (MultiHome) é argumento de linha de comando (?MultiHome=), não INI
    "max_players":              ("GUS", "GameSession",      "MaxPlayers",                  {"always_write": True}),
    "rcon_enabled":             ("GUS", "ServerSettings",   "RCONEnabled",                 {"always_write": True}),
    "rcon_port":                ("GUS", "ServerSettings",   "RCONPort",                    {"always_write": True}),
    "rcon_log_buffer":          ("GUS", "ServerSettings",   "RCONServerGameLogBuffer",     {}),
    "admin_logging":            ("GUS", "ServerSettings",   "AdminLogging",                {}),
    "active_mods":              ("GUS", "ServerSettings",   "ActiveMods",                  {"list_sep": ","}),
    "auto_save_period":         ("GUS", "ServerSettings",   "AutoSavePeriodMinutes",       {}),
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

    # Administration extras
    "max_tribe_logs":                          ("Game","GameMode",     "MaxTribeLogs",                                  {}),
    "tribe_log_destroyed_enemy_structures":    ("GUS", "ServerSettings","TribeLogDestroyedEnemyStructures",            {}),
    "allow_hide_damage_source":                ("GUS", "ServerSettings","AllowHideDamageSourceFromLogs",               {}),
    "enable_extinction_event":                 ("GUS", "ServerSettings","EnableExtinctionEvent",                       {}),
    "extinction_event_interval":               ("GUS", "ServerSettings","ExtinctionEventTimeInterval",                 {"conditional_on": "enable_extinction_event"}),
    "extinction_event_utc":                    ("Game","GameMode",     "NextExtinctionEventUTC",                        {"conditional_on": "enable_extinction_event"}),
    "enable_auto_respawn_wild_dinos":          ("GUS", "ServerSettings","EnableServerAutoForceRespawnWildDinosInterval", {}),
    "auto_respawn_wild_dinos_interval":        ("GUS", "ServerSettings","ServerAutoForceRespawnWildDinosInterval",     {"conditional_on": "enable_auto_respawn_wild_dinos"}),
    "kick_idle_players":                       ("GUS", "ServerSettings","KickIdlePlayersPeriod",                       {"conditional_on": "enable_kick_idle_players"}),

    # Rules extras
    "enable_extra_structure_prevention_volumes":("GUS","ServerSettings","EnableExtraStructurePreventionVolumes",        {}),
    "allow_pve_gamma":                         ("GUS", "ServerSettings","DisablePvEGamma",                             {"inverted": True}),
    "oxygen_swim_speed_stat_multiplier":       ("GUS", "ServerSettings","OxygenSwimSpeedStatMultiplier",               {}),
    "supply_crate_loot_quality_multiplier":    ("Game","GameMode",     "SupplyCrateLootQualityMultiplier",             {}),
    "fishing_loot_quality_multiplier":         ("Game","GameMode",     "FishingLootQualityMultiplier",                 {}),
    "use_corpse_life_span_multiplier":         ("Game","GameMode",     "UseCorpseLifeSpanMultiplier",                  {}),
    "global_powered_battery_durability_decrease": ("Game","GameMode", "GlobalPoweredBatteryDurabilityDecreasePerSecond", {}),
    "tribe_name_change_cooldown":              ("GUS", "ServerSettings","TribeNameChangeCooldown",                     {}),
    "random_supply_crate_points":              ("Game","GameMode",     "bRandomSupplyCratePoints",                     {}),  # prefixo b obrigatório
    "increase_pvp_respawn_interval":           ("Game","GameMode",     "bIncreasePvPRespawnInterval",                  {}),
    "pvp_respawn_check_period":                ("Game","GameMode",     "IncreasePvPRespawnIntervalCheckPeriod",         {"conditional_on": "increase_pvp_respawn_interval"}),
    "pvp_respawn_multiplier":                  ("Game","GameMode",     "IncreasePvPRespawnIntervalMultiplier",          {"conditional_on": "increase_pvp_respawn_interval"}),
    "pvp_respawn_base_amount":                 ("Game","GameMode",     "IncreasePvPRespawnIntervalBaseAmount",          {"conditional_on": "increase_pvp_respawn_interval"}),
    "prevent_pvp_offline_interval":            ("GUS", "ServerSettings","PreventOfflinePvPInterval",                   {"conditional_on": "prevent_pvp_offline"}),
    "prevent_pvp_offline_invincible_interval": ("Game","GameMode",     "PreventOfflinePvPConnectionInvincibleInterval", {"conditional_on": "prevent_pvp_offline"}),
    "auto_pve_use_system_time":                ("Game","GameMode",     "bAutoPvEUseSystemTime",                        {"conditional_on": "auto_pve_timer"}),
    "auto_pve_start_time":                     ("Game","GameMode",     "AutoPvEStartTimeSeconds",                      {"conditional_on": "auto_pve_timer"}),
    "auto_pve_stop_time":                      ("Game","GameMode",     "AutoPvEStopTimeSeconds",                       {"conditional_on": "auto_pve_timer"}),
    "allow_tribe_war_pve":                     ("Game","GameMode",     "bPvEAllowTribeWar",                            {}),
    "allow_tribe_war_cancel_pve":              ("Game","GameMode",     "bPvEAllowTribeWarCancel",                      {}),
    "custom_recipe_effectiveness_multiplier":  ("Game","GameMode",     "CustomRecipeEffectivenessMultiplier",          {}),
    "custom_recipe_skill_multiplier":          ("Game","GameMode",     "CustomRecipeSkillMultiplier",                  {}),
    "non_permanent_diseases":                  ("GUS", "ServerSettings","NonPermanentDiseases",                        {}),
    "override_npc_stasis_range_scale":         ("GUS", "ServerSettings","OverrideNPCNetworkStasisRangeScale",          {}),
    "npc_stasis_range_scale_start":            ("GUS", "ServerSettings","NPCNetworkStasisRangeScalePlayerCountStart",  {"conditional_on": "override_npc_stasis_range_scale"}),
    "npc_stasis_range_scale_end":              ("GUS", "ServerSettings","NPCNetworkStasisRangeScalePlayerCountEnd",    {"conditional_on": "override_npc_stasis_range_scale"}),
    "npc_stasis_range_scale_percent_end":      ("GUS", "ServerSettings","NPCNetworkStasisRangeScalePercentEnd",        {"conditional_on": "override_npc_stasis_range_scale"}),
    "use_corpse_locator":                      ("Game","GameMode",     "bUseCorpseLocator",                            {}),
    "prevent_spawn_animations":                ("GUS", "ServerSettings","PreventSpawnAnimations",                      {}),
    "allow_unlimited_respecs":                 ("Game","GameMode",     "bAllowUnlimitedRespecs",                       {}),
    "allow_platform_saddle_multi_floors":      ("Game","GameMode",     "bAllowPlatformSaddleMultiFloors",              {}),
    "max_alliances_per_tribe":                 ("Game","GameMode",     "MaxAlliancesPerTribe",                         {"conditional_on": "allow_tribe_alliances"}),
    "max_tribes_per_alliance":                 ("Game","GameMode",     "MaxTribesPerAlliance",                         {"conditional_on": "allow_tribe_alliances"}),
    "tribute_char_expiration_seconds":         ("GUS", "ServerSettings","TributeCharacterExpirationSeconds",           {"conditional_on": "save_tribute_char_expiration"}),
    "tribute_item_expiration_seconds":         ("GUS", "ServerSettings","TributeItemExpirationSeconds",                {"conditional_on": "save_tribute_item_expiration"}),
    "tribute_dino_expiration_seconds":         ("GUS", "ServerSettings","TributeDinoExpirationSeconds",                {"conditional_on": "save_tribute_dino_expiration"}),
    "min_dino_reupload_interval":              ("GUS", "ServerSettings","MinimumDinoReuploadInterval",                 {"conditional_on": "save_min_dino_reupload_interval"}),
    "cross_ark_allow_foreign_dino_downloads":  ("GUS", "ServerSettings","CrossARKAllowForeignDinoDownloads",           {}),

    # Dinos extras
    "dino_char_food_drain_multiplier":                  ("GUS","ServerSettings","DinoCharacterFoodDrainMultiplier",             {}),
    "dino_char_stamina_drain_multiplier":               ("GUS","ServerSettings","DinoCharacterStaminaDrainMultiplier",          {}),
    "dino_char_health_recovery_multiplier":             ("GUS","ServerSettings","DinoCharacterHealthRecoveryMultiplier",        {}),
    "allow_raid_dino_feeding":                          ("GUS","ServerSettings","AllowRaidDinoFeeding",                        {}),
    "raid_dino_food_drain_multiplier":                  ("GUS","ServerSettings","RaidDinoCharacterFoodDrainMultiplier",         {}),
    "allow_flying_stamina_recovery":                    ("GUS","ServerSettings","AllowFlyingStaminaRecovery",                  {}),
    "prevent_mate_boost":                               ("GUS","ServerSettings","PreventMateBoost",                            {}),
    "auto_destroy_decayed_dinos":                       ("GUS","ServerSettings","AutoDestroyDecayedDinos",                     {}),
    "pve_dino_decay_period_multiplier":                 ("GUS","ServerSettings","PvEDinoDecayPeriodMultiplier",                {}),
    "allow_multiple_attached_c4":                       ("GUS","ServerSettings","AllowMultipleAttachedC4",                     {}),
    "max_personal_tamed_dinos":                         ("GUS","ServerSettings","MaxPersonalTamedDinos",                       {}),
    "personal_tamed_dinos_saddle_structure_cost":       ("GUS","ServerSettings","PersonalTamedDinosSaddleStructureCost",       {}),
    "use_tame_limit_for_structures_only":               ("Game","GameMode",     "bUseTameLimitForStructuresOnly",              {}),
    "wild_dino_char_food_drain_multiplier":             ("Game","GameMode",     "WildDinoCharacterFoodDrainMultiplier",        {}),
    "tamed_dino_char_food_drain_multiplier":            ("Game","GameMode",     "TamedDinoCharacterFoodDrainMultiplier",       {}),
    "wild_dino_torpor_drain_multiplier":                ("Game","GameMode",     "WildDinoTorporDrainMultiplier",               {}),
    "tamed_dino_torpor_drain_multiplier":               ("Game","GameMode",     "TamedDinoTorporDrainMultiplier",              {}),
    "override_max_xp_dino":                             ("Game","GameMode",     "OverrideMaxExperiencePointsDino",             {}),
    "baby_cuddle_grace_period_multiplier":              ("Game","GameMode",     "BabyCuddleGracePeriodMultiplier",             {}),
    "baby_cuddle_lose_imprint_quality_speed_multiplier":("Game","GameMode",     "BabyCuddleLoseImprintQualitySpeedMultiplier", {}),
    "dino_turret_damage_multiplier":                    ("Game","GameMode",     "DinoTurretDamageMultiplier",                  {}),

    # Environment extras
    "craft_xp_multiplier":                     ("Game","GameMode","CraftXPMultiplier",                          {}),
    "generic_xp_multiplier":                   ("Game","GameMode","GenericXPMultiplier",                        {}),
    "harvest_xp_multiplier":                   ("Game","GameMode","HarvestXPMultiplier",                        {}),
    "kill_xp_multiplier":                      ("Game","GameMode","KillXPMultiplier",                           {}),
    "special_xp_multiplier":                   ("Game","GameMode","SpecialXPMultiplier",                        {}),
    "lay_egg_interval_multiplier":             ("Game","GameMode","LayEggIntervalMultiplier",                   {}),
    "poop_interval_multiplier":                ("Game","GameMode","PoopIntervalMultiplier",                     {}),
    "resource_no_replenish_radius_players":    ("Game","GameMode","ResourceNoReplenishRadiusPlayers",           {}),
    "resource_no_replenish_radius_structures": ("Game","GameMode","ResourceNoReplenishRadiusStructures",        {}),
    "use_optimized_harvesting_health":         ("GUS", "ServerSettings","UseOptimizedHarvestingHealth",         {}),
    "clamp_resource_harvest_damage":           ("GUS", "ServerSettings","ClampResourceHarvestDamage",           {}),
    "clamp_item_spoiling_times":               ("GUS", "ServerSettings","ClampItemSpoilingTimes",               {}),

    # Structures extras
    "pvp_structure_decay":                         ("GUS","ServerSettings","PvPStructureDecay",                             {}),
    "pvp_zone_structure_damage_multiplier":        ("Game","GameMode",     "PvPZoneStructureDamageMultiplier",              {}),
    "structure_damage_repair_cooldown":            ("GUS", "ServerSettings","StructureDamageRepairCooldown",                 {}),  # GUS ServerSettings (não Game.ini)
    "override_structure_platform_prevention":      ("GUS","ServerSettings","OverrideStructurePlatformPrevention",           {}),
    "flyer_platform_allow_unaligned_dino_basing":  ("Game","GameMode",     "bFlyerPlatformAllowUnalignedDinoBasing",        {}),
    "pve_allow_structures_at_supply_drops":        ("GUS","ServerSettings","PvEAllowStructuresAtSupplyDrops",               {}),
    "only_auto_destroy_core_structures":           ("GUS","ServerSettings","OnlyAutoDestroyCoreStructures",                 {}),
    "only_decay_unsnapped_core_structures":        ("GUS","ServerSettings","OnlyDecayUnsnappedCoreStructures",              {}),
    "fast_decay_unsnapped_core_structures":        ("GUS","ServerSettings","FastDecayUnsnappedCoreStructures",              {}),
    "destroy_unconnected_water_pipes":             ("GUS","ServerSettings","DestroyUnconnectedWaterPipes",                  {}),
    "fast_decay_interval":                         ("Game","GameMode",     "FastDecayInterval",                             {"conditional_on": "enable_fast_decay_interval"}),
    "hard_limit_turrets_in_range":                 ("Game","GameMode",     "bHardLimitTurretsInRange",                      {}),
    "passive_defenses_damage_riderless_dinos":     ("Game","GameMode",     "bPassiveDefensesDamageRiderlessDinos",          {}),

    # Engrams
    "only_allow_specified_engrams":              ("Game","GameMode","bOnlyAllowSpecifiedEngrams",                {"conditional_on": "only_allow_specified_engrams"}),
    "auto_unlock_all_engrams":                   ("Game","GameMode","bAutoUnlockAllEngrams",                     {"conditional_on": "auto_unlock_all_engrams"}),

    # PGM
    "pgm_name":                                  ("Game","GameMode","PGMapName",                                 {"conditional_on": "pgm_enabled"}),
    "pgm_terrain_string":                        ("Game","GameMode","PGTerrainPropertiesString",                 {"conditional_on": "pgm_enabled"}),
}

# Mapeamento de arquivo → nome real do arquivo INI
_FILE_NAMES = {
    "GUS":  "GameUserSettings.ini",
    "Game": "Game.ini",
}

# Seção do Game.ini — depende do modo de jogo
_GAME_MODE_SECTION = "/Script/ShooterGame.ShooterGameMode"
# Seção do GUS para MaxPlayers — ASM usa /Script/Engine.GameSession, não "GameSession"
_GUS_GAME_SESSION_SECTION = "/Script/Engine.GameSession"


def _resolve_ini_section(file_key: str, section: str) -> str:
    """Mapeia nomes lógicos do INI_MAP para as seções reais do ARK."""
    if file_key == "Game" and section == "GameMode":
        return _GAME_MODE_SECTION
    if file_key == "GUS" and section == "GameSession":
        return _GUS_GAME_SESSION_SECTION
    return section


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
        section_key = _resolve_ini_section(file_key, section)
        target.setdefault(section_key, {})[ini_key] = value

    # SessionName é obrigatório para listagem — garante gravação mesmo se INI_MAP falhar
    _sn = (cfg.session_name or "").strip()
    if _sn:
        gus.setdefault("SessionSettings", {})["SessionName"] = _sn

    # Seções customizadas livres (legado)
    for custom in cfg.custom_ini_sections:
        f = custom.get("file", "GUS").upper()
        sec = custom.get("section", "")
        target = gus if f in ("GUS", "GAMEUSERSETTINGS.INI") else game
        for entry in custom.get("entries", []):
            target.setdefault(sec, {})[entry["key"]] = entry["value"]

    # Raw INI injetado pelo usuário (parseia linhas key=value por seção)
    def _inject_raw(raw_text: str, target: dict[str, dict[str, str]]) -> None:
        current_sec = "ServerSettings"
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_sec = line[1:-1]
            elif "=" in line:
                k, _, v = line.partition("=")
                target.setdefault(current_sec, {})[k.strip()] = v.strip()

    if cfg.custom_gus_ini_raw:
        _inject_raw(cfg.custom_gus_ini_raw, gus)
    if cfg.custom_game_ini_raw:
        _inject_raw(cfg.custom_game_ini_raw, game)

    # Raw overrides para Game.ini (engrams, levels, crafting, stacks, spawners, supply crates)
    for raw_text in (
        cfg.engram_entries_raw,
        cfg.player_level_stats_raw,
        cfg.dino_level_stats_raw,
        cfg.crafting_overrides_raw,
        cfg.stack_size_overrides_raw,
        cfg.npc_spawn_overrides_raw,
        cfg.supply_crate_overrides_raw,
    ):
        if raw_text:
            _inject_raw(raw_text, game)

    if cfg.prevent_transfer_raw:
        _inject_raw(cfg.prevent_transfer_raw, gus)

    # Per-level stat multipliers (array-indexed — não entram no INI_MAP convencional)
    _PERLEVEL_MAP = [
        ("per_level_player",              "PerLevelStatsMultiplier_Player"),
        ("per_level_dino_wild",           "PerLevelStatsMultiplier_DinoWild"),
        ("per_level_dino_tamed",          "PerLevelStatsMultiplier_DinoTamed"),
        ("per_level_dino_tamed_add",      "PerLevelStatsMultiplier_DinoTamed_Add"),
        ("per_level_dino_tamed_affinity", "PerLevelStatsMultiplier_DinoTamed_Affinity"),
    ]
    game_mode_sec = game.setdefault(_GAME_MODE_SECTION, {})
    for _attr, _prefix in _PERLEVEL_MAP:
        _values: list = getattr(cfg, _attr, [])
        for _idx, _val in enumerate(_values):
            game_mode_sec[f"{_prefix}[{_idx}]"] = _format_value(_val)

    _write_ini_file(_ini_path(cfg.install_dir, "GUS"),  gus)
    _write_ini_file(_ini_path(cfg.install_dir, "Game"), game)

    # Engine.ini (apenas raw)
    if cfg.custom_engine_ini_raw:
        engine: dict[str, dict[str, str]] = {}
        _inject_raw(cfg.custom_engine_ini_raw, engine)  # type: ignore[arg-type]
        _write_ini_file(
            Path(cfg.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "Engine.ini",
            engine,
        )


def _write_ini_file(path: Path, sections: dict[str, dict[str, str]]) -> None:
    """Escreve um arquivo INI preservando seções existentes não gerenciadas."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Lê o arquivo existente (se houver) para preservar seções não mapeadas
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # type: ignore[assignment]  # preserva case
    if path.exists():
        for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as fh:
                    parser.read_file(fh)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                break

    # Injeta / substitui as seções gerenciadas
    for section, kvs in sections.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in kvs.items():
            parser.set(section, key, value)

    # ARK no Windows lê os INIs em UTF-16 LE com BOM.
    # Gravar em UTF-8 faz o jogo ignorar silenciosamente algumas chaves.
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-16") as fh:
        parser.write(fh, space_around_delimiters=False)
    tmp.replace(path)


def read_ini(cfg: AsmServerConfig) -> None:
    """Lê GameUserSettings.ini e Game.ini e popula cfg in-place."""
    if not cfg.install_dir:
        return

    parsers: dict[str, configparser.RawConfigParser] = {}
    for fk in ("GUS", "Game"):
        p = configparser.RawConfigParser()
        p.optionxform = str  # type: ignore[assignment]
        fp = _ini_path(cfg.install_dir, fk)
        if fp.exists():
            for enc in ("utf-16", "utf-8-sig", "utf-8", "latin-1"):
                try:
                    with open(fp, "r", encoding=enc) as fh:
                        p.read_file(fh)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception:
                    break
        parsers[fk] = p

    for field_name, (file_key, section, ini_key, opts) in INI_MAP.items():
        p = parsers[file_key]
        sec = _resolve_ini_section(file_key, section)
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

    # Per-level stat multipliers (array-indexed)
    _PERLEVEL_INI_TO_FIELD = {
        "Player":          "per_level_player",
        "DinoWild":        "per_level_dino_wild",
        "DinoTamed":       "per_level_dino_tamed",
        "DinoTamed_Add":   "per_level_dino_tamed_add",
        "DinoTamed_Affinity": "per_level_dino_tamed_affinity",
    }
    import re as _re
    game_p = parsers["Game"]
    if game_p.has_section(_GAME_MODE_SECTION):
        for ini_key, raw_val in game_p.items(_GAME_MODE_SECTION):
            m = _re.match(r"PerLevelStatsMultiplier_(\w+)\[(\d+)\]", ini_key, _re.IGNORECASE)
            if m:
                suffix = m.group(1)
                idx    = int(m.group(2))
                attr   = _PERLEVEL_INI_TO_FIELD.get(suffix)
                if attr:
                    lst = getattr(cfg, attr, [])
                    if isinstance(lst, list) and idx < len(lst):
                        try:
                            lst[idx] = float(raw_val)
                        except ValueError:
                            pass


def read_ini_from_paths(
    cfg: AsmServerConfig,
    gus_path: str | None = None,
    game_path: str | None = None,
) -> None:
    """Lê .ini de caminhos explícitos e popula cfg in-place.

    Equivalente a read_ini() mas sem depender de install_dir.
    Útil para importar configs de qualquer diretório.
    """
    parsers: dict[str, configparser.RawConfigParser] = {}
    path_map: dict[str, str | None] = {"GUS": gus_path, "Game": game_path}

    for fk, fp_str in path_map.items():
        p = configparser.RawConfigParser()
        p.optionxform = str  # type: ignore[assignment]
        if fp_str:
            fp = Path(fp_str)
            if fp.exists():
                try:
                    with open(fp, "r", encoding="utf-8-sig") as fh:
                        p.read_file(fh)
                except Exception:
                    pass
        parsers[fk] = p

    for field_name, (file_key, section, ini_key, opts) in INI_MAP.items():
        p = parsers[file_key]
        sec = _resolve_ini_section(file_key, section)
        if not p.has_option(sec, ini_key):
            continue
        raw = p.get(sec, ini_key)

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

        if opts.get("inverted") and isinstance(val, bool):
            val = not val

        setattr(cfg, field_name, val)

    # Per-level stat multipliers (array-indexed)
    _PERLEVEL_INI_TO_FIELD = {
        "Player":             "per_level_player",
        "DinoWild":           "per_level_dino_wild",
        "DinoTamed":          "per_level_dino_tamed",
        "DinoTamed_Add":      "per_level_dino_tamed_add",
        "DinoTamed_Affinity": "per_level_dino_tamed_affinity",
    }
    import re as _re
    game_p = parsers["Game"]
    if game_p.has_section(_GAME_MODE_SECTION):
        for ini_key, raw_val in game_p.items(_GAME_MODE_SECTION):
            m = _re.match(r"PerLevelStatsMultiplier_(\w+)\[(\d+)\]", ini_key, _re.IGNORECASE)
            if m:
                suffix = m.group(1)
                idx    = int(m.group(2))
                attr   = _PERLEVEL_INI_TO_FIELD.get(suffix)
                if attr:
                    lst = getattr(cfg, attr, [])
                    if isinstance(lst, list) and idx < len(lst):
                        try:
                            lst[idx] = float(raw_val)
                        except ValueError:
                            pass


def build_launch_args(cfg: AsmServerConfig) -> list[str]:
    """Monta a lista de argumentos de linha de comando fiel ao ASM GetServerArgs().

    SessionName: sempre gravado no GUS.ini ([SessionSettings]/SessionName).
    Quando o nome NÃO contém espaços, também vai na CLI (?SessionName=) como
    cobertura extra — evita o nome genérico 'ARK #NNNNNN' se o INI não for lido.
    Nomes com espaços ficam somente no INI (espaços quebram o parsing do cmd.exe).
    """
    params = [
        f"{cfg.server_map}",
        "?listen",
        f"?Port={cfg.server_port}",
        f"?QueryPort={cfg.query_port}",
        f"?MaxPlayers={cfg.max_players}",
    ]
    _sn = (cfg.session_name or "").strip()
    if _sn and " " not in _sn:
        params.append(f"?SessionName={_sn}")
    if cfg.server_ip:
        params.append(f"?MultiHome={cfg.server_ip}")
    if cfg.alt_save_directory_name:
        params.append(f"?AltSaveDirectoryName={cfg.alt_save_directory_name}")

    flags = ["-nosteamclient", "-game", "-server", "-log"]
    if cfg.allow_cave_flyers:
        flags.append("-ForceAllowCaveFlyers")

    # Cluster: -clusterid= é flag de dash, não URL param (?ClusterId= é ignorado pelo ARK).
    # Referência: primitivo src/server_config.py e comando saudável confirmam isso.
    if cfg.cross_ark_cluster_id:
        flags.append(f"-clusterid={cfg.cross_ark_cluster_id}")
        if cfg.cluster_dir_override:
            _cl_dir = cfg.cluster_dir_override.replace("/", "\\")
            if " " in _cl_dir:
                flags.append(f'"-ClusterDirOverride={_cl_dir}"')
            else:
                flags.append(f"-ClusterDirOverride={_cl_dir}")

    if cfg.additional_args.strip():
        import shlex
        try:
            flags += shlex.split(cfg.additional_args)
        except Exception:
            flags.append(cfg.additional_args)

    # O ARK usa o parser do Unreal Engine que lê o command line raw.
    # Aspas ao redor do MAP?params fazem o UE incluí-las no token, quebrando
    # o parsing de ?Port=, ?QueryPort=, ?AltSaveDirectoryName= etc.
    # SessionName na CLI só quando sem espaços; map string permanece sem aspas.
    combined_map = "".join(params)
    return [combined_map] + flags
