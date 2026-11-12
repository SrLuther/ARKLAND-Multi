"""Read-only inventory and migration preview for classic/TEK server profiles.

This module deliberately uses only the Python standard library and parses the
dataclass source as text. It does not import or instantiate application managers.
"""
from __future__ import annotations

import argparse
import ast
import json
import ntpath
import os
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_FILES = {
    "classic": ("src/server_config.py", ("ServerConfig", "ServerGameSettings", "ServerAdvancedSettings", "ClusterConfig")),
    "tek": ("src/asm_engine/asm_server_config.py", ("AsmServerConfig",)),
}
NESTED_SOURCE_MODELS = {
    "ServerGameSettings": "game_settings",
    "ServerAdvancedSettings": "advanced_settings",
    "ClusterConfig": "cluster",
}
DESTINATION_TYPE_OVERRIDES = {
    "ConfigManager.config.backup.auto_backup": "bool",
    "ConfigManager.config.backup.backup_interval": "str",
    "ConfigManager.config.backup.max_backup_count": "int",
    "ConfigManager.config.backup.include_savegames": "bool",
    "ConfigManager.config.backup.include_config": "bool",
    "ConfigManager.config.backup.backup_exclude_redundant": "bool",
    "ConfigManager.config.backup.backup_dir": "str",
    "cpu_affinity_cores": "List[int]",
    "exclusive_join + whitelist_ids": "bool + List[str]",
    "custom_ini_sections/custom_*_ini_raw": "List[dict] / str",
    "ClusterProfile + AsmServerConfig": "ClusterProfile + TEK scalar fields",
    "<flattened AsmServerConfig fields>": "multiple typed fields",
    "<review child fields>": "multiple typed fields",
}

