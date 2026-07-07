"""Rampa de XP do jogador (LevelExperienceRampOverrides) — parse, geração e cap efetivo."""
from __future__ import annotations

import json
import re
from typing import Any

from .player_level_ascension import (
    ARK_BOSS_ASCENSION_LEVELS,
    ARK_DEFAULT_BASE_LEVEL,
    ARK_TOTAL_BONUS_LEVELS,
    calc_max_total_level,
    level_to_xp,
)

ARK_ASCENSION_RAMP_SLOTS = ARK_BOSS_ASCENSION_LEVELS  # 75 slots na rampa Game.ini


def total_ramp_slots(base_level: int) -> int:
    """Entradas na rampa: nível base (XP) + 75 ascensão de boss."""
    return max(1, int(base_level or 0)) + ARK_ASCENSION_RAMP_SLOTS

_RAMP_ENTRY_RE = re.compile(
    r"ExperiencePointsForLevel\[(\d+)\]\s*=\s*(\d+)",
    re.IGNORECASE,
)
_RAMP_STRIP_RE = re.compile(
    r"^\s*levelexperiencerampoverrides\s*=.*$",
    re.IGNORECASE | re.MULTILINE,
)

XP_CURVE_VANILLA = "vanilla"
XP_CURVE_CUSTOM = "custom"


def is_player_level_progressions_enabled(cfg: object | None) -> bool:
    """Espelha ASM EnableLevelProgressions — rampa/engrams no Game.ini só quando True."""
    if cfg is None:
        return False
    return bool(getattr(cfg, "player_level_progressions_enabled", False))


def vanilla_xp_per_slot(index: int) -> int:
    """XP do slot index (0-based) na curva vanilla ARK SE."""
    return max(1, round(0.667 * (index + 1) ** 2.04))


def geometric_xp_per_slot(index: int, base: int, mult: float) -> int:
    return max(1, int(base * (mult ** index)))


def _slot_matches_vanilla(index: int, xp: int, *, tolerance: float = 0.02) -> bool:
    expected = vanilla_xp_per_slot(index)
    if expected <= 0:
        return xp <= 1
    return abs(xp - expected) <= max(1, int(expected * tolerance))


def infer_xp_curve_from_ramp(values: list[int]) -> dict[str, Any]:
    """Infere vanilla vs geométrica a partir dos slots lidos do Game.ini."""
    if not values:
        return {"mode": XP_CURVE_VANILLA}
    sample = min(len(values), 8)
    if all(_slot_matches_vanilla(i, values[i]) for i in range(sample)):
        return {"mode": XP_CURVE_VANILLA}
    xp_base = max(1, int(values[0]))
    xp_mult = 1.15
    if len(values) > 1 and values[0] > 0:
        xp_mult = float(values[1]) / float(values[0])
    xp_mult = max(1.01, min(xp_mult, 3.0))
    return {
        "mode": XP_CURVE_CUSTOM,
        "xp_base": xp_base,
        "xp_mult": xp_mult,
        "formula": "base * (mult ** i)",
    }


def apply_inferred_xp_curve(cfg: object, values: list[int]) -> None:
    """Atualiza player_xp_curve_* quando a rampa do disco não é vanilla."""
    if not values:
        return
    inferred = infer_xp_curve_from_ramp(values)
    if inferred.get("mode") == XP_CURVE_VANILLA:
        return
    _apply_curve_params_to_cfg(cfg, inferred)


def _apply_curve_params_to_cfg(cfg: object, params: dict[str, Any]) -> None:
    if hasattr(cfg, "player_xp_curve_mode"):
        cfg.player_xp_curve_mode = XP_CURVE_CUSTOM
    if hasattr(cfg, "player_xp_curve_base") and "xp_base" in params:
        cfg.player_xp_curve_base = int(params["xp_base"])
    if hasattr(cfg, "player_xp_curve_mult") and "xp_mult" in params:
        cfg.player_xp_curve_mult = float(params["xp_mult"])
    if hasattr(cfg, "player_xp_curve_formula") and params.get("formula"):
        cfg.player_xp_curve_formula = str(params["formula"])


