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
import re
import shutil
from collections.abc import Callable
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
    "active_event":             ("GUS", "ServerSettings",   "ActiveEvent",                 {"conditional_on": "active_event"}),
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
    "enable_cryo_sickness_pvp":     ("GUS", "ServerSettings", "EnableCryoSicknessPVP",      {}),
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
    "allow_flyer_speed_leveling":           ("Game","GameMode",     "bAllowFlyerSpeedLeveling",               {}),
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
    # Extensões SM (Fase 5)
    "item_stack_size_multiplier":                  ("GUS","ServerSettings","ItemStackSizeMultiplier",                    {}),
    "spoiling_time_multiplier":                    ("GUS","ServerSettings","SpoilingTimeMultiplier",                     {}),
    "item_decomposition_time_multiplier":          ("GUS","ServerSettings","ItemDecompositionTimeMultiplier",          {}),
    "platform_saddle_build_area_bounds_multiplier": ("GUS","ServerSettings","PlatformSaddleBuildAreaBoundsMultiplier", {}),
    "max_tribute_dinos":                           ("GUS","ServerSettings","MaxTributeDinos",                          {}),
    "max_tribute_items":                           ("GUS","ServerSettings","MaxTributeItems",                          {}),
    "baby_imprint_amount_multiplier":              ("Game","GameMode",     "BabyImprintAmountMultiplier",               {}),
    "enable_creative_mode":                        ("Game","GameMode",     "bShowCreativeMode",                         {}),

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
    "limit_turrets_in_range":                    ("Game","GameMode",     "bLimitTurretsInRange",                        {}),
    "limit_turrets_range":                       ("Game","GameMode",     "LimitTurretsRange",                          {"conditional_on": "limit_turrets_in_range"}),
    "limit_turrets_num":                         ("Game","GameMode",     "LimitTurretsNum",                            {"conditional_on": "limit_turrets_in_range"}),

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
    "always_allow_structure_pickup":               ("GUS","ServerSettings","AlwaysAllowStructurePickup",                    {}),
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


def effective_session_name(cfg: AsmServerConfig) -> str:
    """Nome exibido no browser ARK — session_name tem prioridade; fallback para cfg.name."""
    sn = (cfg.session_name or "").strip()
    if sn:
        return sn
    return (cfg.name or "").strip() or "My ARK Server"


_SIMPLE_CLI_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _session_name_cli_param(cfg: AsmServerConfig) -> str | None:
    """?SessionName= na CLI só para nomes simples (sem espaços/colchetes).

    Nomes complexos ficam apenas no GUS.ini (UTF-16 + aspas). O RunServer.cmd
    duplica % como %% — nomes simples na CLI ajudam quando o INI não é lido a tempo.
    """
    sn = effective_session_name(cfg)
    if sn and _SIMPLE_CLI_SESSION_RE.match(sn):
        return f"?SessionName={sn}"
    return None