# These are candidates found by comparing the current model declarations and
# the audited call paths. Non-trivial semantic mappings remain review-only.
ALIASES: dict[str, tuple[str, str, str]] = {
    "map": ("server_map", "equivalence_with_transform", "Verify canonical map-name representation."),
    "server_name": ("session_name", "partial_equivalence", "Classic session name maps to TEK session_name; keep profile name separate."),
    "mods": ("active_mods", "equivalence_with_transform", "Normalize Workshop IDs to strings and preserve order/duplicates policy."),
    "extra_args": ("additional_args", "equivalence_with_transform", "Tokenize and validate command-line arguments without changing meaning."),
    "rcon_server_game_log_buffer": ("rcon_log_buffer", "equivalence_with_transform", "Same intended RCON buffer; validate units/range."),
    "rcon_password": ("admin_password", "partial_equivalence", "TEK RCON bridge falls back to admin_password; confirm credential semantics before transfer."),
    "whitelist_only": ("exclusive_join", "partial_equivalence", "Classic bool may need TEK exclusive_join plus whitelist_ids; validate enforcement semantics."),
    "cpu_core_count": ("cpu_affinity_cores", "equivalence_with_transform", "0/-1/N must be converted to a concrete core list or retained as an explicit mode."),
    "game_settings": ("<flattened AsmServerConfig fields>", "partial_equivalence", "Expand nested ServerGameSettings into TEK flat fields; resolve every child separately."),
    "advanced_settings": ("<flattened AsmServerConfig fields>", "partial_equivalence", "Expand nested ServerAdvancedSettings into TEK flat fields; resolve every child separately."),
    "cluster": ("ClusterProfile + AsmServerConfig", "partial_equivalence", "Separate per-server ClusterConfig from shared ClusterProfile and TEK linkage fields."),
    "cluster.enabled": ("cluster_profile_id/cross_ark_cluster_id", "partial_equivalence", "TEK models cluster linkage/profile rather than this nested enable flag."),
    "cluster.cluster_id": ("cross_ark_cluster_id/ClusterProfile.cluster_id", "partial_equivalence", "Resolve whether this value is a local ID or shared profile ID."),
    "custom_ini_sections": ("custom_ini_sections/custom_*_ini_raw", "partial_equivalence", "Convert section/entry structure without losing repeats, raw text, or ownership."),
    "dynamic_config_enabled": (None, "no_equivalent", "No equivalent TEK profile/runtime field identified in the prior audit."),
    "battlemetrics_id": (None, "no_equivalent", "TEK _on_bm_update is a no-op; parity is not implemented."),
    "mod_ini_configs": (None, "no_equivalent", "TEK has raw custom INI and managed options, but no per-mod ownership model confirmed."),
    "admin_names": (None, "no_equivalent", "TEK has admin IDs but no equivalent cached display-name mapping confirmed."),
    "public_ip": (None, "no_equivalent", "No equivalent public endpoint field identified; do not conflate with bind/server_ip."),
    "scheduled_tasks": (None, "no_equivalent", "Classic task list supports actions beyond confirmed TEK scheduler fields."),
    "auto_broadcasts": (None, "no_equivalent", "TEK per-profile scheduled broadcast fields were not found in AsmServerConfig."),
    "broadcasts": (None, "no_equivalent", "No equivalent per-profile broadcast library confirmed."),
    "auto_restart_on_crash": (None, "no_equivalent", "Crash restart is not equivalent to TEK scheduled auto-restart."),
    "backup_enabled": ("ConfigManager.config.backup.auto_backup", "partial_equivalence", "Current TEK backup setting is global, not per server."),
    "backup_interval_hours": ("ConfigManager.config.backup.backup_interval", "equivalence_with_transform", "Convert integer hours to TEK HH:MM; per-server scope still needs a decision."),
    "backup_keep_count": ("ConfigManager.config.backup.max_backup_count", "partial_equivalence", "TEK retention is global; classic retention is per server."),
    "backup_include_saves": ("ConfigManager.config.backup.include_savegames", "partial_equivalence", "Current TEK setting is global, not per server."),
    "backup_include_config": ("ConfigManager.config.backup.include_config", "partial_equivalence", "Current TEK setting is global, not per server."),
    "backup_exclude_redundant": ("ConfigManager.config.backup.backup_exclude_redundant", "partial_equivalence", "Current TEK setting is global, not per server."),
    "backup_dir": ("ConfigManager.config.backup.backup_dir", "partial_equivalence", "Current TEK backup root is global; per-server override needs a decision."),
    "enable_auto_force_respawn_wild_dinos_interval": ("enable_auto_respawn_wild_dinos", "equivalence_with_transform", "TEK combines the enable toggle with a renamed interval field."),
    "server_auto_force_respawn_wild_dinos_interval": ("auto_respawn_wild_dinos_interval", "equivalence_with_transform", "Validate seconds and enable-toggle behavior."),
    "enable_allow_cave_flyers": ("allow_cave_flyers", "equivalence_with_transform", "TEK field omits the enable_ prefix."),
    "allow_hide_damage_source_from_logs": ("allow_hide_damage_source", "equivalence_with_transform", "TEK field omits the from_logs suffix."),
    "extinction_event_time_interval": ("extinction_event_interval", "equivalence_with_transform", "Validate interval units and enable toggle."),
    "tribute_character_expiration_seconds": ("tribute_char_expiration_seconds", "equivalence_with_transform", "TEK also has a separate save/enable toggle."),
    "tribute_item_expiration_seconds": ("tribute_item_expiration_seconds", "equivalence_with_transform", "TEK also has a separate save/enable toggle."),
    "tribute_dino_expiration_seconds": ("tribute_dino_expiration_seconds", "equivalence_with_transform", "TEK also has a separate save/enable toggle."),
    "minimum_dino_reupload_interval": ("min_dino_reupload_interval", "equivalence_with_transform", "TEK also has a separate save/enable toggle."),
    "server_pvp": ("enable_pvp", "equivalence_with_transform", "Confirm boolean meaning and normalize to TEK enable flag."),
    "server_hardcore": ("enable_hardcore", "equivalence_with_transform", "TEK field uses enable_ prefix."),
    "no_tribute_downloads": ("enable_tribute_downloads", "equivalence_with_transform", "Boolean polarity is inverted."),
    "player_character_water_drain_multiplier": ("player_water_drain_multiplier", "equivalence_with_transform", "TEK field omits character_ segment."),
    "player_character_food_drain_multiplier": ("player_food_drain_multiplier", "equivalence_with_transform", "TEK field omits character_ segment."),
    "player_character_stamina_drain_multiplier": ("player_stamina_drain_multiplier", "equivalence_with_transform", "TEK field omits character_ segment."),
    "player_character_health_recovery_multiplier": ("player_health_recovery_multiplier", "equivalence_with_transform", "TEK field omits character_ segment."),
    "max_fall_speed_multiplier": ("player_max_fall_speed_multiplier", "equivalence_with_transform", "TEK field adds player_ prefix."),
    "override_max_experience_points_player": ("override_max_xp_player", "equivalence_with_transform", "TEK field abbreviates experience points."),
    "override_max_experience_points_dino": ("override_max_xp_dino", "equivalence_with_transform", "TEK field abbreviates experience points."),
    "prevent_offline_pvp": ("prevent_pvp_offline", "equivalence_with_transform", "TEK field reorders the name."),
    "prevent_offline_pvp_interval": ("prevent_pvp_offline_interval", "equivalence_with_transform", "TEK field reorders the name; validate units."),
    "no_transfer_from_filtering": ("no_transfer_from_filtering", "candidate_requires_review", "Same name; validate behavior and cluster ownership."),
    "motd_duration": ("motd_duration", "candidate_requires_review", "Same name/type but model defaults differ (60 vs 20)."),
    "auto_update_on_start": ("enable_auto_update_check", "partial_equivalence", "Update-on-start differs from periodic update checking."),
    "allow_anyone_baby_imprint_cuddle": ("allow_anyone_baby_imprint", "equivalence_with_transform", "TEK field shortens the name."),
    "allow_flyer_carry_pve": ("enable_flyer_carry", "equivalence_with_transform", "TEK field includes an enable flag; verify PvE scope."),
    "allow_third_person_player": ("allow_third_person_view", "equivalence_with_transform", "TEK field renames player to view."),
    "always_notify_player_joined": ("player_joined_notifications", "equivalence_with_transform", "TEK field renames the notification setting."),
    "always_notify_player_left": ("player_leave_notifications", "equivalence_with_transform", "TEK field renames the notification setting."),
    "baby_food_consumption_speed_multiplier": ("baby_food_consumption_multiplier", "equivalence_with_transform", "TEK field shortens the name."),
    "baby_imprinting_stat_scale_multiplier": ("baby_imprinting_stat_scale", "equivalence_with_transform", "TEK field shortens the name."),
    "dino_character_food_drain_multiplier": ("dino_char_food_drain_multiplier", "equivalence_with_transform", "TEK field abbreviates character."),
    "dino_character_health_recovery_multiplier": ("dino_char_health_recovery_multiplier", "equivalence_with_transform", "TEK field abbreviates character."),
    "dino_character_stamina_drain_multiplier": ("dino_char_stamina_drain_multiplier", "equivalence_with_transform", "TEK field abbreviates character."),
    "disable_dino_decay_pvp": ("pvp_dino_decay", "equivalence_with_transform", "Boolean polarity/name differs; verify exact behavior."),
    "disable_imprint_dino_buff": ("disable_imprint_buff", "equivalence_with_transform", "TEK field shortens the name."),
    "disable_structure_decay_pve": ("enable_structure_decay_pve", "equivalence_with_transform", "Boolean polarity is inverted."),
    "dont_always_notify_player_joined": ("player_joined_notifications", "partial_equivalence", "Inverted/legacy notification behavior conflicts with always_notify_player_joined."),
    "kick_idle_players_period": ("enable_kick_idle_players + kick_idle_players", "partial_equivalence", "TEK splits enable state from timeout value."),
    "max_platform_saddle_structure_limit": ("max_platform_saddle_structures", "equivalence_with_transform", "TEK field shortens the name."),
    "max_structures_visible": ("max_structures_in_range", "equivalence_with_transform", "TEK field renames the limit; verify scope."),
    "npc_network_stasis_range_scale_percent_end": ("npc_stasis_range_scale_percent_end", "equivalence_with_transform", "TEK field shortens the name."),
    "npc_network_stasis_range_scale_player_count_end": ("npc_stasis_range_scale_end", "equivalence_with_transform", "TEK field shortens the name."),
    "npc_network_stasis_range_scale_player_count_start": ("npc_stasis_range_scale_start", "equivalence_with_transform", "TEK field shortens the name."),
    "override_npc_network_stasis_range_scale": ("override_npc_stasis_range_scale", "equivalence_with_transform", "TEK field shortens the name."),
    "per_level_stats_mult_player": ("per_level_player", "equivalence_with_transform", "TEK field shortens the name; validate array length/order."),
    "per_level_stats_mult_dino_wild": ("per_level_dino_wild", "equivalence_with_transform", "TEK field shortens the name; validate array length/order."),
    "per_level_stats_mult_dino_tamed": ("per_level_dino_tamed", "equivalence_with_transform", "TEK field shortens the name; validate array length/order."),
    "per_level_stats_mult_dino_tamed_add": ("per_level_dino_tamed_add", "equivalence_with_transform", "TEK field shortens the name; validate array length/order."),
    "per_level_stats_mult_dino_tamed_affinity": ("per_level_dino_tamed_affinity", "equivalence_with_transform", "TEK field shortens the name; validate array length/order."),
    "player_level_cap": ("player_level_cap_schema_version/player_level_xp_thresholds", "partial_equivalence", "TEK stores the cap as a versioned ramp; derive and validate the full level table."),
    "dino_level_cap": (None, "no_equivalent", "No TEK per-profile dino level cap field was identified."),
    "resource_respawn_period_multiplier": ("resources_respawn_multiplier", "equivalence_with_transform", "TEK field pluralizes resources."),
    "b_auto_pve_timer": ("auto_pve_timer", "equivalence_with_transform", "TEK field omits the b_ prefix."),
    "b_auto_pve_use_system_time": ("auto_pve_use_system_time", "equivalence_with_transform", "TEK field omits the b_ prefix."),
    "auto_pve_start_time_seconds": ("auto_pve_start_time", "equivalence_with_transform", "Convert seconds only after confirming TEK units."),
    "auto_pve_stop_time_seconds": ("auto_pve_stop_time", "equivalence_with_transform", "Convert seconds only after confirming TEK units."),
    "b_passive_defenses_damage_riderless_dinos": ("passive_defenses_damage_riderless_dinos", "equivalence_with_transform", "TEK field omits the b_ prefix."),
    "increase_pvp_respawn_interval_base_amount": ("pvp_respawn_base_amount", "equivalence_with_transform", "TEK field shortens the name."),
    "increase_pvp_respawn_interval_check_period": ("pvp_respawn_check_period", "equivalence_with_transform", "TEK field shortens the name; verify units."),
    "increase_pvp_respawn_interval_multiplier": ("pvp_respawn_multiplier", "equivalence_with_transform", "TEK field shortens the name."),
    "npc_spawn_entries_add": ("npc_spawn_overrides_raw", "partial_equivalence", "Convert structured entries to raw TEK form while preserving order and weights."),
    "npc_spawn_entries_override": ("npc_spawn_overrides_raw", "partial_equivalence", "Convert structured entries to raw TEK form while preserving order and weights."),
    "override_player_level_engram_points": ("player_engram_points", "equivalence_with_transform", "Validate level indexing and array length."),
    "prevent_offline_pvp_connection_invincible_interval": ("prevent_pvp_offline_invincible_interval", "equivalence_with_transform", "TEK field reorders the name; validate units."),
    "raid_dino_character_food_drain_multiplier": ("raid_dino_food_drain_multiplier", "equivalence_with_transform", "TEK field shortens the name."),
    "supply_crate_overrides": ("supply_crate_overrides_raw", "partial_equivalence", "Convert structured overrides to raw form without losing duplicate entries."),
    "tamed_dino_character_food_drain_multiplier": ("tamed_dino_char_food_drain_multiplier", "equivalence_with_transform", "TEK field abbreviates character."),
    "wild_dino_character_food_drain_multiplier": ("wild_dino_char_food_drain_multiplier", "equivalence_with_transform", "TEK field abbreviates character."),
    "baby_hatch_speed_multiplier": (None, "no_equivalent", "No distinct TEK baby-hatch field was identified; do not conflate with egg_hatch_speed_multiplier."),
    "global_corpse_decomposition_time_multiplier": ("global_corpse_decomposition_multiplier", "equivalence_with_transform", "TEK field shortens the name."),
    "global_powered_battery_durability_decrease_per_second": ("global_powered_battery_durability_decrease", "equivalence_with_transform", "TEK field shortens the name; confirm unit semantics."),
}