def _read_override_xp_from_cfg(cfg: object) -> int:
    existing_xp = _read_cfg_int(cfg, "override_max_xp_player", 0)
    gs = getattr(cfg, "game_settings", None)
    if gs is not None:
        existing_xp = max(
            existing_xp,
            _read_cfg_int(gs, "override_max_experience_points_player", 0),
        )
    return existing_xp


def vanilla_xp_cap_for_base(base: int) -> int:
    """XP acumulado na curva vanilla até o nível base."""
    base = max(1, int(base or 0))
    values = build_ramp_values(base, mode=XP_CURVE_VANILLA)
    return cumulative_xp_on_ramp(values, base)


def is_legacy_geometric_xp_cap(existing_xp: int, base: int) -> bool:
    """True quando o cap GUS/JSON indica curva geométrica legada (≫ vanilla)."""
    cap = int(existing_xp or 0)
    base = int(base or 0)
    if cap <= 0 or base <= 0:
        return False
    vanilla_cap = vanilla_xp_cap_for_base(base)
    return cap > max(vanilla_cap * 2, 10_000_000)


def infer_player_level_progressions_enabled(data: dict) -> bool:
    """Migração: habilita progressões só quando o perfil já tinha rampa/curva custom."""
    if "player_level_progressions_enabled" in data:
        return bool(data["player_level_progressions_enabled"])
    if str(data.get("player_xp_curve_mode", "")).lower() == XP_CURVE_CUSTOM:
        return True
    raw = str(data.get("player_level_stats_raw", "") or "")
    if int(parse_ramp_from_text(raw).get("entry_count", 0) or 0) > 0:
        return True
    base = int(data.get("player_base_level", 0) or 0)
    xp = int(data.get("override_max_xp_player", 0) or 0)
    if base > 0 and is_legacy_geometric_xp_cap(xp, base):
        return True
    return False


def _expected_ramp_slots(cfg: object, base: int | None = None) -> int:
    resolved = int(base if base is not None else _resolve_base_level(cfg))
    if resolved > 0:
        return total_ramp_slots(resolved)
    count = _read_cfg_int(cfg, "player_ramp_entry_count", 0)
    if count > 0:
        return count
    parsed = parse_ramp_from_text(_read_cfg_str(cfg, "player_level_stats_raw", ""))
    return max(int(parsed.get("entry_count", 0) or 0), 0)


def ensure_ramp_slot_count(cfg: object, count: int, *, base: int | None = None) -> int:
    """Garante contagem mínima base+75 quando o nível base está configurado."""
    count = max(0, int(count or 0))
    expected = _expected_ramp_slots(cfg, base)
    if expected > 0 and (count <= 0 or count < expected):
        return expected
    return count


def detect_and_apply_legacy_curve(cfg: object) -> bool:
    """Detecta curva geométrica (rampa, cap GUS) e atualiza cfg — só com progressões ativas."""
    if not is_player_level_progressions_enabled(cfg):
        return False
    base = _resolve_base_level(cfg)
    applied = False

    parsed = parse_ramp_from_text(_read_cfg_str(cfg, "player_level_stats_raw", ""))
    ramp_count = ensure_ramp_slot_count(
        cfg,
        int(parsed.get("entry_count", 0) or 0),
        base=base if base > 0 else None,
    )
    if ramp_count > 0 and parsed.get("slots"):
        values = ramp_slots_to_values(parsed["slots"], ramp_count)
        inferred = infer_xp_curve_from_ramp(values)
        if inferred.get("mode") == XP_CURVE_CUSTOM:
            _apply_curve_params_to_cfg(cfg, inferred)
            applied = True

    if base > 0 and is_legacy_geometric_xp_cap(_read_override_xp_from_cfg(cfg), base):
        _apply_curve_params_to_cfg(
            cfg,
            {
                "xp_base": _read_cfg_int(cfg, "player_xp_curve_base", 70),
                "xp_mult": _read_cfg_float(cfg, "player_xp_curve_mult", 1.15),
                "formula": _read_cfg_str(
                    cfg, "player_xp_curve_formula", "base * (mult ** i)"
                ),
            },
        )
        applied = True

    if (
        base > 0
        and is_player_level_progressions_enabled(cfg)
        and _read_cfg_str(cfg, "player_xp_curve_mode", XP_CURVE_VANILLA).lower() != XP_CURVE_CUSTOM
    ):
        if not applied:
            _apply_curve_params_to_cfg(
                cfg,
                {
                    "xp_base": _read_cfg_int(cfg, "player_xp_curve_base", 70),
                    "xp_mult": _read_cfg_float(cfg, "player_xp_curve_mult", 1.15),
                    "formula": _read_cfg_str(
                        cfg, "player_xp_curve_formula", "base * (mult ** i)"
                    ),
                },
            )
        applied = True

    return applied


