"""One-off audit: AsmServerConfig vs TEK UI exposure."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import fields

from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_engine.asm_ini_manager import INI_MAP
from src.ui.tek_section_fields import SECTION_FIELDS
from src.ui.server_field_labels import FIELD_LABELS
from src.asm_ui.asm_server_panel import SECTIONS

config_fields = {f.name for f in fields(AsmServerConfig)}
ini_fields = set(INI_MAP.keys())

field_to_sections: dict[str, list[str]] = defaultdict(list)
for sec, flist in SECTION_FIELDS.items():
    for f in flist:
        field_to_sections[f].append(sec)
section_fields = set(field_to_sections)
duplicates = {k: v for k, v in field_to_sections.items() if len(v) > 1}

INTERNAL = {
    "id", "cluster_profile_id", "disable_loot_crates_extra", "custom_ini_sections",
    "shop_server_id", "cross_chat_label", "customshop_config_path",
    "shop_show_on_home", "shop_exclude",
}
RAW_EDITORS = {
    "engram_entries_raw", "player_level_stats_raw", "dino_level_stats_raw",
    "crafting_overrides_raw", "stack_size_overrides_raw", "npc_spawn_overrides_raw",
    "supply_crate_overrides_raw", "prevent_transfer_raw",
    "custom_gus_ini_raw", "custom_game_ini_raw", "custom_engine_ini_raw",
    "per_level_player", "per_level_dino_wild", "per_level_dino_tamed",
    "per_level_dino_tamed_add", "per_level_dino_tamed_affinity",
    "admin_ids", "whitelist_ids", "exclusive_join_ids",
    "harvest_resource_multipliers", "dino_class_resistance_multipliers",
    "dino_class_damage_multipliers", "tamed_dino_class_resistance_multipliers",
    "tamed_dino_class_damage_multipliers", "dino_spawn_weight_multipliers",
    "prevent_dino_tame_class_names",
}
SKIP = INTERNAL | RAW_EDITORS

catalog = FIELD_LABELS
missing_labels = sorted(k for k in config_fields if k not in catalog and k not in INTERNAL)
weak_labels = sorted(
    k for k, m in catalog.items()
    if k in config_fields and k not in INTERNAL
    and (m.pt == k or m.pt == m.en)
)
not_in_sections = sorted(config_fields - section_fields - SKIP)
in_ini_not_sections = sorted(ini_fields - section_fields - SKIP)
in_sections_not_config = sorted(section_fields - config_fields)
panel_only = [s for s in SECTIONS if s not in SECTION_FIELDS]
sections_only_in_map = [s for s in SECTION_FIELDS if s not in SECTIONS]

print("=== STATS ===")
print(f"Config fields: {len(config_fields)}")
print(f"INI_MAP fields: {len(ini_fields)}")
print(f"SECTION_FIELDS unique: {len(section_fields)}")
print(f"Duplicates: {len(duplicates)}")
print(f"Not in SECTION_FIELDS (excl internal/raw): {len(not_in_sections)}")
print(f"INI not in sections: {len(in_ini_not_sections)}")
print(f"Missing from catalog: {len(missing_labels)}")
print(f"Panel sections without SECTION_FIELDS entry: {len(panel_only)}")
print(f"SECTION_FIELDS keys not in panel SECTIONS: {len(sections_only_in_map)}")
print()
print("=== DUPLICATES ===")
for k, v in sorted(duplicates.items()):
    print(f"  {k}: {v}")
print()
print("=== NOT IN SECTION_FIELDS ===")
for f in not_in_sections:
    print(f"  {f}")
print()
print("=== INI NOT IN SECTIONS ===")
for f in in_ini_not_sections:
    print(f"  {f}")
print()
print("=== PANEL SECTIONS WITHOUT SECTION_FIELDS ===")
for s in panel_only:
    print(f"  {s}")
print()
print("=== MISSING LABELS ===")
for f in missing_labels:
    print(f"  {f}")