DIRECT_VALIDATED = {
    # Only mappings supported by audited role/type evidence are marked validated.
    # All other same-name fields remain candidates requiring semantic review.
    "id", "name", "install_dir", "server_exe", "server_port", "query_port",
    "rcon_port", "rcon_enabled", "max_players", "auto_start_on_launch",
}

DEPENDENCY_OVERRIDES = {
    "whitelist_only": ["exclusive_join", "whitelist_ids"],
    "backup_enabled": ["backup_interval_hours", "backup_dir", "global BackupConfig scope"],
    "backup_interval_hours": ["backup_enabled", "global interval format HH:MM"],
    "backup_keep_count": ["global BackupConfig retention limit"],
    "backup_include_saves": ["global BackupConfig scope"],
    "backup_include_config": ["global BackupConfig scope", "INI backup policy"],
    "scheduled_tasks": ["TEK auto_restart_time/days", "TEK update-check interval", "broadcast schedule"],
    "auto_broadcasts": ["RCON configuration", "scheduled broadcast model absent from AsmServerConfig"],
    "cluster": ["ClusterProfile", "cluster_profile_id", "cluster directory/path validation"],
    "mod_ini_configs": ["mod identity", "INI ownership manifest", "external mod sections"],
    "rcon_password": ["TEK RCON bridge admin_password fallback", "credential preservation"],
    "cpu_core_count": ["host CPU topology", "cpu_affinity_cores"],
    "map": ["map alias normalization", "server save name"],
    "custom_ini_sections": ["Game.ini/GUS/Engine targets", "managed_ini_options ownership"],
    "player_level_cap": ["player_level_xp_thresholds", "player ramp", "engram points"],
    "override_player_level_engram_points": ["player_engram_points", "level indexing"],
    "npc_spawn_entries_add": ["npc_spawn_overrides_raw", "spawn editor serialization"],
    "npc_spawn_entries_override": ["npc_spawn_overrides_raw", "spawn editor serialization"],
    "supply_crate_overrides": ["supply_crate_overrides_raw", "duplicate override handling"],
}