def resolve_xp_curve_mode(cfg: object | None) -> str:
    """Modo efetivo da curva — custom só com progressões habilitadas."""
    if cfg is None:
        return XP_CURVE_VANILLA
    if not is_player_level_progressions_enabled(cfg):
        return XP_CURVE_VANILLA
    detect_and_apply_legacy_curve(cfg)
    return _read_cfg_str(cfg, "player_xp_curve_mode", XP_CURVE_VANILLA).lower()


def parse_ramp_from_text(text: str) -> dict[str, Any]:
    """Conta entradas e índices de LevelExperienceRampOverrides em texto INI.

    Aceita o formato oficial (uma linha, todos os níveis) e o legado ASM
    (uma chave repetida por índice).
    """
    slots: dict[int, int] = {}
    if not text or not str(text).strip():
        return {"entry_count": 0, "max_index": -1, "slots": slots, "indices": []}
    for match in _RAMP_ENTRY_RE.finditer(str(text)):
        idx = int(match.group(1))
        xp = int(match.group(2))
        slots[idx] = xp
    indices = sorted(slots)
    max_index = max(indices) if indices else -1
    entry_count = max_index + 1 if max_index >= 0 else len(indices)
    return {
        "entry_count": entry_count,
        "max_index": max_index,
        "slots": slots,
        "indices": indices,
    }


def ramp_slots_to_values(slots: dict[int, int], entry_count: int) -> list[int]:
    """Converte mapa de slots em lista ordenada (preenche lacunas com vanilla)."""
    if entry_count <= 0:
        return []
    values: list[int] = []
    for i in range(entry_count):
        if i in slots:
            values.append(slots[i])
        else:
            values.append(vanilla_xp_per_slot(i))
    return values


def build_ramp_values(
    base_level: int,
    *,
    mode: str = XP_CURVE_VANILLA,
    xp_base: int = 70,
    xp_mult: float = 1.15,
    formula: str = "base * (mult ** i)",
) -> list[int]:
    """Gera valores de XP por slot: base_level farmáveis + 75 ascensão."""
    count = total_ramp_slots(base_level)
    values: list[int] = []
    mode_n = (mode or XP_CURVE_VANILLA).strip().lower()
    for i in range(count):
        if mode_n == XP_CURVE_CUSTOM:
            try:
                xp = int(
                    eval(
                        (formula or "base * (mult ** i)").strip(),
                        {"__builtins__": {}},
                        {"i": i, "base": int(xp_base), "mult": float(xp_mult)},
                    )
                )
            except Exception:
                xp = geometric_xp_per_slot(i, int(xp_base), float(xp_mult))
            values.append(max(1, xp))
        else:
            values.append(vanilla_xp_per_slot(i))
    return values


def build_ramp_ini_line(values: list[int]) -> str:
    """Uma linha no formato oficial ARK (todos os níveis na mesma entrada)."""
    parts = ",".join(
        f"ExperiencePointsForLevel[{i}]={xp}" for i, xp in enumerate(values)
    )
    return f"LevelExperienceRampOverrides=({parts})"


def build_ramp_ini_lines(values: list[int]) -> list[str]:
    """Retorna uma única linha para patch_game_ini_repeated_lines."""
    if not values:
        return []
    return [build_ramp_ini_line(values)]


def cumulative_xp_on_ramp(values: list[int], level: int) -> int:
    """XP acumulado na rampa até atingir `level` (1-based)."""
    lvl = max(0, int(level))
    if lvl <= 1:
        return 0
    need = min(lvl - 1, len(values))
    return sum(values[:need])


