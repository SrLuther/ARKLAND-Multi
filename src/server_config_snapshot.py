"""Coleta rates e níveis de servidor a partir de INI / AsmServerConfig para a Web Store."""
from __future__ import annotations

import re
import copy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .buff_manager import (
    BUFF_RATE_FIELDS,
    BUFF_TYPE_BREEDING,
    BUFF_TYPE_DOMA,
    BUFF_TYPE_FARM,
    BUFF_TYPE_XP,
    BuffEvent,
    DEFAULT_SERVER_RATE_MULT,
    compute_buff_field_value,
    stack_buff_rate,
)


def norm_slug(value: str) -> str:
    """Slug estável para casar mapa ↔ servidor (público para arkshop_web)."""
    base = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


_norm_slug = norm_slug


def _read_rate(cfg: object, field_name: str, *, game_settings: bool = False) -> float:
    if game_settings and hasattr(cfg, "game_settings"):
        val = getattr(cfg.game_settings, field_name, 1.0)
    else:
        val = getattr(cfg, field_name, 1.0)
    try:
        f = float(val)
    except (TypeError, ValueError):
        return 1.0
    return f if f > 0 else 1.0


def _is_tek(cfg: object) -> bool:
    return hasattr(cfg, "enable_difficulty_override") and not hasattr(cfg, "game_settings")


def _reload_ini_if_possible(cfg: object) -> object:
    """Read the live INI files into a copy so public snapshots reflect disk state."""
    if not _is_tek(cfg):
        install_dir = (getattr(cfg, "install_dir", "") or "").strip()
        if not install_dir:
            return cfg
        try:
            from .ark_ini import ArkIniManager

            snapshot_cfg = copy.deepcopy(cfg)
            ini = ArkIniManager(install_dir)
            ini.load_game_user_settings(snapshot_cfg)
            ini.load_game_ini(snapshot_cfg)
            return snapshot_cfg
        except Exception:
            return cfg
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return cfg
    try:
        from .asm_engine.asm_ini_manager import read_ini

        read_ini(cfg)  # type: ignore[arg-type]
    except Exception:
        pass
    return cfg


def compute_max_wild_dino_level(cfg: object) -> int:
    if _is_tek(cfg):
        if getattr(cfg, "enable_difficulty_override", False):
            diff = float(getattr(cfg, "override_official_difficulty", 5.0) or 5.0)
            return max(1, int(round(diff * 30)))
        offset = float(getattr(cfg, "difficulty_offset", 0.2) or 0.2)
        return max(1, int(round((offset + 0.5) * 30)))
    gs = getattr(cfg, "game_settings", None)
    if gs is None:
        return 150
    diff = float(getattr(gs, "override_official_difficulty", 5.0) or 5.0)
    return max(1, int(round(diff * 30)))


def compute_max_player_level(cfg: object) -> int:
    from .player_level_ascension import resolve_max_player_level

    return resolve_max_player_level(cfg)


def compute_theoretical_player_level(cfg: object) -> int:
    from .player_level_ascension import resolve_theoretical_player_level

    return resolve_theoretical_player_level(cfg)


def _effective_rate(
    cfg: object,
    field_name: str,
    *,
    buff_event: Optional[BuffEvent],
    game_settings: bool = False,
) -> float:
    base = _read_rate(cfg, field_name, game_settings=game_settings)
    if buff_event is None:
        return round(base, 4)

    if buff_event.sector_mults.has_any():
        for buff_type, fields in BUFF_RATE_FIELDS.items():
            sector_val = None
            mapping = {
                BUFF_TYPE_XP: buff_event.sector_mults.xp,
                BUFF_TYPE_DOMA: buff_event.sector_mults.doma,
                BUFF_TYPE_BREEDING: buff_event.sector_mults.breeding,
                BUFF_TYPE_FARM: buff_event.sector_mults.farm,
            }
            sector_val = mapping.get(buff_type)
            if sector_val is None:
                continue
            for fname, _label, is_inv in fields:
                if fname != field_name:
                    continue
                return compute_buff_field_value(
                    base, float(sector_val), is_inverse=is_inv,
                    server_mult=DEFAULT_SERVER_RATE_MULT,
                )

    for fields in BUFF_RATE_FIELDS.values():
        for fname, _label, _inv in fields:
            if fname != field_name:
                continue
            buff_val = getattr(buff_event.rates, fname, None)
            if buff_val is not None:
                return stack_buff_rate(base, float(buff_val))
    return round(base, 4)


