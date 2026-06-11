#!/usr/bin/env python3
"""Verifica cobertura do catálogo server_field_labels vs AsmServerConfig."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataclasses import fields as dc_fields  # noqa: E402

from src.asm_engine.asm_server_config import AsmServerConfig  # noqa: E402
from src.asm_engine.asm_ini_manager import INI_MAP  # noqa: E402
from src.ui.server_field_labels import FIELD_LABELS, missing_pt_translations  # noqa: E402


def main() -> int:
    cfg_fields = {f.name for f in dc_fields(AsmServerConfig)}
    label_fields = set(FIELD_LABELS.keys())

    missing_in_catalog = sorted(cfg_fields - label_fields)
    extra_in_catalog = sorted(label_fields - cfg_fields)
    ini_not_in_cfg = sorted(set(INI_MAP.keys()) - cfg_fields)
    cfg_not_in_ini = sorted(
        f for f in cfg_fields
        if f not in INI_MAP
        and not f.endswith("_raw")
        and f not in (
            "id", "name", "install_dir", "server_exe", "server_ip", "active_mods",
            "server_map", "total_conversion_mod_id", "alt_save_directory_name",
            "branch_name", "branch_password", "cross_ark_cluster_id", "cluster_dir_override",
            "additional_args", "admin_ids", "whitelist_ids", "exclusive_join_ids",
            "per_level_player", "per_level_dino_wild", "per_level_dino_tamed",
            "per_level_dino_tamed_add", "per_level_dino_tamed_affinity",
            "custom_ini_sections", "notes", "color", "tags", "folder",
            "shop_server_id", "customshop_config_path",
            "cpu_affinity_cores", "process_priority",
            "enable_auto_restart", "auto_restart_time", "restart_countdown_minutes",
            "enable_auto_update_check", "auto_update_check_minutes", "notify_discord_on_events",
            "discord_webhook_url", "discord_notify_server_start", "discord_notify_server_stop",
            "discord_notify_player_join", "discord_notify_player_leave",
            "pgm_enabled", "exclusive_join", "enable_kick_idle_players",
            "enable_ban_list_url", "ban_list_url", "kick_idle_players",
            "disable_loot_crates_extra", "allow_cave_flyers", "allow_pve_gamma",
            "save_tribute_char_expiration", "save_tribute_item_expiration",
            "save_tribute_dino_expiration", "save_min_dino_reupload_interval",
            "enable_fast_decay_interval",
            "use_battleye", "force_respawn_dinos", "use_allcores", "active_event",
            "crossplay", "epic_only", "use_vivox", "use_item_dupe_check",
            "use_raw_sockets", "no_net_threading", "force_net_threading",
            "public_ip_for_epic", "no_transfer_from_filtering",
            "disable_vac", "disable_anti_speed_hack", "speed_hack_bias",
            "disable_player_move_physics_opt", "use_cache", "use_old_save_format",
            "use_no_memory_bias", "stasis_keep_controllers", "use_no_hang_detection",
            "server_allow_ansel", "no_dinos", "force_dx10", "force_shader_model4",
            "force_low_memory", "enable_auto_destroy_structures", "enable_no_fish_loot",
            "enable_web_alarm", "web_alarm_key", "web_alarm_url",
            "enable_server_admin_logs", "server_admin_logs_include_tribe_logs",
            "server_rcon_output_tribe_logs", "notify_admin_commands_in_chat",
            "harvest_resource_multipliers", "dino_class_resistance_multipliers",
            "dino_class_damage_multipliers", "tamed_dino_class_resistance_multipliers",
            "tamed_dino_class_damage_multipliers", "dino_spawn_weight_multipliers",
            "prevent_dino_tame_class_names",
        )
    )

    no_pt = missing_pt_translations()

    print("=== check_field_labels ===")
    print(f"AsmServerConfig fields: {len(cfg_fields)}")
    print(f"FIELD_LABELS entries:   {len(label_fields)}")
    print()

    ok = True
    if missing_in_catalog:
        ok = False
        print(f"MISSING in catalog ({len(missing_in_catalog)}):")
        for k in missing_in_catalog:
            print(f"  - {k}")
        print()

    if extra_in_catalog:
        print(f"Extra in catalog ({len(extra_in_catalog)}):")
        for k in extra_in_catalog:
            print(f"  - {k}")
        print()

    if ini_not_in_cfg:
        print(f"INI_MAP keys not in AsmServerConfig ({len(ini_not_in_cfg)}):")
        for k in ini_not_in_cfg[:20]:
            print(f"  - {k}")
        if len(ini_not_in_cfg) > 20:
            print(f"  ... +{len(ini_not_in_cfg) - 20} more")
        print()

    print(f"Fields without PT override ({len(no_pt)}) — target 0 after Fase 2")
    if no_pt:
        for k in no_pt[:30]:
            print(f"  - {k}")
        if len(no_pt) > 30:
            print(f"  ... +{len(no_pt) - 30} more")
    print()

    if ok and not missing_in_catalog:
        print("Catalog coverage: OK (all AsmServerConfig fields present)")
    else:
        print("Catalog coverage: INCOMPLETE")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