SENSITIVE_RE = re.compile(r"password|passwd|token|secret|webhook|api.?key|credential", re.I)
REQUIRED_FIELDS = ("id", "name", "install_dir")
NESTED_MODELS = {
    "game_settings": "ServerGameSettings",
    "advanced_settings": "ServerAdvancedSettings",
    "cluster": "ClusterConfig",
}


@dataclass(frozen=True)
class FieldSpec:
    path: str
    type_name: str
    default: Any
    purpose: str
    is_container: bool = False


class PreviewError(ValueError):
    """Input could not be safely interpreted as a profile repository."""


def _default_value(value: ast.AST | None) -> tuple[Any, bool]:
    """Return a JSON-safe literal default, without executing model code."""
    if value is None:
        return "<required>", False
    try:
        return ast.literal_eval(value), True
    except (ValueError, TypeError):
        pass
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "field":
        keywords = {kw.arg: kw.value for kw in value.keywords if kw.arg}
        if "default" in keywords:
            return _default_value(keywords["default"])
        factory = keywords.get("default_factory")
        if isinstance(factory, ast.Name) and factory.id in {"list", "dict", "set"}:
            return {"list": [], "dict": {}, "set": []}[factory.id], True
        if isinstance(factory, ast.Name):
            return f"<factory:{factory.id}>", False
        return "<factory>", False
    return "<dynamic>", False


def _comment_map(source: str) -> dict[int, str]:
    comments: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(iter(source.splitlines(keepends=True)).__next__):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string.lstrip("# ").strip()
    except (tokenize.TokenError, IndentationError):
        pass
    return comments