def xp_to_level_on_ramp(values: list[int], xp: int) -> int:
    """Converte XP acumulado em nível-teto na rampa customizada."""
    target = max(0, int(xp or 0))
    if target <= 0 or not values:
        return 0
    total = 0
    for i, slot_xp in enumerate(values):
        total += slot_xp
        if total > target:
            return i + 1
    return len(values) + 1


def xp_cap_on_ramp(values: list[int], override_xp: int) -> int:
    """Nível máximo permitido pelo cap de XP na rampa."""
    cap = int(override_xp or 0)
    if cap <= 0:
        return 0
    if not values:
        return 0
    return xp_to_level_on_ramp(values, cap)


def strip_ramp_from_raw(raw: str) -> str:
    if not raw or not str(raw).strip():
        return ""
    kept: list[str] = []
    for line in str(raw).splitlines():
        if _RAMP_STRIP_RE.match(line.strip()):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def export_ramp_raw(values: list[int]) -> str:
    return "\n".join(build_ramp_ini_lines(values))


def _read_cfg_int(cfg: object, name: str, default: int = 0) -> int:
    try:
        return int(getattr(cfg, name, default) or default)
    except (TypeError, ValueError):
        return default


def _read_cfg_float(cfg: object, name: str, default: float = 1.0) -> float:
    try:
        return float(getattr(cfg, name, default) or default)
    except (TypeError, ValueError):
        return default


def _read_cfg_str(cfg: object, name: str, default: str = "") -> str:
    val = getattr(cfg, name, default)
    return str(val if val is not None else default)


def get_ramp_values_from_cfg(cfg: object) -> list[int]:
    """Valores da rampa: vazio no modo simples; senão nível base tem prioridade."""
    if not is_player_level_progressions_enabled(cfg):
        return []
    detect_and_apply_legacy_curve(cfg)
    base = _resolve_base_level(cfg)
    curve = _curve_params_from_cfg(cfg)
    if base > 0:
        return build_ramp_values(
            base,
            mode=str(curve["mode"]),
            xp_base=int(curve["xp_base"]),
            xp_mult=float(curve["xp_mult"]),
            formula=str(curve["formula"]),
        )

    count = ensure_ramp_slot_count(cfg, _read_cfg_int(cfg, "player_ramp_entry_count", 0))
    parsed = parse_ramp_from_text(_read_cfg_str(cfg, "player_level_stats_raw", ""))
    if count > 0 and parsed.get("slots"):
        return ramp_slots_to_values(parsed["slots"], count)
    return []


def _resolve_base_level(cfg: object) -> int:
    base = _read_cfg_int(cfg, "player_base_level", 0)
    if base <= 0:
        gs = getattr(cfg, "game_settings", None)
        if gs is not None:
            base = _read_cfg_int(gs, "player_base_level", 0)
    return base


def get_ramp_entry_count(cfg: object) -> int:
    base = _resolve_base_level(cfg)
    if base > 0:
        return total_ramp_slots(base)
    stored = _read_cfg_int(cfg, "player_ramp_entry_count", 0)
    parsed = parse_ramp_from_text(_read_cfg_str(cfg, "player_level_stats_raw", ""))
    disk_count = int(parsed.get("entry_count", 0) or 0)
    return ensure_ramp_slot_count(cfg, max(stored, disk_count))