def _windows_server_ini_dir(cfg: AsmServerConfig) -> Path:
    return Path(cfg.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"


def _read_ini_dir(cfg: AsmServerConfig) -> Path:
    """Diretório de leitura: pasta custom ASE se definida, senão WindowsServer."""
    custom = (cfg.user_config_folder or "").strip()
    if custom:
        p = Path(custom)
        if p.is_dir():
            return p
    return _windows_server_ini_dir(cfg)


def sync_user_config_folder_to_server(cfg: AsmServerConfig) -> None:
    """Copia INIs da pasta custom para WindowsServer antes do start (paridade ASM ASE)."""
    custom = (cfg.user_config_folder or "").strip()
    if not custom or not cfg.install_dir:
        return
    src_dir = Path(custom)
    if not src_dir.is_dir():
        return
    dest_dir = _windows_server_ini_dir(cfg)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in ("GameUserSettings.ini", "Game.ini", "Engine.ini"):
        src = src_dir / name
        if src.is_file():
            shutil.copy2(src, dest_dir / name)


def _ini_path(install_dir: str, file_key: str) -> Path:
    name = _FILE_NAMES[file_key]
    return Path(install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / name


def _ini_path_for_cfg(cfg: AsmServerConfig, file_key: str, *, write: bool = False) -> Path:
    base = _windows_server_ini_dir(cfg) if write else _read_ini_dir(cfg)
    return base / _FILE_NAMES[file_key]


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


def _strip_ini_quotes(value: str) -> str:
    """Remove aspas externas de valores INI (ARK/ASM)."""
    v = value.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


def _ini_quote_value(value: str) -> str:
    """Coloca aspas quando o valor pode confundir o parser do ARK ([, ], espaços)."""
    if any(c in value for c in " []"):
        if not (value.startswith('"') and value.endswith('"')):
            return f'"{value}"'
    return value


_GUS_DEFAULT_SECTION = "ServerSettings"


def inject_raw_ini_text(
    raw_text: str,
    target: dict[str, dict[str, str]],
    *,
    default_section: str = _GUS_DEFAULT_SECTION,
    skip_key: Callable[[str], bool] | None = None,
) -> None:
    """Parse blocos ``[Seção]`` + ``chave=valor`` e injeta no dict destino.

    ``default_section`` é usada para linhas sem cabeçalho de seção explícito.
    Game.ini deve usar ``_GAME_MODE_SECTION``; GameUserSettings.ini usa
    ``ServerSettings``.
    """
    current_sec = default_section
    text = raw_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            end = stripped.find("]")
            if end > 0:
                current_sec = stripped[1:end].strip()
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            k, v = k.strip(), v.strip()
            if k and (skip_key is None or not skip_key(k)):
                target.setdefault(current_sec, {})[k] = v


def _iter_custom_ini_sections(cfg: AsmServerConfig):
    """Itera seções custom legadas (lista ASM ou dict ``gus``/``game`` do TEK)."""
    raw = cfg.custom_ini_sections
    if isinstance(raw, dict):
        for file_key, secs in raw.items():
            fk = str(file_key).upper()
            file_tag = "GUS" if fk in ("GUS", "GAMEUSERSETTINGS", "GAMEUSERSETTINGS.INI") else "Game"
            if not isinstance(secs, list):
                continue
            for sec in secs:
                if isinstance(sec, dict):
                    yield file_tag, sec.get("section", ""), sec.get("entries", [])
        return
    if not isinstance(raw, list):
        return
    for custom in raw:
        if not isinstance(custom, dict):
            continue
        f = custom.get("file", "GUS").upper()
        yield f, custom.get("section", ""), custom.get("entries", [])


def _render_ini_text(
    parser: configparser.RawConfigParser,
    section_order: tuple[str, ...] | None = None,
) -> str:
    """Renderiza INI no formato nativo do ARK (key=value, seções separadas por linha em branco)."""
    if section_order:
        order_lower = {s.lower(): s for s in section_order}
        seen: set[str] = set()
        ordered: list[str] = []
        for sec in section_order:
            for existing in parser.sections():
                if existing.lower() == sec.lower() and existing not in seen:
                    ordered.append(existing)
                    seen.add(existing)
                    break
        for sec in parser.sections():
            if sec not in seen:
                ordered.append(sec)
        sections = ordered
    else:
        sections = parser.sections()

    lines: list[str] = []
    for section in sections:
        lines.append(f"[{section}]")
        for key, value in parser.items(section, raw=True):
            lines.append(f"{key}={_ini_quote_value(value)}")
        lines.append("")
    return "\r\n".join(lines)


def write_ini(cfg: AsmServerConfig) -> None:
    """Escreve GameUserSettings.ini e Game.ini a partir de AsmServerConfig.

    ⚠️  T13 PENDENTE — confirmar se a escrita causa crash do ArkShopUI antes
        de usar em produção. Ver PENDING_ISSUES.md T13.
    """
    if not cfg.install_dir:
        raise ValueError("install_dir não configurado")

    from ..ui_constants import normalize_active_event
    cfg.active_event = normalize_active_event(cfg.active_event)

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

    # Seções customizadas livres (legado)
    for f, sec, entries in _iter_custom_ini_sections(cfg):
        target = gus if f in ("GUS", "GAMEUSERSETTINGS.INI") else game
        for entry in entries:
            key = entry.get("key", "")
            if key:
                target.setdefault(sec, {})[key] = entry.get("value", "")

    # Raw INI injetado pelo usuário (parseia linhas key=value por seção)
    from .asm_game_list_ini import is_repeated_game_ini_key

    if cfg.custom_gus_ini_raw:
        inject_raw_ini_text(cfg.custom_gus_ini_raw, gus, default_section=_GUS_DEFAULT_SECTION)
    if cfg.custom_game_ini_raw:
        inject_raw_ini_text(
            cfg.custom_game_ini_raw,
            game,
            default_section=_GAME_MODE_SECTION,
            skip_key=is_repeated_game_ini_key,
        )

    # Raw overrides (engrams, levels) — chaves únicas via inject_raw_ini_text
    from ..player_engram_points import (
        should_apply_engram_multiplier,
        strip_engram_points_from_raw,
    )

    player_level_raw = cfg.player_level_stats_raw
    if should_apply_engram_multiplier(cfg):
        player_level_raw = strip_engram_points_from_raw(player_level_raw)

    for raw_text in (
        cfg.engram_entries_raw,
        player_level_raw,
        cfg.dino_level_stats_raw,
    ):
        if raw_text:
            inject_raw_ini_text(raw_text, game, default_section=_GAME_MODE_SECTION)
    # crafting/stack/spawner/supply + listas agregadas → patch pós-escrita (chaves repetidas)

    if cfg.prevent_transfer_raw:
        inject_raw_ini_text(cfg.prevent_transfer_raw, gus, default_section=_GUS_DEFAULT_SECTION)

    remove_gus_options: list[tuple[str, str]] = []
    if not cfg.active_event and "ServerSettings" in gus and "ActiveEvent" in gus.get("ServerSettings", {}):
        del gus["ServerSettings"]["ActiveEvent"]
    if not cfg.active_event:
        remove_gus_options.append(("ServerSettings", "ActiveEvent"))

    # SessionName por último — raw/custom não pode sobrescrever o nome efetivo
    _sn = effective_session_name(cfg)
    if _sn:
        gus.setdefault("SessionSettings", {})["SessionName"] = _sn
        gus.setdefault("ServerSettings", {})["SessionName"] = _sn

    # MaxPlayers: espelhar em todas as seções que o ARK/Steam podem ler.
    # Só atualizar [/Script/Engine.GameSession] deixa MaxPlayers=70 obsoleto em
    # [SessionSettings] (modo primitivo / ASM legado) — a listagem Steam usa o valor antigo.
    _mp = _format_value(cfg.max_players)
    gus.setdefault("SessionSettings", {})["MaxPlayers"] = _mp
    gus.setdefault("GameSession", {})["MaxPlayers"] = _mp

    # ActiveMods: inclui map mod (paridade modo primitivo)
    from .asm_mod_utils import active_mods_for_ini
    _mods_ini = active_mods_for_ini(cfg)
    gus.setdefault("ServerSettings", {})["ActiveMods"] = ",".join(_mods_ini)

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

    _write_ini_file(_ini_path_for_cfg(cfg, "GUS", write=True),  gus, remove_options=remove_gus_options)
    _game_path = _ini_path_for_cfg(cfg, "Game", write=True)
    _write_ini_file(_game_path, game)

    from .asm_game_list_ini import build_repeated_game_lines, patch_game_ini_repeated_lines
    patch_game_ini_repeated_lines(_game_path, build_repeated_game_lines(cfg))

    # Engine.ini (apenas raw)
    if cfg.custom_engine_ini_raw:
        engine: dict[str, dict[str, str]] = {}
        inject_raw_ini_text(cfg.custom_engine_ini_raw, engine)
        _write_ini_file(
            _windows_server_ini_dir(cfg) / "Engine.ini",
            engine,
        )

    custom = (cfg.user_config_folder or "").strip()
    if custom:
        dest_custom = Path(custom)
        dest_custom.mkdir(parents=True, exist_ok=True)
        for fk in ("GUS", "Game"):
            src = _ini_path_for_cfg(cfg, fk, write=True)
            if src.is_file():
                shutil.copy2(src, dest_custom / _FILE_NAMES[fk])


def _write_ini_file(
    path: Path,
    sections: dict[str, dict[str, str]],
    *,
    remove_options: list[tuple[str, str]] | None = None,
) -> None:
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

    for section, key in remove_options or []:
        if parser.has_section(section) and parser.has_option(section, key):
            parser.remove_option(section, key)

    if path.name.lower() == "gameusersettings.ini":
        from ..ark_ini_fields import ensure_gus_ark_skeleton, GUS_SECTION_ORDER
        ensure_gus_ark_skeleton(parser)
        _section_order = GUS_SECTION_ORDER
    else:
        _section_order = None

    # ARK no Windows lê os INIs em UTF-16 LE com BOM.
    # configparser.write() não cita valores com '[' — o ARK interpreta como seção nova.
    tmp = path.with_suffix(".tmp")
    text = _render_ini_text(parser, section_order=_section_order)
    with open(tmp, "wb") as fh:
        fh.write(b"\xff\xfe")
        fh.write(text.encode("utf-16-le"))
    tmp.replace(path)


def read_ini(cfg: AsmServerConfig) -> None:
    """Lê GameUserSettings.ini e Game.ini e popula cfg in-place."""
    if not cfg.install_dir:
        return

    parsers: dict[str, configparser.RawConfigParser] = {}
    for fk in ("GUS", "Game"):
        p = configparser.RawConfigParser()
        p.optionxform = str  # type: ignore[assignment]
        fp = _ini_path_for_cfg(cfg, fk, write=False)
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
                val = _strip_ini_quotes(raw)
        except Exception:
            continue

        # Desfaz inversão
        if opts.get("inverted") and isinstance(val, bool):
            val = not val

        setattr(cfg, field_name, val)

    from ..ui_constants import normalize_active_event
    cfg.active_event = normalize_active_event(cfg.active_event)

    # SessionName: fallback em ServerSettings (instalações Steam/ASM legadas)
    _gus = parsers["GUS"]
    if not (cfg.session_name or "").strip():
        for _sec in ("SessionSettings", "ServerSettings"):
            if _gus.has_option(_sec, "SessionName"):
                _sn = _strip_ini_quotes(_gus.get(_sec, "SessionName")).strip()
                if _sn:
                    cfg.session_name = _sn
                    break

    # MaxPlayers: prioridade [/Script/Engine.GameSession] → [GameSession] → [SessionSettings]
    for _sec in (_GUS_GAME_SESSION_SECTION, "GameSession", "SessionSettings"):
        if _gus.has_option(_sec, "MaxPlayers"):
            try:
                cfg.max_players = int(float(_gus.get(_sec, "MaxPlayers")))
                break
            except ValueError:
                pass

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

    if cfg.install_dir:
        from .asm_game_list_ini import populate_lists_from_game_ini
        populate_lists_from_game_ini(cfg, _ini_path_for_cfg(cfg, "Game", write=False))

    from ..rcon_util import sanitize_rcon_password
    cfg.admin_password = sanitize_rcon_password(cfg.admin_password)


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

    if game_path:
        from .asm_game_list_ini import populate_lists_from_game_ini
        populate_lists_from_game_ini(cfg, Path(game_path))


def _launch_url_params(cfg: AsmServerConfig) -> list[str]:
    """Parâmetros ?key=value concatenados ao mapa (estilo ASM/UE)."""
    from .asm_mod_utils import map_cli_name

    params = [
        map_cli_name(cfg.server_map, cfg.install_dir or ""),
        "?listen",
    ]
    _sn_cli = _session_name_cli_param(cfg)
    if _sn_cli:
        params.append(_sn_cli)
    params.extend([
        f"?Port={cfg.server_port}",
        f"?QueryPort={cfg.query_port}",
        f"?MaxPlayers={cfg.max_players}",
    ])
    if cfg.exclusive_join:
        params.append("?ExclusiveJoin")
    from ..ui_constants import normalize_active_event
    _evt = normalize_active_event(cfg.active_event)
    if _evt:
        params.append(f"?ActiveEvent={_evt}")
    if cfg.auto_save_period != 15.0:
        params.append(f"?AutoSavePeriodMinutes={cfg.auto_save_period}")
    if cfg.server_ip:
        params.append(f"?MultiHome={cfg.server_ip}")
    if cfg.use_raw_sockets:
        params.append("?bRawSockets")
    if cfg.alt_save_directory_name:
        params.append(f"?AltSaveDirectoryName={cfg.alt_save_directory_name}")
    if cfg.prevent_spawn_animations:
        params.append("?PreventSpawnAnimations=True")
    if cfg.show_floating_damage_text:
        params.append("?ShowFloatingDamageText=True")
    return params


def _launch_dash_flags(cfg: AsmServerConfig) -> list[str]:
    """Flags -flag (dash) do executável do servidor."""
    flags: list[str] = []

    if (cfg.total_conversion_mod_id or "").strip():
        flags.append(f"-TotalConversionMod={cfg.total_conversion_mod_id.strip()}")

    flags.extend(["-nosteamclient", "-game", "-server", "-log"])

    if not cfg.use_battleye:
        flags.append("-NoBattlEye")
    if cfg.use_allcores:
        flags.append("-useallavailablecores")
    if cfg.force_respawn_dinos:
        flags.append("-ForceRespawnDinos")
    if cfg.crossplay:
        flags.append("-crossplay")
        if cfg.public_ip_for_epic:
            flags.append(f"-PublicIPForEpic={cfg.public_ip_for_epic}")
    if cfg.epic_only:
        flags.append("-epiconly")
    if cfg.use_vivox:
        flags.append("-UseVivox")
    if cfg.use_item_dupe_check:
        flags.append("-UseItemDupeCheck")
    if cfg.no_net_threading:
        flags.append("-nonetthreading")
    if cfg.force_net_threading:
        flags.append("-forcenetthreading")

    if cfg.no_dinos:
        flags.append("-NoDinos")
    if cfg.allow_cave_flyers:
        flags.append("-ForceAllowCaveFlyers")
    if cfg.enable_auto_destroy_structures:
        flags.append("-AutoDestroyStructures")
    if cfg.enable_no_fish_loot:
        flags.append("-nofishloot")

    if cfg.disable_vac:
        flags.append("-insecure")
    if cfg.disable_anti_speed_hack:
        flags.append("-noantispeedhack")
    elif cfg.speed_hack_bias != 1.0:
        flags.append(f"-speedhackbias={cfg.speed_hack_bias}f")
    if cfg.disable_player_move_physics_opt:
        flags.append("-nocombineclientmoves")

    if cfg.force_dx10:
        flags.append("-d3d10")
    if cfg.force_shader_model4:
        flags.append("-sm4")
    if cfg.force_low_memory:
        flags.append("-lowmemory")
    if cfg.use_cache:
        flags.append("-usecache")
    if cfg.use_old_save_format:
        flags.append("-oldsaveformat")
    if cfg.use_no_memory_bias:
        flags.append("-nomemorybias")
    if cfg.stasis_keep_controllers:
        flags.append("-StasisKeepControllers")
    if cfg.use_no_hang_detection:
        flags.append("-NoHangDetection")

    if cfg.server_allow_ansel:
        flags.append("-ServerAllowAnsel")
    if cfg.enable_server_admin_logs:
        flags.append("-servergamelog")
        if cfg.server_admin_logs_include_tribe_logs:
            flags.append("-servergamelogincludetribelogs")
    if cfg.server_rcon_output_tribe_logs:
        flags.append("-ServerRCONOutputTribeLogs")
    if cfg.notify_admin_commands_in_chat:
        flags.append("-NotifyAdminCommandsInChat")

    if cfg.enable_web_alarm:
        flags.append("-webalarm")
        if cfg.web_alarm_key:
            flags.append(f"-webalarmkey={cfg.web_alarm_key}")
        if cfg.web_alarm_url:
            flags.append(f"-webalarmurl={cfg.web_alarm_url}")

    if cfg.cross_ark_cluster_id:
        if cfg.no_transfer_from_filtering:
            flags.append("-NoTransferFromFiltering")
        flags.append(f"-clusterid={cfg.cross_ark_cluster_id}")
        if cfg.cluster_dir_override:
            from ..cluster_paths import format_cluster_dir_launch_flag
            _flag = format_cluster_dir_launch_flag(cfg.cluster_dir_override)
            if _flag:
                flags.append(_flag)

    return flags


def _append_additional_args(flags: list[str], extra: str) -> None:
    raw = extra.strip()
    if not raw:
        return
    import shlex
    try:
        flags.extend(shlex.split(raw))
    except Exception:
        flags.append(raw)


def build_launch_args(cfg: AsmServerConfig) -> list[str]:
    """Monta a lista de argumentos de linha de comando fiel ao ASM GetServerArgs().

    SessionName vai ao GUS.ini (SessionSettings + ServerSettings, UTF-16 + aspas).
    Na travel URL entra ?SessionName= apenas para nomes simples (A-Za-z0-9_-).
    """
    params = _launch_url_params(cfg)
    flags = _launch_dash_flags(cfg)
    _append_additional_args(flags, cfg.additional_args)

    # O ARK usa o parser do Unreal Engine que lê o command line raw.
    # Aspas ao redor do MAP?params fazem o UE incluí-las no token, quebrando
    # o parsing de ?Port=, ?QueryPort=, ?AltSaveDirectoryName= etc.
    combined_map = "".join(params)
    return [combined_map] + flags