def _class_fields(source_path: Path, class_name: str) -> list[tuple[str, str, Any, str]]:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    comments = _comment_map(source)
    lines = source.splitlines()
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if node is None:
        raise PreviewError(f"Dataclass {class_name} not found in {source_path}")
    result: list[tuple[str, str, Any, str]] = []
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        typ = ast.unparse(stmt.annotation)
        default, _ = _default_value(stmt.value)
        purpose = comments.get(stmt.lineno, "")
        if not purpose and stmt.lineno > 1:
            # Keep only the immediately adjacent comment block, never section headings.
            gathered: list[str] = []
            cursor = stmt.lineno - 2
            while cursor >= 0 and lines[cursor].lstrip().startswith("#"):
                txt = lines[cursor].lstrip()[1:].strip()
                if txt:
                    gathered.append(txt)
                cursor -= 1
            if gathered and len(gathered) <= 3:
                purpose = " ".join(reversed(gathered))
        result.append((name, typ, default, purpose or "Sem comentário de finalidade junto à declaração; requer validação funcional."))
    return result


def build_field_matrix(repo_root: Path) -> list[dict[str, Any]]:
    classic_file = repo_root / SCHEMA_FILES["classic"][0]
    tek_file = repo_root / SCHEMA_FILES["tek"][0]
    classic: list[FieldSpec] = []
    tek_fields: dict[str, str] = {}
    for name, typ, default, purpose in _class_fields(tek_file, "AsmServerConfig"):
        tek_fields[name] = typ
    for class_name in SCHEMA_FILES["classic"][1]:
        for name, typ, default, purpose in _class_fields(classic_file, class_name):
            field_path = name if class_name == "ServerConfig" else f"{NESTED_SOURCE_MODELS[class_name]}.{name}"
            classic.append(FieldSpec(field_path, typ, default, purpose, name in NESTED_MODELS))

    matrix: list[dict[str, Any]] = []
    for spec in classic:
        leaf = spec.path.split(".")[-1]
        rule = ALIASES.get(spec.path, ALIASES.get(leaf))
        if rule:
            target, compatibility, rationale = rule
            target_type = DESTINATION_TYPE_OVERRIDES.get(target) or (tek_fields.get(target) if target and not target.startswith("<") else None)
            transform = rationale
        elif spec.is_container:
            target, target_type, compatibility = "<review child fields>", None, "partial_equivalence"
            transform = "Container is expanded to TEK fields; the container itself must not be copied as a scalar."
        elif leaf in tek_fields:
            target, target_type = leaf, tek_fields[leaf]
            if leaf in DIRECT_VALIDATED:
                compatibility, transform = "direct_equivalence_validated", "Identity mapping; field type is compatible."
            else:
                compatibility, transform = "candidate_requires_review", "Same field name is only a candidate; semantic parity is not inferred from the name."
        else:
            target, target_type, compatibility = None, None, "no_equivalent"
            transform = "No destination field identified; a non-default value blocks safe future migration."
        matrix.append({
            "source": spec.path,
            "source_type": spec.type_name,
            "source_default": spec.default,
            "purpose": spec.purpose,
            "destination": target,
            "destination_type": target_type,
            "compatibility": compatibility,
            "transformation": transform,
            "data_loss_risk": "none_for_default_value" if compatibility == "no_equivalent" else "review_before_migration",
            "dependencies": DEPENDENCY_OVERRIDES.get(spec.path, DEPENDENCY_OVERRIDES.get(leaf, ["not individually assessed; verify before migration"])),
            "migration_decision": "pending_review" if compatibility not in {"direct_equivalence_validated"} else "approved_mapping_only",
        })
    return sorted(matrix, key=lambda row: row["source"].casefold())