def populate_player_ramp_from_game_ini(cfg: object, game_path) -> None:
    """Lê rampa do Game.ini e popula campos de contagem no cfg."""
    from pathlib import Path

    path = Path(game_path)
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-16")
    except (UnicodeDecodeError, UnicodeError, OSError):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            return
    parsed = parse_ramp_from_text(text)
    count = int(parsed.get("entry_count", 0) or 0)
    max_index = int(parsed.get("max_index", -1) or -1)
    if hasattr(cfg, "player_ramp_entry_count"):
        cfg.player_ramp_entry_count = count
    if hasattr(cfg, "player_ramp_max_index"):
        cfg.player_ramp_max_index = max_index
    count = ensure_ramp_slot_count(cfg, count)
    if hasattr(cfg, "player_ramp_entry_count"):
        cfg.player_ramp_entry_count = count
    if count > 0 and parsed.get("slots"):
        values = ramp_slots_to_values(parsed["slots"], count)
        if hasattr(cfg, "player_level_stats_raw"):
            cfg.player_level_stats_raw = export_ramp_raw(values)
        apply_inferred_xp_curve(cfg, values)
        if hasattr(cfg, "player_level_progressions_enabled"):
            cfg.player_level_progressions_enabled = True
        detect_and_apply_legacy_curve(cfg)
        if _resolve_base_level(cfg) <= 0 and count > ARK_ASCENSION_RAMP_SLOTS:
            inferred_base = max(1, count - ARK_ASCENSION_RAMP_SLOTS)
            if hasattr(cfg, "player_base_level"):
                cfg.player_base_level = inferred_base


def _curve_params_from_cfg(cfg: object | None) -> dict[str, Any]:
    if cfg is None:
        return {
            "mode": XP_CURVE_VANILLA,
            "xp_base": 70,
            "xp_mult": 1.15,
            "formula": "base * (mult ** i)",
        }
    mode = resolve_xp_curve_mode(cfg)
    return {
        "mode": mode,
        "xp_base": _read_cfg_int(cfg, "player_xp_curve_base", 70),
        "xp_mult": _read_cfg_float(cfg, "player_xp_curve_mult", 1.15),
        "formula": _read_cfg_str(cfg, "player_xp_curve_formula", "base * (mult ** i)"),
    }


def sync_config_player_level(cfg: object) -> dict[str, int]:
    """Ponto único de derivação: rampa (base+75), XP cap no base, teto base+100."""
    progressions = is_player_level_progressions_enabled(cfg)
    if progressions:
        detect_and_apply_legacy_curve(cfg)
    base = _resolve_base_level(cfg)
    ramp_base = base if base > 0 else max(
        get_ramp_entry_count(cfg) - ARK_ASCENSION_RAMP_SLOTS,
        ARK_DEFAULT_BASE_LEVEL,
    )
    ramp_base = max(1, ramp_base)

    theoretical = calc_max_total_level(ramp_base if base <= 0 else base)
    asc_bonus = ARK_TOTAL_BONUS_LEVELS

    if progressions:
        curve = _curve_params_from_cfg(cfg)
        values = build_ramp_values(
            ramp_base,
            mode=str(curve["mode"]),
            xp_base=int(curve["xp_base"]),
            xp_mult=float(curve["xp_mult"]),
            formula=str(curve["formula"]),
        )
        xp_level = base if base > 0 else ramp_base
        override_xp = cumulative_xp_on_ramp(values, xp_level)
        existing_xp = _read_override_xp_from_cfg(cfg)
        if existing_xp > override_xp:
            if (
                str(curve["mode"]).lower() == XP_CURVE_CUSTOM
                or is_legacy_geometric_xp_cap(existing_xp, ramp_base)
            ):
                override_xp = existing_xp
    else:
        values = []
        xp_level = base if base > 0 else ramp_base
        override_xp = level_to_xp(xp_level)

    effective = theoretical if base > 0 else resolve_effective_ingame_cap(
        cfg,
        theoretical=theoretical,
        base_level=ramp_base,
        ramp_values=values,
        override_xp=override_xp,
    )

    if hasattr(cfg, "override_max_xp_player"):
        cfg.override_max_xp_player = override_xp
    if hasattr(cfg, "player_ramp_entry_count"):
        cfg.player_ramp_entry_count = len(values)
    if hasattr(cfg, "player_ramp_max_index"):
        cfg.player_ramp_max_index = len(values) - 1 if values else -1
    if hasattr(cfg, "player_level_stats_raw"):
        cfg.player_level_stats_raw = export_ramp_raw(values) if values else ""

    from .player_level_ascension import serialize_ascension_state

    if hasattr(cfg, "player_ascension_state"):
        cfg.player_ascension_state = serialize_ascension_state()

    gs = getattr(cfg, "game_settings", None)
    if gs is not None:
        if hasattr(gs, "override_max_experience_points_player"):
            gs.override_max_experience_points_player = override_xp
        if hasattr(gs, "player_level_cap"):
            gs.player_level_cap = theoretical
        if hasattr(gs, "player_ascension_state"):
            gs.player_ascension_state = serialize_ascension_state()

    return {
        "base_level": base if base > 0 else ramp_base,
        "ascension_bonus": asc_bonus,
        "theoretical_total": theoretical,
        "override_xp": override_xp,
        "ramp_entries": len(values),
        "effective_ingame_cap": effective,
    }


