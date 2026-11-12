"""Safe, profile-scoped change history for TEK server settings."""
from __future__ import annotations

import json
from dataclasses import fields

from ..arkland_environment import default_manager_log_dir
from ..change_logger import ChangeLogger, diff_snapshots
from .asm_server_config import AsmServerConfig


_NEVER_LOG = {
    "admin_ids", "whitelist_ids", "exclusive_join_ids", "notes",
    "mod_ini_configs", "managed_mod_ini_blocks", "managed_ini_options",
    "custom_ini_sections", "custom_gus_ini_raw", "custom_game_ini_raw",
    "custom_engine_ini_raw", "crafting_overrides_raw", "stack_size_overrides_raw",
    "npc_spawn_overrides_raw", "supply_crate_overrides_raw", "prevent_transfer_raw",
    "player_level_stats_raw", "dino_level_stats_raw", "engram_entries_raw",
    "install_dir", "user_config_folder", "additional_args",
    "backup_dir", "server_ip",
}
_SECRET_PARTS = (
    "password", "token", "secret", "credential", "webhook", "api_key",
    "private_key", "license", "args",
)


def snapshot_asm_server(srv: AsmServerConfig) -> dict[tuple[str, str], str]:
    """Serialize only scalar/list settings that are safe to retain in audit logs."""
    result: dict[tuple[str, str], str] = {}
    for field_def in fields(AsmServerConfig):
        name = field_def.name
        lowered = name.casefold()
        if name in _NEVER_LOG or lowered.endswith("_raw"):
            continue
        if any(part in lowered for part in _SECRET_PARTS):
            continue
        if name in {"id", "color", "folder", "tags"}:
            continue
        value = getattr(srv, name, None)
        if isinstance(value, (str, bool, int, float)) or (
            isinstance(value, list)
            and all(isinstance(item, (str, bool, int, float)) for item in value)
        ):
            result[("TEK", name)] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return result


def get_asm_change_logger(server_id: str) -> ChangeLogger:
    """Return the TEK-isolated JSONL file; classic history remains untouched."""
    return ChangeLogger(default_manager_log_dir(), f"tek_{server_id}")


def record_asm_server_changes(
    server_id: str,
    before: dict[tuple[str, str], str],
    after: dict[tuple[str, str], str],
    *,
    before_profile: dict | None = None,
    after_profile: dict | None = None,
) -> int:
    logger = get_asm_change_logger(server_id)
    count = diff_snapshots(logger, before, after)
    before_profile = before_profile or {}
    after_profile = after_profile or {}
    redacted_fields = set(_NEVER_LOG)
    redacted_fields.update(
        field_def.name
        for field_def in fields(AsmServerConfig)
        if any(part in field_def.name.casefold() for part in _SECRET_PARTS)
        or field_def.name.casefold().endswith("_raw")
    )
    for name in redacted_fields:
        old = before_profile.get(name)
        new = after_profile.get(name)
        if old != new:
            logger.log("TEK", f"{name} (valores omitidos)", "anterior", "alterado")
            count += 1
    return count