def _load_profiles(path: Path, repo_kind: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        payload = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreviewError(f"Cannot read {repo_kind} profile repository: {exc}") from exc
    if isinstance(payload, dict):
        payload = payload.get("servers", payload.get("profiles"))
    if not isinstance(payload, list):
        raise PreviewError(f"{repo_kind} repository must be a JSON array or contain a servers/profiles array")
    profiles: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(payload):
        if isinstance(item, dict):
            profiles.append(item)
        else:
            errors.append(f"{repo_kind}[{index}] is not an object")
    return profiles, errors


def _path_info(raw_value: Any) -> dict[str, Any]:
    raw = raw_value.strip() if isinstance(raw_value, str) else ""
    if not raw:
        return {"raw": "", "normalized": "", "absolute": False, "directory_state": "missing_value"}
    normalized = ntpath.normcase(ntpath.normpath(raw.replace("/", "\\")))
    absolute = ntpath.isabs(raw)
    if not absolute:
        state = "relative_unresolved"
    elif os.name != "nt" and ntpath.splitdrive(raw)[0]:
        state = "unverifiable_host_path"
    else:
        try:
            state = "directory_exists" if Path(raw).is_dir() else "directory_missing_or_inaccessible"
        except OSError:
            state = "directory_missing_or_inaccessible"
    return {"raw": raw, "normalized": normalized, "absolute": absolute, "directory_state": state}


def _same_installation(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not left["absolute"] or not right["absolute"]:
        return False
    if left["normalized"] == right["normalized"]:
        return True
    if left["directory_state"] == right["directory_state"] == "directory_exists":
        try:
            return Path(left["raw"]).samefile(Path(right["raw"]))
        except OSError:
            return False
    return False


def _get_field(profile: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = profile
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _matches_default(value: Any, default: Any) -> bool:
    return value == default


def _value_matches_type(value: Any, type_name: str) -> bool:
    primitives = {
        "str": lambda v: isinstance(v, str),
        "bool": lambda v: isinstance(v, bool),
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "dict": lambda v: isinstance(v, dict),
        "list": lambda v: isinstance(v, list),
    }
    if type_name in primitives:
        return primitives[type_name](value)
    match = re.fullmatch(r"(List|Dict)\[(.*)\]", type_name)
    if not match:
        return True
    container, arguments = match.groups()
    if container == "List":
        if not isinstance(value, list):
            return False
        item_type = arguments.strip()
        check = primitives.get(item_type)
        return all(check(item) for item in value) if check else True
    if not isinstance(value, dict):
        return False
    key_type, separator, value_type = arguments.partition(",")
    if not separator:
        return True
    key_check = primitives.get(key_type.strip())
    value_check = primitives.get(value_type.strip())
    return all((key_check(k) if key_check else True) and (value_check(v) if value_check else True) for k, v in value.items())


def _profile_fields(profile: dict[str, Any], matrix: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    changed: list[dict[str, Any]] = []
    sensitive: list[str] = []
    invalid: list[str] = []
    for container in NESTED_MODELS:
        if container in profile and not isinstance(profile[container], dict):
            invalid.append(container)
    for row in matrix:
        path = row["source"]
        if path in {"game_settings", "advanced_settings", "cluster"}:
            continue
        present, value = _get_field(profile, path)
        if not present:
            continue
        if not _value_matches_type(value, row["source_type"]):
            invalid.append(path)
        default = row["source_default"]
        if isinstance(default, str) and default.startswith("<"):
            is_changed = True
        else:
            is_changed = not _matches_default(value, default)
        if not is_changed:
            continue
        if SENSITIVE_RE.search(path):
            sensitive.append(path)
        changed.append({
            "field": path,
            "compatibility": row["compatibility"],
            "destination": row["destination"],
            "value_included": False,
        })
    return changed, sensitive, invalid


def _unknown_classic_fields(profile: dict[str, Any], matrix: list[dict[str, Any]]) -> list[str]:
    known_root = {row["source"].split(".")[0] for row in matrix if "." not in row["source"]}
    unknown = sorted(set(profile) - known_root)
    known_children: dict[str, set[str]] = {}
    for row in matrix:
        if "." in row["source"]:
            root, child = row["source"].split(".", 1)
            known_children.setdefault(root, set()).add(child)
    for root, known in known_children.items():
        nested = profile.get(root)
        if isinstance(nested, dict):
            unknown.extend(f"{root}.{key}" for key in nested if key not in known)
    return sorted(unknown)


def _unknown_tek_fields(profile: dict[str, Any], known_fields: set[str]) -> list[str]:
    unknown = sorted(set(profile) - known_fields)
    for container, model_name in NESTED_MODELS.items():
        _ = model_name  # documents the container relationship without importing the dataclass
        nested = profile.get(container)
        if isinstance(nested, dict):
            unknown.extend(f"{container}.{key}" for key in nested)
    return sorted(unknown)


def _id_duplicates(groups: dict[str, list[dict[str, Any]]]) -> set[tuple[str, str]]:
    duplicates: set[tuple[str, str]] = set()
    for kind, profiles in groups.items():
        by_id: dict[str, int] = {}
        for profile in profiles:
            value = profile.get("id")
            if isinstance(value, str) and value:
                by_id[value] = by_id.get(value, 0) + 1
        duplicates.update((kind, key) for key, count in by_id.items() if count > 1)
    return duplicates


def build_preview(classic_path: Path, tek_path: Path, repo_root: Path, clusters_path: Path | None = None) -> dict[str, Any]:
    matrix = build_field_matrix(repo_root)
    tek_schema_path = repo_root / SCHEMA_FILES["tek"][0]
    tek_field_names = {name for name, _typ, _default, _purpose in _class_fields(tek_schema_path, "AsmServerConfig")}
    classic_profiles, classic_errors = _load_profiles(classic_path, "classic")
    tek_profiles, tek_errors = _load_profiles(tek_path, "TEK")
    cluster_profiles: list[dict[str, Any]] = []
    cluster_errors: list[str] = []
    if clusters_path is not None:
        cluster_profiles, cluster_errors = _load_profiles(clusters_path, "cluster")
    groups = {"classic": classic_profiles, "TEK": tek_profiles}
    duplicate_ids = _id_duplicates(groups)

    path_entries: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    summaries: dict[str, list[dict[str, Any]]] = {"classic": [], "TEK": []}
    for kind, profiles in groups.items():
        for profile in profiles:
            info = _path_info(profile.get("install_dir"))
            profile_id = str(profile.get("id", ""))
            summaries[kind].append({
                "id": profile_id,
                "name": str(profile.get("name", "")),
                "origin": kind,
                "install_path": info,
                "unknown_field_names": sorted(
                    set(profile) - (tek_field_names if kind == "TEK" else {r["source"].split(".")[0] for r in matrix})
                ),
            })
            if info["absolute"]:
                path_entries.append((kind, profile, info))

    path_conflicts: list[list[tuple[str, dict[str, Any], dict[str, Any]]]] = []
    for index, entry in enumerate(path_entries):
        matching = [entry]
        for candidate in path_entries[index + 1 :]:
            if _same_installation(entry[2], candidate[2]):
                matching.append(candidate)
        if len(matching) > 1 and not any(
            all(any(existing[1] is member[1] for existing in group) for member in matching)
            for group in path_conflicts
        ):
            path_conflicts.append(matching)
    cross_id_counts: dict[str, set[str]] = {}
    for kind, profiles in groups.items():
        for profile in profiles:
            pid = profile.get("id")
            if isinstance(pid, str) and pid:
                cross_id_counts.setdefault(pid, set()).add(kind)

    reports: list[dict[str, Any]] = []
    for profile in classic_profiles:
        pid = str(profile.get("id", ""))
        path_info = _path_info(profile.get("install_dir"))
        changed, sensitive, invalid = _profile_fields(profile, matrix)
        unknown_fields = _unknown_classic_fields(profile, matrix)
        id_matches = [x for x in tek_profiles if pid and str(x.get("id", "")) == pid]
        path_matches = [x for x in tek_profiles if _same_installation(path_info, _path_info(x.get("install_dir")))]
        candidates = {str(x.get("id", "")) for x in [*id_matches, *path_matches]}
        issues: list[dict[str, str]] = []
        blocked = False
        if not pid or not isinstance(profile.get("id"), str):
            issues.append({"code": "invalid_required_id", "severity": "blocker"}); blocked = True
        if not str(profile.get("name", "")).strip():
            issues.append({"code": "invalid_required_name", "severity": "blocker"}); blocked = True
        if not path_info["raw"]:
            issues.append({"code": "install_path_missing", "severity": "blocker"}); blocked = True
        if ("classic", pid) in duplicate_ids or pid in cross_id_counts and len(cross_id_counts[pid]) > 1:
            issues.append({"code": "duplicate_profile_id", "severity": "blocker"}); blocked = True
        if any(any(entry[1] is profile for entry in group) for group in path_conflicts):
            issues.append({"code": "duplicate_install_path", "severity": "blocker"}); blocked = True
        if path_info["directory_state"] != "directory_exists":
            issues.append({"code": path_info["directory_state"], "severity": "review"})
        if invalid:
            issues.extend({"code": f"invalid_field_type:{field}", "severity": "blocker"} for field in invalid); blocked = True
        if unknown_fields:
            issues.append({"code": "unrecognized_source_fields", "severity": "blocker"}); blocked = True
        if path_matches:
            issues.append({"code": "tek_profile_already_targets_same_installation", "severity": "blocker"}); blocked = True
        referenced_cluster = str(profile.get("cluster_profile_id", "")).strip()
        if referenced_cluster and clusters_path is None:
            issues.append({"code": "cluster_repository_not_supplied", "severity": "review"})
        elif referenced_cluster and not any(str(c.get("id", "")) == referenced_cluster for c in cluster_profiles):
            issues.append({"code": "referenced_cluster_profile_missing", "severity": "blocker"}); blocked = True
        for matched in [*id_matches, *path_matches]:
            unknown_tek = _unknown_tek_fields(matched, tek_field_names)
            if unknown_tek:
                issues.append({"code": "matched_tek_profile_has_unrecognized_fields", "severity": "blocker"})
                blocked = True
                break
        unresolved = []
        for item in changed:
            status = item["compatibility"]
            if status == "no_equivalent":
                issues.append({"code": f"nondefault_field_without_destination:{item['field']}", "severity": "blocker"})
                blocked = True
            elif status != "direct_equivalence_validated":
                unresolved.append(item["field"])
        if unresolved:
            issues.append({"code": "nondefault_fields_need_semantic_review", "severity": "review"})
        if path_info["directory_state"] in {"relative_unresolved", "directory_missing_or_inaccessible", "unverifiable_host_path", "missing_value"}:
            blocked = blocked or path_info["directory_state"] == "missing_value"
        status = "BLOCKED" if blocked else ("REVIEW_REQUIRED" if issues or unresolved else "READY_FOR_FUTURE_MIGRATION")
        reports.append({
            "id": pid,
            "name": str(profile.get("name", "")),
            "origin": "classic",
            "install_path": path_info,
            "tek_candidates": sorted(candidates),
            "changed_fields": sorted(changed, key=lambda x: x["field"]),
            "sensitive_fields_present": sorted(sensitive),
            "invalid_fields": sorted(invalid),
            "unknown_field_names": unknown_fields,
            "conflicts_and_pending_items": sorted(issues, key=lambda x: (x["severity"], x["code"])),
            "eligibility": status,
        })

    conflicts = []
    for kind, errors in (("classic", classic_errors), ("TEK", tek_errors)):
        conflicts.extend({"code": "malformed_profile_entry", "origin": kind, "detail": error, "severity": "blocker"} for error in errors)
    conflicts.extend({"code": "malformed_profile_entry", "origin": "cluster", "detail": error, "severity": "blocker"} for error in cluster_errors)
    for pid, kinds in sorted(cross_id_counts.items()):
        if len(kinds) > 1:
            conflicts.append({"code": "duplicate_id_across_repositories", "id": pid, "origins": sorted(kinds), "severity": "blocker"})
    for entries in path_conflicts:
        conflicts.append({
            "code": "duplicate_normalized_install_path",
            "normalized_path": entries[0][2]["normalized"],
            "profiles": sorted({(kind, str(profile.get("id", ""))) for kind, profile, _info in entries}),
            "identity_basis": "normalized_path_or_filesystem_samefile",
            "severity": "blocker",
        })
    cluster_ids: dict[str, int] = {}
    for cluster in cluster_profiles:
        cid = str(cluster.get("id", ""))
        if cid:
            cluster_ids[cid] = cluster_ids.get(cid, 0) + 1
    for cid, count in sorted(cluster_ids.items()):
        if count > 1:
            conflicts.append({"code": "duplicate_cluster_profile_id", "id": cid, "count": count, "severity": "blocker"})

    return {
        "report_version": 1,
        "mode": "read_only_preview",
        "migration_performed": False,
        "application_components_loaded": False,
        "ini_files_opened": False,
        "database_opened": False,
        "server_operations_performed": False,
        "profile_repositories": {
            "classic": {"path": str(classic_path), "profiles": summaries["classic"]},
            "TEK": {"path": str(tek_path), "profiles": summaries["TEK"]},
            "clusters": {
                "path": str(clusters_path) if clusters_path else None,
                "provided": clusters_path is not None,
                "profiles": [
                    {"id": str(c.get("id", "")), "name": str(c.get("name", "")),
                     "cluster_id": str(c.get("cluster_id", ""))}
                    for c in sorted(cluster_profiles, key=lambda x: (str(x.get("name", "")).casefold(), str(x.get("id", ""))))
                ],
            },
        },
        "classic_profile_previews": sorted(reports, key=lambda x: (x["name"].casefold(), x["id"])),
        "global_conflicts": sorted(conflicts, key=lambda x: (x.get("code", ""), x.get("id", ""))),
        "field_matrix": matrix,
        "decision_note": "Eligibility is diagnostic only. No profile or INI migration is implemented by this tool.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# ARKLAND — Pré-visualização de migração para TEK",
        "",
        "Modo: somente leitura. Migração executada: não.",
        "",
        "## Perfis clássicos",
        "",
        "| Perfil | ID | Caminho normalizado | Estado | Pendências |",
        "|---|---|---|---|---|",
    ]
    for item in report["classic_profile_previews"]:
        path = item["install_path"]["normalized"].replace("|", "\\|")
        pending = ", ".join(x["code"] for x in item["conflicts_and_pending_items"]) or "—"
        lines.append(f"| {item['name']} | `{item['id']}` | `{path}` | **{item['eligibility']}** | {pending} |")
    lines += ["", "## Conflitos globais", ""]
    if report["global_conflicts"]:
        for conflict in report["global_conflicts"]:
            lines.append(f"- `{conflict['code']}` ({conflict['severity']})")
    else:
        lines.append("Nenhum conflito global detectado nos dados fornecidos.")
    lines += ["", "## Campos clássicos fora do padrão", "", "Valores não são incluídos no relatório; apenas nomes e classificações.", ""]
    for profile in report["classic_profile_previews"]:
        lines.append(f"### {profile['name']} (`{profile['id']}`)")
        lines.append("")
        lines.append("| Campo | Tipo origem | Padrão | Destino candidato | Compatibilidade | Decisão |")
        lines.append("|---|---|---|---|---|---|")
        changed = {x["field"] for x in profile["changed_fields"]}
        for row in report["field_matrix"]:
            if row["source"] not in changed:
                continue
            lines.append("| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row["source"], row["source_type"], str(row["source_default"]).replace("|", "\\|"),
                row["destination"] or "sem equivalente", row["compatibility"], row["migration_decision"],
            ))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_new_output(path: Path, data: str, inputs: list[Path]) -> None:
    destination = path.expanduser().resolve(strict=False)
    protected = {p.expanduser().resolve(strict=False) for p in inputs}
    if destination in protected:
        raise PreviewError("Output path resolves to an input file; refusing to overwrite profile data")
    if not destination.parent.is_dir():
        raise PreviewError("Output directory must already exist; the preview never creates directories")
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise PreviewError("Output file already exists; refusing to overwrite it") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only classic-to-TEK profile migration preview")
    parser.add_argument("--classic", type=Path, help="Path to classic servers.json")
    parser.add_argument("--tek", type=Path, help="Path to TEK asm_servers.json")
    parser.add_argument("--clusters", type=Path, help="Optional shared clusters.json, read-only")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--out", type=Path, help="Optional new diagnostic output file; never overwrites")
    parser.add_argument("--matrix-only", action="store_true", help="Emit the field matrix instead of profile comparison")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        if args.matrix_only:
            output: Any = {"field_matrix": build_field_matrix(root), "migration_performed": False}
        else:
            if args.classic is None or args.tek is None:
                parser.error("--classic and --tek are required unless --matrix-only is used")
            output = build_preview(args.classic, args.tek, root, args.clusters)
        rendered = render_markdown(output) if args.format == "markdown" and not args.matrix_only else json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out:
            inputs = [] if args.matrix_only else [args.classic, args.tek, *([args.clusters] if args.clusters else [])]
            _write_new_output(args.out, rendered, inputs)
        else:
            sys.stdout.write(rendered)
    except (PreviewError, OSError, SyntaxError) as exc:
        print(f"preview error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