def resolve_effective_ingame_cap(
    cfg: object,
    *,
    theoretical: int | None = None,
    base_level: int | None = None,
    ramp_values: list[int] | None = None,
    override_xp: int | None = None,
) -> int:
    """Teto in-game: base + 100 quando nível base está configurado."""
    base = int(base_level if base_level is not None else _resolve_base_level(cfg))
    if base > 0:
        return calc_max_total_level(base)

    from .player_level_ascension import resolve_theoretical_player_level

    theo = int(theoretical if theoretical is not None else resolve_theoretical_player_level(cfg))
    values = ramp_values if ramp_values is not None else get_ramp_values_from_cfg(cfg)
    ramp_count = len(values) if values else get_ramp_entry_count(cfg)
    if ramp_count <= 0 and base > 0:
        ramp_count = base

    cap_xp = override_xp
    if cap_xp is None:
        cap_xp = _read_cfg_int(cfg, "override_max_xp_player", 0)
        if cap_xp <= 0:
            gs = getattr(cfg, "game_settings", None)
            if gs is not None:
                cap_xp = _read_cfg_int(gs, "override_max_experience_points_player", 0)

    candidates = [max(1, theo)]
    if ramp_count > 0:
        candidates.append(ramp_count)
    if values and cap_xp > 0:
        lvl = xp_cap_on_ramp(values, cap_xp)
        if lvl > 0:
            candidates.append(lvl)
    elif cap_xp > 0 and not values:
        from .player_level_ascension import xp_to_level

        candidates.append(xp_to_level(cap_xp))

    return max(1, min(candidates))


def build_player_ramp_ini_lines(cfg: object) -> list[str]:
    """Linhas LevelExperienceRampOverrides para patch_game_ini_repeated_lines."""
    sync_config_player_level(cfg)
    if not is_player_level_progressions_enabled(cfg):
        return []
    values = get_ramp_values_from_cfg(cfg)
    base = _resolve_base_level(cfg) or ARK_DEFAULT_BASE_LEVEL
    expected = total_ramp_slots(base) if base > 0 else 0
    if not values or (expected > 0 and len(values) < expected):
        curve = _curve_params_from_cfg(cfg)
        values = build_ramp_values(
            base,
            mode=str(curve["mode"]),
            xp_base=int(curve["xp_base"]),
            xp_mult=float(curve["xp_mult"]),
            formula=str(curve["formula"]),
        )
    return build_ramp_ini_lines(values)


def migrate_player_level_dict(data: dict, pl: dict) -> None:
    """Migra bloco player_level unificado para campos legados."""
    if not isinstance(pl, dict):
        return
    if "base_level" in pl:
        data.setdefault("player_base_level", pl["base_level"])
    asc = pl.get("ascension")
    if isinstance(asc, dict):
        data.setdefault("player_ascension_state", json.dumps(asc, ensure_ascii=False, separators=(",", ":")))
    xpc = pl.get("xp_curve")
    if isinstance(xpc, dict):
        if xpc.get("mode"):
            data.setdefault("player_xp_curve_mode", xpc["mode"])
        custom = xpc.get("custom")
        if isinstance(custom, dict):
            if "xp_base" in custom:
                data.setdefault("player_xp_curve_base", custom["xp_base"])
            if "mult" in custom:
                data.setdefault("player_xp_curve_mult", custom["mult"])
            if "formula" in custom:
                data.setdefault("player_xp_curve_formula", custom["formula"])
    if "engram_multiplier" in pl:
        data.setdefault("player_engram_points_multiplier", pl["engram_multiplier"])
    if "progressions_enabled" in pl:
        data.setdefault("player_level_progressions_enabled", pl["progressions_enabled"])
