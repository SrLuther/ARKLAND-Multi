"""
Categorias de configuração ASM — fonte única para import INI e presets.

Campos de identidade/rede (nome, portas, install_dir, cluster, etc.) nunca entram
nas categorias sincronizáveis.
"""
from __future__ import annotations

from typing import Dict, Iterator, List, Tuple

# Campos que NUNCA são copiados por preset ou import INI
ASM_EXCLUDED_FIELDS: frozenset[str] = frozenset({
    "id", "name", "install_dir", "server_exe", "user_config_folder",
    "server_port", "query_port", "rcon_port", "server_ip",
    "session_name",
    "branch_name", "branch_password",
    "cross_ark_cluster_id", "cluster_dir_override", "cluster_profile_id",
    "additional_args", "alt_save_directory_name", "server_map",
    "total_conversion_mod_id",
    "notes", "tags", "max_players",
})

# (slug interno, rótulo PT, campos)
_ASM_CATEGORY_SPECS: List[Tuple[str, str, List[str]]] = [
    ("senhas_mods", "Senhas e Mods", [
        "server_password", "admin_password", "spectator_password",
        "rcon_enabled", "rcon_log_buffer", "admin_logging",
        "active_mods", "auto_save_period",
        "kick_idle_players", "enable_kick_idle_players",
        "enable_ban_list_url", "ban_list_url",
        "motd", "motd_duration",
        "max_tribe_logs", "tribe_log_destroyed_enemy_structures",
        "allow_hide_damage_source",
    ]),
    ("regras", "Regras", [
        "enable_hardcore", "enable_pvp", "allow_cave_building_pve",
        "disable_friendly_fire_pvp", "disable_friendly_fire_pve",
        "disable_loot_crates", "enable_difficulty_override",
        "override_official_difficulty", "difficulty_offset",
        "max_tribe_size", "allow_pvp_gamma", "allow_pve_gamma",
        "allow_tribe_alliances", "allow_custom_recipes",
        "enable_diseases", "non_permanent_diseases",
        "prevent_pvp_offline", "prevent_pvp_offline_interval",
        "prevent_pvp_offline_invincible_interval",
        "auto_pve_timer", "auto_pve_use_system_time",
        "auto_pve_start_time", "auto_pve_stop_time",
        "allow_tribe_war_pve", "allow_tribe_war_cancel_pve",
        "enable_extra_structure_prevention_volumes",
        "oxygen_swim_speed_stat_multiplier",
        "supply_crate_loot_quality_multiplier",
        "fishing_loot_quality_multiplier",
        "use_corpse_life_span_multiplier",
        "global_powered_battery_durability_decrease",
        "tribe_name_change_cooldown", "random_supply_crate_points",
        "increase_pvp_respawn_interval", "pvp_respawn_check_period",
        "pvp_respawn_multiplier", "pvp_respawn_base_amount",
        "custom_recipe_effectiveness_multiplier",
        "custom_recipe_skill_multiplier",
        "override_npc_stasis_range_scale",
        "npc_stasis_range_scale_start", "npc_stasis_range_scale_end",
        "npc_stasis_range_scale_percent_end",
        "use_corpse_locator", "prevent_spawn_animations",
        "allow_unlimited_respecs",
        "max_alliances_per_tribe", "max_tribes_per_alliance",
    ]),
    ("transferencias_tributo", "Transferências / Tributo", [
        "enable_tribute_downloads",
        "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
        "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
        "cross_ark_allow_foreign_dino_downloads",
        "save_tribute_char_expiration", "tribute_char_expiration_seconds",
        "save_tribute_item_expiration", "tribute_item_expiration_seconds",
        "save_tribute_dino_expiration", "tribute_dino_expiration_seconds",
        "save_min_dino_reupload_interval", "min_dino_reupload_interval",
    ]),
    ("chat_notificacoes", "Chat e Notificações", [
        "global_voice_chat", "proximity_chat",
        "player_leave_notifications", "player_joined_notifications",
    ]),
    ("hud_visuais", "HUD e Visuais", [
        "allow_crosshair", "allow_hud", "allow_third_person_view",
        "show_map_player_location", "show_floating_damage_text", "allow_hit_markers",
    ]),
    ("jogadores", "Jogadores", [
        "xp_multiplier", "player_damage_multiplier", "player_resistance_multiplier",
        "player_water_drain_multiplier", "player_food_drain_multiplier",
        "player_stamina_drain_multiplier", "player_health_recovery_multiplier",
        "player_harvesting_damage_multiplier", "crafting_skill_bonus_multiplier",
        "enable_flyer_carry", "override_max_xp_player", "player_engram_points_multiplier",
    ]),
    ("dinos", "Dinos", [
        "dino_damage_multiplier", "tamed_dino_damage_multiplier",
        "dino_resistance_multiplier", "tamed_dino_resistance_multiplier",
        "max_tamed_dinos", "dino_count_multiplier", "taming_speed_multiplier",
        "disable_imprint_buff", "allow_anyone_baby_imprint",
        "disable_dino_riding", "disable_dino_taming", "allow_flyer_speed_leveling",
        "passive_tame_interval_multiplier", "dino_harvesting_damage_multiplier",
        "disable_dino_decay_pve", "pvp_dino_decay",
        "dino_char_food_drain_multiplier", "dino_char_stamina_drain_multiplier",
        "dino_char_health_recovery_multiplier",
        "allow_raid_dino_feeding", "raid_dino_food_drain_multiplier",
        "allow_flying_stamina_recovery", "prevent_mate_boost",
        "auto_destroy_decayed_dinos", "pve_dino_decay_period_multiplier",
        "allow_multiple_attached_c4", "max_personal_tamed_dinos",
        "personal_tamed_dinos_saddle_structure_cost",
        "use_tame_limit_for_structures_only",
        "wild_dino_char_food_drain_multiplier", "tamed_dino_char_food_drain_multiplier",
        "wild_dino_torpor_drain_multiplier", "tamed_dino_torpor_drain_multiplier",
        "override_max_xp_dino", "dino_turret_damage_multiplier",
    ]),
    ("reproducao", "Reprodução", [
        "mating_interval_multiplier", "egg_hatch_speed_multiplier",
        "baby_mature_speed_multiplier", "baby_food_consumption_multiplier",
        "baby_cuddle_interval_multiplier", "baby_imprinting_stat_scale",
        "baby_cuddle_grace_period_multiplier",
        "baby_cuddle_lose_imprint_quality_speed_multiplier",
    ]),
    ("meio_ambiente", "Meio Ambiente", [
        "harvest_amount_multiplier", "harvest_health_multiplier",
        "resources_respawn_multiplier",
        "day_cycle_speed_scale", "day_time_speed_scale", "night_time_speed_scale",
        "global_spoiling_time_multiplier",
        "global_item_decomposition_multiplier",
        "global_corpse_decomposition_multiplier",
        "crop_decay_speed_multiplier", "crop_growth_speed_multiplier",
        "hair_growth_speed_multiplier", "base_temperature_multiplier",
        "disable_weather_fog",
        "craft_xp_multiplier", "generic_xp_multiplier",
        "harvest_xp_multiplier", "kill_xp_multiplier", "special_xp_multiplier",
        "lay_egg_interval_multiplier", "poop_interval_multiplier",
        "resource_no_replenish_radius_players",
        "resource_no_replenish_radius_structures",
        "use_optimized_harvesting_health",
        "clamp_resource_harvest_damage", "clamp_item_spoiling_times",
    ]),
    ("estruturas", "Estruturas", [
        "override_structure_platform_prevention",
        "per_platform_max_structures_multiplier",
        "max_platform_saddle_structures",
        "platform_saddle_build_area_bounds_multiplier",
        "allow_platform_saddle_multi_floors",
        "flyer_platform_allow_unaligned_dino_basing",
        "structure_resistance_multiplier", "structure_damage_multiplier",
        "max_structures_in_range",
        "enable_structure_decay_pve", "pve_structure_decay_period_multiplier",
        "pve_structure_decay_destruction_period",
        "auto_destroy_old_structures_multiplier", "force_all_structure_locking",
        "disable_structure_placement_collision",
        "limit_turrets_in_range", "limit_turrets_range", "limit_turrets_num",
        "hard_limit_turrets_in_range",
        "pvp_structure_decay", "pvp_zone_structure_damage_multiplier",
        "structure_damage_repair_cooldown",
        "always_allow_structure_pickup",
        "pve_allow_structures_at_supply_drops",
        "only_auto_destroy_core_structures", "only_decay_unsnapped_core_structures",
        "fast_decay_unsnapped_core_structures", "destroy_unconnected_water_pipes",
        "enable_fast_decay_interval", "fast_decay_interval",
        "passive_defenses_damage_riderless_dinos",
    ]),
    ("extincao_wilds", "Extinção e Wilds", [
        "enable_extinction_event", "extinction_event_interval", "extinction_event_utc",
        "enable_auto_respawn_wild_dinos", "auto_respawn_wild_dinos_interval",
    ]),
    ("engramas", "Engramas", [
        "only_allow_specified_engrams", "auto_unlock_all_engrams",
        "engram_entries_raw",
    ]),
    ("progressoes_nivel", "Progressões de Nível", [
        "per_level_player", "per_level_dino_wild", "per_level_dino_tamed",
        "per_level_dino_tamed_add", "per_level_dino_tamed_affinity",
        "player_level_stats_raw", "dino_level_stats_raw",
    ]),
    ("subs_crafting", "Subs. de Crafting", ["crafting_overrides_raw"]),
    ("subs_stack", "Subs. de Stack", ["stack_size_overrides_raw"]),
    ("subs_spawner", "Subs. de Spawner", ["npc_spawn_overrides_raw"]),
    ("supply_crates", "Supply Crates", ["supply_crate_overrides_raw"]),
    ("impedir_transferencias", "Impedir Transferências", ["prevent_transfer_raw"]),
    ("custom_gus_ini", "Custom GUS INI", ["custom_gus_ini_raw", "custom_ini_sections"]),
    ("custom_game_ini", "Custom Game.ini", ["custom_game_ini_raw"]),
    ("custom_engine_ini", "Custom Engine.ini", ["custom_engine_ini_raw"]),
    ("pgm", "PGM", ["pgm_enabled", "pgm_name", "pgm_terrain_string"]),
]