def _format_rate(value: float) -> str:
    if value >= 100:
        return f"{value:.0f}x"
    if value >= 10:
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}x"
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}x"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}x"


def collect_server_snapshot(
    srv: object,
    *,
    buff_event: Optional[BuffEvent] = None,
    reload_ini: bool = True,
) -> Dict[str, Any]:
    """Monta snapshot público de rates/níveis para um servidor TEK ou clássico."""
    cfg = srv
    if reload_ini:
        cfg = _reload_ini_if_possible(cfg)

    tek = _is_tek(cfg)
    xp = _effective_rate(cfg, "xp_multiplier", buff_event=buff_event, game_settings=not tek)
    taming = _effective_rate(
        cfg, "taming_speed_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    harvest = _effective_rate(
        cfg, "harvest_amount_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    mating = _effective_rate(
        cfg, "mating_interval_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    mature = _effective_rate(
        cfg, "baby_mature_speed_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    hatch = _effective_rate(
        cfg, "egg_hatch_speed_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    cuddle = _effective_rate(
        cfg, "baby_cuddle_interval_multiplier", buff_event=buff_event, game_settings=not tek,
    )
    game_settings = getattr(cfg, "game_settings", None)
    breeding_cfg = game_settings if game_settings is not None else cfg

    def _read_any_rate(*field_names: str) -> float:
        for field_name in field_names:
            if hasattr(breeding_cfg, field_name):
                return _read_rate(breeding_cfg, field_name)
        return 1.0

    food_consumption = _read_any_rate(
        "baby_food_consumption_speed_multiplier", "baby_food_consumption_multiplier",
    )
    cuddle_grace = _read_any_rate("baby_cuddle_grace_period_multiplier")
    imprint_scale = _read_any_rate(
        "baby_imprinting_stat_scale_multiplier", "baby_imprinting_stat_scale",
    )
    tribe_cfg = game_settings if game_settings is not None else cfg
    try:
        max_tribe_size = max(0, int(getattr(tribe_cfg, "max_tribe_size", 0) or 0))
    except (TypeError, ValueError):
        max_tribe_size = 0
    structure_decay = _read_rate(
        game_settings if game_settings is not None else cfg,
        "pve_structure_decay_period_multiplier",
    )
    dino_decay = _read_rate(
        game_settings if game_settings is not None else cfg,
        "pve_dino_decay_period_multiplier",
    )
    structure_decay_disabled = bool(getattr(tribe_cfg, "disable_structure_decay_pve", False))
    dino_decay_disabled = bool(getattr(tribe_cfg, "disable_dino_decay_pve", False))

    theoretical = compute_theoretical_player_level(cfg)
    effective = compute_max_player_level(cfg)

    snapshot: Dict[str, Any] = {
        "xp_multiplier": xp,
        "taming_speed_multiplier": taming,
        "harvest_amount_multiplier": harvest,
        "mating_interval_multiplier": mating,
        "baby_mature_speed_multiplier": mature,
        "egg_hatch_speed_multiplier": hatch,
        "baby_cuddle_interval_multiplier": cuddle,
        "baby_food_consumption_speed_multiplier": food_consumption,
        "baby_cuddle_grace_period_multiplier": cuddle_grace,
        "baby_imprinting_stat_scale_multiplier": imprint_scale,
        "max_tribe_size": max_tribe_size,
        "pve_structure_decay_period_multiplier": structure_decay,
        "pve_dino_decay_period_multiplier": dino_decay,
        "disable_structure_decay_pve": structure_decay_disabled,
        "disable_dino_decay_pve": dino_decay_disabled,
        "max_player_level": effective,
        "max_player_level_theoretical": theoretical,
        "max_dino_level": compute_max_wild_dino_level(cfg),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "buff_active": buff_event is not None,
        "seasonal_event_active": buff_event is not None,
    }
    if buff_event is not None:
        snapshot["buff_name"] = buff_event.name
        snapshot["seasonal_event_name"] = buff_event.name
    return snapshot


