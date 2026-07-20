"""
Utilitários de mods/mapas — paridade com ModUtils.cs do ARK Server Manager.
"""
from __future__ import annotations

import struct
from pathlib import Path

from .asm_server_config import AsmServerConfig

# Mapas oficiais ASE (vanilla + DLC). Nomes curtos na CLI — NÃO expandir para
# /Game/Mods/{ActiveMods[0]}/… (ActiveMods[0] costuma ser S+/stack, não mapa).
VANILLA_ARK_MAP_NAMES: frozenset[str] = frozenset({
    "theisland",
    "thecenter",
    "scorchedearth_p",
    "ragnarok",
    "aberration_p",
    "extinction",
    "valguero_p",
    "genesis",
    "crystalisles",
    "gen2",
    "lostisland",
    "fjordur",
    "olympus",  # raro / legado
})


def is_vanilla_ark_map(server_map: str) -> bool:
    """True se o token de mapa (ou último segmento) é mapa oficial ASE."""
    name = get_map_name_from_path(server_map) or (server_map or "").strip()
    if not name:
        return False
    return name.strip().lower() in VANILLA_ARK_MAP_NAMES


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


def should_expand_bare_map_with_active_mod(
    server_map: str,
    mod_id: str,
    install_dir: str = "",
) -> bool:
    """ServerMap curto + ActiveMods[0] → /Game/Mods/{id}/{map}?

    Só para mapas **mod** (Amissa, Alps, …). Vanilla/DLC (CrystalIsles, Gen2, …)
    nunca expandem — ActiveMods[0] em clusters reais é tipicamente S+/stack.
    Se existir ``{modId}.mod``, exige que o nome do mapa conste no ficheiro.
    """
    raw = (server_map or "").strip()
    if not raw or "/" in raw or get_map_mod_id(raw):
        return False
    mid = (mod_id or "").strip()
    if not mid.isdigit():
        return False
    map_token = map_cli_name(raw, install_dir)
    if not map_token or is_vanilla_ark_map(map_token) or is_vanilla_ark_map(raw):
        return False
    install = (install_dir or "").strip()
    if install:
        mod_dir = Path(install) / "ShooterGame" / "Content" / "Mods" / mid
        if not mod_dir.is_dir():
            return False
        from_dot = read_map_name_from_dot_mod(install, mid)
        if from_dot:
            return from_dot.strip().lower() == map_token.strip().lower()
        # Pasta existe sem .mod legível — permite expand (paridade testes / mods novos)
        return True
    # Sem install_dir: só expansível se não for vanilla (já filtrado)
    return True


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
    """ActiveMods no GUS — paridade modo primitivo (inclui map mod)."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(mid: str) -> None:
        m = (mid or "").strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)

    _add(get_map_mod_id(cfg.server_map))
    for mid in cfg.active_mods or []:
        _add(str(mid))
    return out


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
            "Use «Baixar Mods»."
        )
    else:
        from .asm_mod_copy import mod_needs_decompress_repair
        if mod_needs_decompress_repair(mod_dir):
            issues.append(
                f"Map mod {mod_id}: PrimalGameData ainda comprimido (.uasset.z) — "
                "use «Baixar Mods» para descomprimir (paridade ASM)."
            )
    cli = map_cli_name(cfg.server_map, cfg.install_dir)
    expected = get_map_name_from_path(cfg.server_map)
    if expected and cli and expected != cli and dot_mod.is_file():
        issues.append(
            f"Nome do mapa na CLI será '{cli}' (do .mod); "
            f"configurado como '{expected}' — verifique ServerMap."
        )
    return issues