# Slugs legados (presets antigos) → slug canônico
PRESET_CATEGORY_ALIASES: Dict[str, str] = {
    "players": "jogadores",
    "breeding": "reproducao",
    "environment": "meio_ambiente",
    "structures": "estruturas",
    "rules": "regras",
}

PRESET_CATEGORY_LABELS: Dict[str, str] = {
    slug: label for slug, label, _ in _ASM_CATEGORY_SPECS
}
for old, new in PRESET_CATEGORY_ALIASES.items():
    if new in PRESET_CATEGORY_LABELS:
        PRESET_CATEGORY_LABELS[old] = PRESET_CATEGORY_LABELS[new]


def _filter_fields(field_names: List[str]) -> List[str]:
    return [f for f in field_names if f not in ASM_EXCLUDED_FIELDS]


def _build_preset_categories() -> Dict[str, List[str]]:
    cats: Dict[str, List[str]] = {}
    for slug, _, fields in _ASM_CATEGORY_SPECS:
        cats[slug] = _filter_fields(fields)
    cats["full"] = list({f for fl in cats.values() for f in fl})
    return cats


PRESET_CATEGORIES: Dict[str, List[str]] = _build_preset_categories()


def resolve_preset_category(cat_id: str) -> str:
    return PRESET_CATEGORY_ALIASES.get(cat_id, cat_id)


def get_preset_category_fields(cat_id: str) -> List[str]:
    resolved = resolve_preset_category(cat_id)
    fields = PRESET_CATEGORIES.get(resolved)
    if fields is not None:
        return fields
    if cat_id not in PRESET_CATEGORY_ALIASES and cat_id not in PRESET_CATEGORIES:
        return [cat_id]
    return []


def iter_preset_categories() -> Iterator[Tuple[str, str]]:
    """(slug, rótulo PT) — para UI de presets."""
    for slug, label, _ in _ASM_CATEGORY_SPECS:
        yield slug, label


def iter_import_categories() -> Iterator[Tuple[str, List[str]]]:
    """(rótulo PT, campos) — para diálogo de import INI."""
    for _, label, fields in _ASM_CATEGORY_SPECS:
        yield label, _filter_fields(fields)