def snapshot_public_view(snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Formata snapshot para API pública / cards da home."""
    if not snapshot or not isinstance(snapshot, dict):
        return None
    xp = float(snapshot.get("xp_multiplier", 1) or 1)
    taming = float(snapshot.get("taming_speed_multiplier", 1) or 1)
    harvest = float(snapshot.get("harvest_amount_multiplier", 1) or 1)
    mating = float(snapshot.get("mating_interval_multiplier", 1) or 1)
    mature = float(snapshot.get("baby_mature_speed_multiplier", 1) or 1)
    hatch = float(snapshot.get("egg_hatch_speed_multiplier", 1) or 1)
    cuddle = float(snapshot.get("baby_cuddle_interval_multiplier", 1) or 1)
    food_consumption = float(snapshot.get("baby_food_consumption_speed_multiplier", 1) or 1)
    cuddle_grace = float(snapshot.get("baby_cuddle_grace_period_multiplier", 1) or 1)
    imprint_scale = float(snapshot.get("baby_imprinting_stat_scale_multiplier", 1) or 1)
    max_tribe_size = int(snapshot.get("max_tribe_size", 0) or 0)
    structure_decay = float(snapshot.get("pve_structure_decay_period_multiplier", 1) or 1)
    dino_decay = float(snapshot.get("pve_dino_decay_period_multiplier", 1) or 1)
    out = {
        "xp": _format_rate(xp),
        "taming": _format_rate(taming),
        "harvest": _format_rate(harvest),
        "mating": _format_rate(mating),
        "mature": _format_rate(mature),
        "hatch": _format_rate(hatch),
        "cuddle_interval": _format_rate(cuddle),
        "baby_food_consumption": _format_rate(food_consumption),
        "cuddle_grace": _format_rate(cuddle_grace),
        "imprint_scale": _format_rate(imprint_scale),
        "max_tribe_size": max_tribe_size,
        "structure_decay": _format_rate(structure_decay),
        "dino_decay": _format_rate(dino_decay),
        "structure_decay_disabled": bool(snapshot.get("disable_structure_decay_pve")),
        "dino_decay_disabled": bool(snapshot.get("disable_dino_decay_pve")),
        "updated_at": str(snapshot.get("updated_at") or ""),
        "max_player_level": int(snapshot.get("max_player_level", 0) or 0),
        "max_dino_level": int(snapshot.get("max_dino_level", 0) or 0),
        "buff_active": bool(snapshot.get("buff_active")),
        "seasonal_event_active": bool(
            snapshot.get("seasonal_event_active", snapshot.get("buff_active"))
        ),
    }
    theo = int(snapshot.get("max_player_level_theoretical", 0) or 0)
    eff = int(out["max_player_level"])
    if theo > 0 and theo != eff:
        out["max_player_level_theoretical"] = theo
    event_name = snapshot.get("seasonal_event_name") or snapshot.get("buff_name")
    if event_name:
        out["buff_name"] = str(event_name)
        out["seasonal_event_name"] = str(event_name)
    return out


def match_snapshot_for_map(
    map_entry: Dict[str, Any],
    snapshots_by_id: Dict[str, Dict[str, Any]],
    snapshots_by_slug: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Associa card de mapa ao snapshot por server_id explícito ou nome."""
    sid = str(map_entry.get("server_id") or "").strip()
    if sid and sid in snapshots_by_id:
        return snapshot_public_view(snapshots_by_id[sid])

    for key in (
        _norm_slug(map_entry.get("name", "")),
        _norm_slug(map_entry.get("id", "")),
    ):
        if key and key in snapshots_by_slug:
            return snapshot_public_view(snapshots_by_slug[key])
    return None


def build_snapshot_indexes(
    servers: list[Dict[str, Any]],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_slug: Dict[str, Dict[str, Any]] = {}
    for srv in servers:
        if not isinstance(srv, dict):
            continue
        snap = srv.get("config_snapshot")
        if not isinstance(snap, dict):
            continue
        sid = str(srv.get("server_id", "")).strip()
        if sid:
            by_id[sid] = snap
        for raw in (sid, srv.get("label", ""), srv.get("server_map", "")):
            slug = _norm_slug(str(raw or ""))
            if slug:
                by_slug[slug] = snap
    return by_id, by_slug
