"""Coleta rates e níveis de servidor a partir de INI / AsmServerConfig para a Web Store."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .buff_manager import BUFF_RATE_FIELDS, BuffEvent, stack_buff_rate


def _norm_slug(value: str) -> str:
    base = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


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


def _reload_ini_if_possible(cfg: object) -> None:
    if not _is_tek(cfg):
        return
    install_dir = (getattr(cfg, "install_dir", "") or "").strip()
    if not install_dir:
        return
    try:
        from .asm_engine.asm_ini_manager import read_ini

        read_ini(cfg)  # type: ignore[arg-type]
    except Exception:
        pass


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
    if _is_tek(cfg):
        override = int(getattr(cfg, "override_max_xp_player", 0) or 0)
        if override > 0:
            return override
        if getattr(cfg, "enable_difficulty_override", False):
            diff = float(getattr(cfg, "override_official_difficulty", 5.0) or 5.0)
            return 105 + int(round(diff * 15))
        return 105
    gs = getattr(cfg, "game_settings", None)
    if gs is None:
        return 105
    diff = float(getattr(gs, "override_official_difficulty", 5.0) or 5.0)
    return 105 + int(round(diff * 15))


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
        _reload_ini_if_possible(cfg)

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

    snapshot: Dict[str, Any] = {
        "xp_multiplier": xp,
        "taming_speed_multiplier": taming,
        "harvest_amount_multiplier": harvest,
        "mating_interval_multiplier": mating,
        "baby_mature_speed_multiplier": mature,
        "max_player_level": compute_max_player_level(cfg),
        "max_dino_level": compute_max_wild_dino_level(cfg),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "buff_active": buff_event is not None,
    }
    if buff_event is not None:
        snapshot["buff_name"] = buff_event.name
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
    out = {
        "xp": _format_rate(xp),
        "taming": _format_rate(taming),
        "harvest": _format_rate(harvest),
        "mating": _format_rate(mating),
        "mature": _format_rate(mature),
        "max_player_level": int(snapshot.get("max_player_level", 0) or 0),
        "max_dino_level": int(snapshot.get("max_dino_level", 0) or 0),
        "buff_active": bool(snapshot.get("buff_active")),
    }
    if snapshot.get("buff_name"):
        out["buff_name"] = str(snapshot["buff_name"])
    if snapshot.get("updated_at"):
        out["updated_at"] = str(snapshot["updated_at"])
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
        for raw in (sid, srv.get("label", "")):
            slug = _norm_slug(str(raw or ""))
            if slug:
                by_slug[slug] = snap
    return by_id, by_slug
