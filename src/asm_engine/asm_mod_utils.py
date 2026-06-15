"""
Utilitários de mods/mapas — paridade com ModUtils.cs do ARK Server Manager.
"""
from __future__ import annotations

import struct
from pathlib import Path

from .asm_server_config import AsmServerConfig


def get_map_mod_id(server_map: str) -> str:
    """Extrai workshop ID de ServerMap no formato /Game/Mods/{id}/{mapName}."""
    if not (server_map or "").strip():
        return ""
    parts = [p for p in server_map.split("/") if p]
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    if len(parts) != 4:
        return ""
    if parts[0].lower() != "game" or parts[1].lower() != "mods":
        return ""
    return parts[2]


def get_map_name_from_path(server_map: str) -> str:
    """Nome interno UE4 para a CLI — 4º segmento ou mapa vanilla."""
    if not (server_map or "").strip():
        return ""
    parts = [p for p in server_map.split("/") if p]
    if len(parts) == 1:
        return server_map.strip()
    if len(parts) != 4:
        return ""
    if parts[0].lower() != "game" or parts[1].lower() != "mods":
        return ""
    return parts[3]


def read_map_name_from_dot_mod(install_dir: str, mod_id: str) -> str:
    """Lê o primeiro mapName do arquivo {modId}.mod (como ASM ReadModFile)."""
    if not mod_id or not install_dir:
        return ""
    dot_mod = (
        Path(install_dir) / "ShooterGame" / "Content" / "Mods" / f"{mod_id}.mod"
    )
    if not dot_mod.is_file():
        return ""
    try:
        raw = dot_mod.read_bytes()
        if len(raw) < 16:
            return ""
        offset = 8
        if offset + 4 > len(raw):
            return ""
        name_len = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        if offset + name_len > len(raw):
            return ""
        mod_name = raw[offset: offset + name_len]
        offset += name_len
        if offset + 4 > len(raw):
            return ""
        mod_path_len = struct.unpack_from("<I", raw, offset)[0]
        offset += 4 + mod_path_len
        if offset + 4 > len(raw):
            return ""
        num_maps = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        for _ in range(num_maps):
            if offset + 4 > len(raw):
                break
            map_len = struct.unpack_from("<I", raw, offset)[0]
            offset += 4
            if offset + map_len > len(raw):
                break
            map_name = raw[offset: offset + map_len].decode("utf-8", errors="replace")
            if map_name:
                return map_name
            offset += map_len
    except Exception:
        pass
    return ""


def map_cli_name(server_map: str, install_dir: str = "") -> str:
    """Nome do mapa na linha de comando (GetProfileMapName / ModUtils.GetMapName)."""
    name = get_map_name_from_path(server_map)
    if name:
        return name
    mod_id = get_map_mod_id(server_map)
    if mod_id and install_dir:
        from_dot = read_map_name_from_dot_mod(install_dir, mod_id)
        if from_dot:
            return from_dot
    return (server_map or "").strip() or "TheIsland"


def normalize_server_map_path(mod_id: str, map_name: str) -> str:
    """Formato canônico ASM para mapas mod."""
    return f"/Game/Mods/{mod_id}/{map_name}"


def collect_mod_ids_for_install(cfg: AsmServerConfig) -> list[str]:
    """IDs para SteamCMD: map mod + total conversion + ActiveMods (sem duplicar)."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(mid: str) -> None:
        m = (mid or "").strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)

    _add(get_map_mod_id(cfg.server_map))
    _add(cfg.total_conversion_mod_id)
    for mid in cfg.active_mods or []:
        _add(str(mid))

    return out


def active_mods_for_ini(cfg: AsmServerConfig) -> list[str]:
    """ActiveMods no GUS — map mod fica fora (paridade ASM)."""
    map_id = get_map_mod_id(cfg.server_map)
    return [
        str(m).strip()
        for m in (cfg.active_mods or [])
        if str(m).strip() and str(m).strip() != map_id
    ]


def validate_map_mod_on_disk(cfg: AsmServerConfig) -> list[str]:
    """Avisos se mapa mod referenciado não está instalado no servidor."""
    issues: list[str] = []
    mod_id = get_map_mod_id(cfg.server_map)
    if not mod_id or not (cfg.install_dir or "").strip():
        return issues
    mods_root = Path(cfg.install_dir) / "ShooterGame" / "Content" / "Mods"
    mod_dir = mods_root / mod_id
    dot_mod = mods_root / f"{mod_id}.mod"
    if not mod_dir.is_dir():
        issues.append(
            f"Map mod {mod_id} não encontrado em Content/Mods/{mod_id}/ — "
            "use «Baixar Mods» para instalar o mapa."
        )
    elif not dot_mod.is_file():
        issues.append(
            f"Arquivo {mod_id}.mod ausente — o ARK não carrega o mapa sem ele. "
            "Baixe o mod pelo SteamCMD."
        )
    cli = map_cli_name(cfg.server_map, cfg.install_dir)
    expected = get_map_name_from_path(cfg.server_map)
    if expected and cli and expected != cli and dot_mod.is_file():
        issues.append(
            f"Nome do mapa na CLI será '{cli}' (do .mod); "
            f"configurado como '{expected}' — verifique ServerMap."
        )
    return issues
