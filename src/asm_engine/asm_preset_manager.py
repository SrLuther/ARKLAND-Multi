"""
AsmPresetManager — salva/aplica subconjuntos de configuração como presets reutilizáveis.
Presets ficam em %APPDATA%\\ARKLAND-ServerManager\\presets\\*.json
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .asm_server_config import AsmServerConfig

# ── Categorias de preset ──────────────────────────────────────────────────────

PRESET_CATEGORIES: Dict[str, List[str]] = {
    "players": [
        "xp_multiplier", "player_damage_multiplier", "player_resistance_multiplier",
        "player_water_drain_multiplier", "player_food_drain_multiplier",
        "player_stamina_drain_multiplier", "player_health_recovery_multiplier",
        "player_harvesting_damage_multiplier", "crafting_skill_bonus_multiplier",
        "craft_xp_multiplier", "generic_xp_multiplier", "harvest_xp_multiplier",
        "kill_xp_multiplier", "special_xp_multiplier", "override_max_xp_player",
        "enable_flyer_carry", "per_level_player",
    ],
    "dinos": [
        "dino_damage_multiplier", "tamed_dino_damage_multiplier",
        "dino_resistance_multiplier", "tamed_dino_resistance_multiplier",
        "max_tamed_dinos", "dino_count_multiplier", "taming_speed_multiplier",
        "passive_tame_interval_multiplier", "disable_imprint_buff",
        "allow_anyone_baby_imprint", "disable_dino_riding", "disable_dino_taming",
        "dino_harvesting_damage_multiplier", "per_level_dino_wild",
        "per_level_dino_tamed", "per_level_dino_tamed_add",
        "per_level_dino_tamed_affinity",
    ],
    "breeding": [
        "mating_interval_multiplier", "egg_hatch_speed_multiplier",
        "baby_mature_speed_multiplier", "baby_food_consumption_multiplier",
        "baby_cuddle_interval_multiplier", "baby_cuddle_grace_period_multiplier",
        "baby_cuddle_lose_imprint_quality_speed_multiplier",
        "baby_imprinting_stat_scale",
    ],
    "environment": [
        "harvest_amount_multiplier", "harvest_health_multiplier",
        "resources_respawn_multiplier", "day_cycle_speed_scale",
        "day_time_speed_scale", "night_time_speed_scale",
        "global_spoiling_time_multiplier", "global_item_decomposition_multiplier",
        "global_corpse_decomposition_multiplier", "crop_decay_speed_multiplier",
        "crop_growth_speed_multiplier", "hair_growth_speed_multiplier",
        "base_temperature_multiplier", "disable_weather_fog",
    ],
    "structures": [
        "structure_resistance_multiplier", "structure_damage_multiplier",
        "max_structures_in_range", "per_platform_max_structures_multiplier",
        "max_platform_saddle_structures", "enable_structure_decay_pve",
        "pve_structure_decay_period_multiplier", "limit_turrets_in_range",
        "limit_turrets_num",
    ],
    "rules": [
        "enable_pvp", "enable_hardcore", "allow_cave_building_pve",
        "disable_friendly_fire_pvp", "disable_friendly_fire_pve",
        "enable_difficulty_override", "override_official_difficulty",
        "difficulty_offset", "max_tribe_size", "allow_tribe_alliances",
        "allow_custom_recipes", "enable_diseases",
    ],
}
PRESET_CATEGORIES["full"] = list({
    f for cat_fields in PRESET_CATEGORIES.values() for f in cat_fields
})


class AsmPresetManager:
    """Exporta/importa subconjuntos de config como presets reutilizáveis."""

    def __init__(self) -> None:
        self._dir = (
            Path(os.environ.get("APPDATA", Path.home()))
            / "ARKLAND-ServerManager"
            / "presets"
        )

    # ── Persistência ──────────────────────────────────────────────────────────

    def _path(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
        return self._dir / f"{safe}.json"

    def list_presets(self) -> List[Dict[str, Any]]:
        if not self._dir.exists():
            return []
        result = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
                result.append({
                    "name":        data.get("name", p.stem),
                    "created_at":  data.get("created_at", ""),
                    "categories":  data.get("categories", []),
                    "description": data.get("description", ""),
                    "path":        str(p),
                })
            except Exception:
                pass
        return result

    def save_preset(
        self,
        name: str,
        srv: "AsmServerConfig",
        categories: List[str],
        description: str = "",
    ) -> None:
        """Salva um preset com os campos das categorias indicadas."""
        all_fields = set()
        for cat in categories:
            all_fields.update(PRESET_CATEGORIES.get(cat, [cat]))  # suporta campo direto

        valid = {f.name for f in fields(srv)}
        values: Dict[str, Any] = {}
        for f_name in all_fields:
            if f_name in valid:
                values[f_name] = getattr(srv, f_name)

        payload = {
            "version":     "1.0",
            "name":        name,
            "created_at":  datetime.now().isoformat(timespec="seconds"),
            "categories":  categories,
            "description": description,
            "values":      values,
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._path(name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    def load_preset(self, name_or_path: str, srv: "AsmServerConfig") -> None:
        """Aplica um preset ao servidor (sem sobrescrever campos fora do preset)."""
        p = Path(name_or_path)
        if not p.is_absolute():
            p = self._path(name_or_path)
        with open(p, encoding="utf-8") as fh:
            payload = json.load(fh)
        values: Dict[str, Any] = payload.get("values", {})
        valid = {f.name for f in fields(srv)}
        for k, v in values.items():
            if k in valid:
                try:
                    setattr(srv, k, v)
                except Exception:
                    pass

    def delete_preset(self, name: str) -> None:
        p = self._path(name)
        if p.exists():
            p.unlink()
